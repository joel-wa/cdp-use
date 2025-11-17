#!/usr/bin/env python3
"""
Workflow Engine - Learning, Execution, and Management

Contains workflow learning engine, execution engine, validation, and library management.
"""

import asyncio
import logging
import time
import yaml
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from collections import deque
from datetime import datetime

from mcp import ClientSession
from models import (
    WorkflowDefinition, WorkflowStep, WorkflowParameter, WorkflowExecutionContext,
    WorkflowExecutionResult, WorkflowSession, WorkflowPattern, WorkflowCandidate,
    ToolExecutionResult, ToolExecutionStatus, WorkflowExecutionError,
    RetryPolicy, StepValidation, ValidationResult
)
from config import (
    WORKFLOWS_DIR, WORKFLOW_PATTERN_MIN_LENGTH, AUTO_SUGGEST_WORKFLOWS,
    logger
)


# =====================================================
# PATTERN ANALYSIS & LEARNING
# =====================================================

class PatternAnalyzer:
    """Analyzes tool execution patterns for workflow candidacy"""
    
    def __init__(self):
        self.web_patterns = [
            ["navigate", "take_screenshot", "get_interactive_elements"],
            ["navigate", "execute_javascript", "take_screenshot"], 
            ["navigate", "get_page_content", "execute_javascript"],
            ["click_element_by_index", "wait_for_element", "execute_javascript"],
            ["get_interactive_elements", "click_element_by_index", "get_page_content"]
        ]
        
        self.file_patterns = [
            ["list_directory", "read_file", "execute_javascript"],
            ["read_file", "execute_javascript", "write_file"],
            ["navigate", "get_page_content", "read_file"]
        ]
        
        self.automation_patterns = [
            ["take_screenshot", "get_interactive_elements", "click_element_by_index"],
            ["navigate", "type_text", "click_element_by_index"],
            ["execute_javascript", "take_screenshot", "get_page_content"]
        ]
    
    def matches_pattern(self, tool_sequence: List[str], pattern: List[str]) -> bool:
        """Check if tool sequence matches a known pattern"""
        if len(tool_sequence) < len(pattern):
            return False
            
        pattern_idx = 0
        for tool in tool_sequence:
            if pattern_idx < len(pattern) and tool == pattern[pattern_idx]:
                pattern_idx += 1
                
        return pattern_idx == len(pattern)
    
    def analyze_chain_for_patterns(self, chain: List[ToolExecutionResult]) -> List[str]:
        """Analyze tool chain and return matching pattern names"""
        tool_names = [result.tool_name for result in chain]
        matching_patterns = []
        
        all_patterns = {
            "web_automation": self.web_patterns,
            "file_processing": self.file_patterns,
            "ui_automation": self.automation_patterns
        }
        
        for pattern_category, patterns in all_patterns.items():
            for pattern in patterns:
                if self.matches_pattern(tool_names, pattern):
                    matching_patterns.append(pattern_category)
                    break
                    
        return matching_patterns


class ParameterExtractor:
    """Extracts parameterizable values from tool execution history"""
    
    def extract_parameters(self, chain: List[ToolExecutionResult]) -> List[WorkflowParameter]:
        """Extract parameters from successful tool chain"""
        parameters = []
        
        for result in chain:
            params = self._analyze_tool_arguments(result)
            parameters.extend(params)
            
        return self._merge_parameters(parameters)
        
    def _analyze_tool_arguments(self, result: ToolExecutionResult) -> List[WorkflowParameter]:
        """Analyze tool arguments to identify parameterizable values"""
        parameters = []
        
        for arg_name, arg_value in result.arguments.items():
            if isinstance(arg_value, str) and arg_value.startswith(('http://', 'https://')):
                parameters.append(WorkflowParameter(
                    name=f"{result.tool_name}_{arg_name}",
                    type="string",
                    description=f"URL for {result.tool_name}",
                    validation={"pattern": "^https?://.+"},
                    default=arg_value
                ))
                
            elif isinstance(arg_value, str) and ('/' in arg_value or '\\' in arg_value):
                parameters.append(WorkflowParameter(
                    name=f"{result.tool_name}_{arg_name}",
                    type="string", 
                    description=f"File path for {result.tool_name}",
                    default=arg_value
                ))
                
            elif isinstance(arg_value, (int, float)) and arg_value > 0:
                parameters.append(WorkflowParameter(
                    name=f"{result.tool_name}_{arg_name}",
                    type="integer" if isinstance(arg_value, int) else "float",
                    description=f"Numeric parameter for {result.tool_name}",
                    validation={"min": 0},
                    default=arg_value
                ))
                
            elif isinstance(arg_value, str) and len(arg_value) > 10 and ' ' in arg_value:
                parameters.append(WorkflowParameter(
                    name=f"{result.tool_name}_{arg_name}",
                    type="string",
                    description=f"Text content for {result.tool_name}",
                    default=arg_value
                ))
                
        return parameters
    
    def _merge_parameters(self, parameters: List[WorkflowParameter]) -> List[WorkflowParameter]:
        """Merge similar parameters and deduplicate"""
        merged = {}
        
        for param in parameters:
            key = param.name
            if key in merged:
                if len(param.validation) > len(merged[key].validation):
                    merged[key] = param
            else:
                merged[key] = param
                
        return list(merged.values())


class WorkflowLearningEngine:
    """Learns workflows from agent execution patterns"""
    
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.pattern_analyzer = PatternAnalyzer()
        self.parameter_extractor = ParameterExtractor()
        self.min_chain_length = WORKFLOW_PATTERN_MIN_LENGTH
        
    async def analyze_session_for_workflows(self) -> List[WorkflowCandidate]:
        """Analyze current session to identify repeatable patterns"""
        execution_history = self.orchestrator.system_state.tool_execution_history
        tool_chains = self._group_tool_chains(execution_history)
        
        candidates = []
        for chain in tool_chains:
            if self._is_workflow_candidate(chain):
                candidate = await self._create_workflow_candidate(chain)
                candidates.append(candidate)
                
        return candidates
        
    def _group_tool_chains(self, history: List[ToolExecutionResult]) -> List[List[ToolExecutionResult]]:
        """Group consecutive successful tool executions into chains"""
        chains = []
        current_chain = []
        
        for result in history:
            if result.status == ToolExecutionStatus.COMPLETED:
                current_chain.append(result)
            else:
                if len(current_chain) >= self.min_chain_length:
                    chains.append(current_chain)
                current_chain = []
                
        if len(current_chain) >= self.min_chain_length:
            chains.append(current_chain)
            
        return chains
        
    def _is_workflow_candidate(self, chain: List[ToolExecutionResult]) -> bool:
        """Determine if tool chain is suitable for workflow creation"""
        if len(chain) < self.min_chain_length:
            return False
            
        matching_patterns = self.pattern_analyzer.analyze_chain_for_patterns(chain)
        if not matching_patterns:
            parameters = self.parameter_extractor.extract_parameters(chain)
            return len(parameters) >= 1
            
        return True
    
    async def _create_workflow_candidate(self, chain: List[ToolExecutionResult]) -> WorkflowCandidate:
        """Create workflow candidate from tool chain"""
        suggested_parameters = self.parameter_extractor.extract_parameters(chain)
        confidence_score = self._calculate_confidence_score(chain, suggested_parameters)
        
        tool_names = [r.tool_name for r in chain]
        name = f"workflow_{tool_names[0]}_to_{tool_names[-1]}"
        description = f"Automated workflow: {' → '.join(tool_names[:3])}{'...' if len(tool_names) > 3 else ''}"
        
        return WorkflowCandidate(
            name=name,
            description=description,
            tool_chain=chain,
            confidence_score=confidence_score,
            suggested_parameters=suggested_parameters,
            estimated_reusability=confidence_score * 0.8
        )
    
    def _calculate_confidence_score(self, chain: List[ToolExecutionResult], 
                                  parameters: List[WorkflowParameter]) -> float:
        """Calculate confidence score for workflow candidacy"""
        base_score = 0.5
        
        matching_patterns = self.pattern_analyzer.analyze_chain_for_patterns(chain)
        if matching_patterns:
            base_score += 0.2
            
        if parameters:
            base_score += min(0.3, len(parameters) * 0.1)
            
        length_boost = min(0.2, (len(chain) - self.min_chain_length) * 0.05)
        base_score += length_boost
        
        failed_count = sum(1 for r in chain if r.status == ToolExecutionStatus.FAILED)
        if failed_count > 0:
            base_score -= failed_count * 0.1
            
        return max(0.0, min(1.0, base_score))


# =====================================================
# WORKFLOW VALIDATION & EXECUTION
# =====================================================

class WorkflowValidator:
    """Validates workflow definitions and parameters"""
    
    def validate_workflow_definition(self, workflow: WorkflowDefinition) -> Tuple[bool, List[str]]:
        """Validate workflow definition for correctness"""
        errors = []
        
        if not workflow.name or not workflow.name.strip():
            errors.append("Workflow name is required")
            
        if not workflow.steps:
            errors.append("Workflow must have at least one step")
            
        step_ids = {step.id for step in workflow.steps}
        for step in workflow.steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    errors.append(f"Step {step.id} depends on non-existent step {dep}")
                    
        if self._has_circular_dependencies(workflow.steps):
            errors.append("Circular dependencies detected in workflow steps")
            
        return len(errors) == 0, errors
    
    def validate_parameters(self, workflow: WorkflowDefinition, 
                          parameters: Dict[str, Any]) -> ValidationResult:
        """Validate provided parameters against workflow definition"""
        errors = []
        warnings = []
        
        for param in workflow.parameters:
            if param.required and param.name not in parameters:
                if param.default is not None:
                    parameters[param.name] = param.default
                    warnings.append(f"Using default value for {param.name}: {param.default}")
                else:
                    errors.append(f"Required parameter {param.name} is missing")
            elif param.name in parameters:
                is_valid, error = param.validate(parameters[param.name])
                if not is_valid:
                    errors.append(f"Parameter {param.name}: {error}")
                    
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    def _has_circular_dependencies(self, steps: List[WorkflowStep]) -> bool:
        """Check for circular dependencies using DFS"""
        graph = {step.id: step.depends_on for step in steps}
        states = {step_id: 0 for step_id in graph}
        
        def has_cycle(node_id: str) -> bool:
            if states[node_id] == 1:
                return True
            if states[node_id] == 2:
                return False
                
            states[node_id] = 1
            
            for dep in graph.get(node_id, []):
                if dep in states and has_cycle(dep):
                    return True
                    
            states[node_id] = 2
            return False
        
        return any(has_cycle(step_id) for step_id in graph if states[step_id] == 0)


class WorkflowStateManager:
    """Manages state during workflow execution"""
    
    def __init__(self):
        self.execution_states = {}
        self.step_dependencies = {}
        
    def can_execute_step(self, step: WorkflowStep, context: WorkflowExecutionContext) -> bool:
        """Check if step dependencies are satisfied"""
        for dep_id in step.depends_on:
            if dep_id not in context.step_results:
                return False
        return True
    
    def evaluate_condition(self, condition: str, context: WorkflowExecutionContext) -> bool:
        """Evaluate step condition using context variables"""
        if not condition:
            return True
            
        try:
            variables = context.get_variables()
            
            for var_name, var_value in variables.items():
                condition = condition.replace(f"{{{{{var_name}}}}}", str(var_value))
                
            if "==" in condition:
                left, right = condition.split("==", 1)
                return left.strip().strip('"') == right.strip().strip('"')
            elif "!=" in condition:
                left, right = condition.split("!=", 1)
                return left.strip().strip('"') != right.strip().strip('"')
            elif condition.lower() in ['true', 'false']:
                return condition.lower() == 'true'
                
            return True
            
        except Exception as e:
            logger.warning(f"Error evaluating condition '{condition}': {e}")
            return True


class WorkflowExecutor:
    """Executes workflows without LLM intervention"""
    
    def __init__(self, mcp_session: ClientSession):
        self.mcp_session = mcp_session
        self.validator = WorkflowValidator()
        self.state_manager = WorkflowStateManager()
        
    async def execute_workflow(self, workflow: WorkflowDefinition, 
                              parameters: Dict[str, Any]) -> WorkflowExecutionResult:
        """Execute workflow with given parameters"""
        start_time = datetime.now()
        
        is_valid, validation_errors = self.validator.validate_workflow_definition(workflow)
        if not is_valid:
            return WorkflowExecutionResult(
                workflow_name=workflow.name,
                success=False, 
                execution_time=datetime.now() - start_time,
                steps_executed=0,
                error=f"Workflow validation failed: {'; '.join(validation_errors)}"
            )
        
        validation_result = self.validator.validate_parameters(workflow, parameters)
        if not validation_result.is_valid:
            return WorkflowExecutionResult(
                workflow_name=workflow.name,
                success=False,
                execution_time=datetime.now() - start_time,
                steps_executed=0,
                error=f"Parameter validation failed: {'; '.join(validation_result.errors)}"
            )
        
        context = WorkflowExecutionContext(
            workflow=workflow,
            parameters=parameters,
            start_time=start_time
        )
        
        context.log(f"Starting workflow execution: {workflow.name}")
        
        try:
            execution_order = self._calculate_execution_order(workflow.steps)
            
            executed_count = 0
            for step in execution_order:
                if await self._execute_step(step, context):
                    executed_count += 1
                else:
                    if not workflow.error_handling.continue_on_error:
                        break
                        
            outputs = self._process_outputs(workflow.outputs, context)
            
            return WorkflowExecutionResult(
                workflow_name=workflow.name,
                success=True,
                execution_time=datetime.now() - context.start_time,
                steps_executed=executed_count,
                outputs=outputs,
                execution_log=context.execution_log
            )
            
        except WorkflowExecutionError as e:
            return WorkflowExecutionResult(
                workflow_name=workflow.name,
                success=False,
                execution_time=datetime.now() - context.start_time,
                steps_executed=len(context.step_results),
                error=str(e),
                partial_outputs=context.step_results,
                execution_log=context.execution_log
            )
    
    def _calculate_execution_order(self, steps: List[WorkflowStep]) -> List[WorkflowStep]:
        """Calculate step execution order based on dependencies"""
        step_dict = {step.id: step for step in steps}
        in_degree = {step.id: 0 for step in steps}
        
        for step in steps:
            for dep in step.depends_on:
                if dep in in_degree:
                    in_degree[step.id] += 1
                    
        queue = deque([step_id for step_id, degree in in_degree.items() if degree == 0])
        result = []
        
        while queue:
            step_id = queue.popleft()
            step = step_dict[step_id]
            result.append(step)
            
            for other_step in steps:
                if step_id in other_step.depends_on:
                    in_degree[other_step.id] -= 1
                    if in_degree[other_step.id] == 0:
                        queue.append(other_step.id)
                        
        return result
            
    async def _execute_step(self, step: WorkflowStep, context: WorkflowExecutionContext) -> bool:
        """Execute individual workflow step"""
        context.log(f"Executing step: {step.id} ({step.tool})")
        
        if not self.state_manager.can_execute_step(step, context):
            error_msg = f"Dependencies not satisfied for step {step.id}"
            context.log(f"❌ {error_msg}")
            raise WorkflowExecutionError(error_msg)
            
        if step.conditional and not self.state_manager.evaluate_condition(step.conditional, context):
            context.log(f"⏭️  Skipping step {step.id} due to condition: {step.conditional}")
            return True
            
        resolved_params = step.resolve_parameters(context.get_variables())
        context.log(f"Resolved parameters: {resolved_params}")
        
        retry_policy = step.retry_policy or RetryPolicy()
        
        for attempt in range(retry_policy.max_attempts):
            try:
                context.log(f"Attempt {attempt + 1}/{retry_policy.max_attempts}")
                
                result = await self.mcp_session.call_tool(step.tool, resolved_params)
                
                if step.validation and not self._validate_step_result(step.validation, result):
                    raise WorkflowExecutionError(f"Step validation failed for {step.id}")
                    
                context.step_results[step.id] = result
                context.log(f"✅ Step {step.id} executed successfully")
                return True
                
            except Exception as e:
                error_msg = f"Step {step.id} attempt {attempt + 1} failed: {e}"
                context.log(f"❌ {error_msg}")
                
                if attempt < retry_policy.max_attempts - 1:
                    delay = retry_policy.get_delay(attempt)
                    context.log(f"⏳ Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise WorkflowExecutionError(f"Step {step.id} failed after {retry_policy.max_attempts} attempts: {e}")
                    
        return False
    
    def _validate_step_result(self, validation: StepValidation, result: Any) -> bool:
        """Validate step execution result"""
        try:
            if validation.success_condition:
                condition = validation.success_condition
                
                if "result" in condition:
                    condition = condition.replace("result", str(result))
                    
                if "!=" in condition:
                    left, right = condition.split("!=", 1)
                    return left.strip() != right.strip()
                elif "==" in condition:
                    left, right = condition.split("==", 1)
                    return left.strip() == right.strip()
                elif condition in ["true", "True"]:
                    return True
                elif condition in ["false", "False"]:
                    return False
                    
            return True
            
        except Exception as e:
            logger.warning(f"Error in step validation: {e}")
            return True
    
    def _process_outputs(self, output_configs, context: WorkflowExecutionContext) -> Dict[str, Any]:
        """Process workflow outputs from execution context"""
        outputs = {}
        
        for output_config in output_configs:
            try:
                if output_config.source == "workflow.execution_log":
                    outputs[output_config.name] = context.execution_log
                elif output_config.source.startswith("workflow."):
                    prop_name = output_config.source.split(".", 1)[1]
                    if prop_name == "execution_time":
                        outputs[output_config.name] = (datetime.now() - context.start_time).total_seconds()
                elif "." in output_config.source:
                    step_id, result_path = output_config.source.split(".", 1)
                    if step_id in context.step_results:
                        result_data = context.step_results[step_id]
                        if result_path == "result":
                            outputs[output_config.name] = result_data
                        else:
                            value = result_data
                            for key in result_path.split("."):
                                if isinstance(value, dict) and key in value:
                                    value = value[key]
                                else:
                                    value = None
                                    break
                            outputs[output_config.name] = value
                            
            except Exception as e:
                logger.warning(f"Error processing output {output_config.name}: {e}")
                outputs[output_config.name] = None
                
        return outputs


# =====================================================
# WORKFLOW LIBRARY & RECORDING
# =====================================================

class WorkflowLibrary:
    """Manages workflow definitions and execution"""
    
    def __init__(self, storage_path: str = WORKFLOWS_DIR):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.workflows: Dict[str, WorkflowDefinition] = {}
        self.execution_history: List[WorkflowExecutionResult] = []
        
    async def save_workflow(self, workflow: WorkflowDefinition):
        """Save workflow definition to storage"""
        workflow_path = self.storage_path / f"{workflow.name}.yaml"
        
        with open(workflow_path, 'w', encoding='utf-8') as f:
            yaml.dump(workflow.to_dict(), f, default_flow_style=False, allow_unicode=True)
            
        self.workflows[workflow.name] = workflow
        logger.info(f"📁 Saved workflow: {workflow.name} to {workflow_path}")
        
    async def load_workflow(self, name: str) -> Optional[WorkflowDefinition]:
        """Load workflow definition from storage"""
        if name in self.workflows:
            return self.workflows[name]
            
        workflow_path = self.storage_path / f"{name}.yaml"
        if workflow_path.exists():
            try:
                with open(workflow_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    workflow = WorkflowDefinition.from_dict(data)
                    self.workflows[name] = workflow
                    return workflow
            except Exception as e:
                logger.error(f"Error loading workflow {name}: {e}")
                return None
                
        return None
        
    async def list_workflows(self) -> List[str]:
        """List available workflow names"""
        workflows = list(self.workflows.keys())
        
        if self.storage_path.exists():
            for file_path in self.storage_path.glob("*.yaml"):
                name = file_path.stem
                if name not in workflows:
                    workflows.append(name)
                        
        return sorted(workflows)
    
    async def delete_workflow(self, name: str) -> bool:
        """Delete workflow from storage"""
        try:
            workflow_path = self.storage_path / f"{name}.yaml"
            if workflow_path.exists():
                workflow_path.unlink()
                
            if name in self.workflows:
                del self.workflows[name]
                
            logger.info(f"🗑️  Deleted workflow: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting workflow {name}: {e}")
            return False
    
    async def search_workflows(self, query: str) -> List[WorkflowDefinition]:
        """Search workflows by name or description"""
        results = []
        query_lower = query.lower()
        
        all_names = await self.list_workflows()
        for name in all_names:
            workflow = await self.load_workflow(name)
            if workflow and (
                query_lower in workflow.name.lower() or 
                query_lower in workflow.description.lower()
            ):
                results.append(workflow)
                
        return results
    
    def record_execution(self, result: WorkflowExecutionResult):
        """Record workflow execution result"""
        self.execution_history.append(result)
        
        if len(self.execution_history) > 1000:
            self.execution_history = self.execution_history[-500:]
    
    async def get_workflow_stats(self, name: str) -> Dict[str, Any]:
        """Get execution statistics for a workflow"""
        executions = [r for r in self.execution_history if r.workflow_name == name]
        
        if not executions:
            return {"executions": 0, "success_rate": 0, "avg_duration": 0}
            
        success_count = sum(1 for r in executions if r.success)
        total_duration = sum(r.execution_time.total_seconds() for r in executions)
        
        return {
            "executions": len(executions),
            "success_rate": success_count / len(executions),
            "avg_duration": total_duration / len(executions),
            "last_execution": executions[-1].timestamp.isoformat(),
            "last_success": executions[-1].success
        }


class WorkflowRecordingMode:
    """Extension to orchestrator for workflow recording"""
    
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.recording_session: Optional[WorkflowSession] = None
        self.learning_engine = WorkflowLearningEngine(orchestrator)
        self.workflow_library = WorkflowLibrary()
        
    async def start_recording(self, session_name: str, description: str = ""):
        """Start recording session for workflow creation"""
        self.recording_session = WorkflowSession(
            name=session_name,
            description=description,
            start_time=datetime.now()
        )
        
        self.orchestrator.system_state.tool_execution_history.clear()
        
        logger.info(f"🎬 Started workflow recording: {session_name}")
        return f"🎬 Recording started: {session_name}. All subsequent tool executions will be captured for workflow creation."
        
    async def stop_recording_and_create_workflow(self, user_intent: str = "") -> Optional[WorkflowDefinition]:
        """Stop recording and attempt to create workflow"""
        if not self.recording_session:
            return None
            
        candidates = await self.learning_engine.analyze_session_for_workflows()
        
        if not candidates:
            logger.info("No workflow patterns detected in recording session")
            self.recording_session = None
            return None
            
        best_candidate = max(candidates, key=lambda c: c.confidence_score)
        
        workflow = WorkflowDefinition.from_execution_history(
            best_candidate.tool_chain,
            user_intent or self.recording_session.description,
            self.recording_session.name
        )
        
        await self.workflow_library.save_workflow(workflow)
        
        self.recording_session = None
        
        logger.info(f"✅ Created workflow: {workflow.name} with {len(workflow.steps)} steps")
        return workflow
        
    def is_recording(self) -> bool:
        """Check if currently recording"""
        return self.recording_session is not None
        
    async def suggest_workflow_improvements(self, workflow_name: str) -> List[str]:
        """Analyze workflow execution to suggest improvements"""
        stats = await self.workflow_library.get_workflow_stats(workflow_name)
        suggestions = []
        
        if stats["success_rate"] < 0.8:
            suggestions.append("Consider adding more retry attempts or better error handling")
            
        if stats["avg_duration"] > 60:
            suggestions.append("Workflow takes a long time - consider optimizing step dependencies")
            
        if stats["executions"] < 5:
            suggestions.append("More executions needed to gather reliable statistics")
            
        return suggestions
    
    async def auto_suggest_workflows(self) -> List[WorkflowCandidate]:
        """Automatically suggest workflows based on recent activity"""
        if not AUTO_SUGGEST_WORKFLOWS:
            return []
            
        recent_history = self.orchestrator.system_state.tool_execution_history[-20:]
        
        if len(recent_history) < WORKFLOW_PATTERN_MIN_LENGTH:
            return []
            
        candidates = await self.learning_engine.analyze_session_for_workflows()
        high_confidence = [c for c in candidates if c.confidence_score > 0.7]
        
        return high_confidence
