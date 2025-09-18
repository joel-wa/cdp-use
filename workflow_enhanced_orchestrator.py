#!/usr/bin/env python3
"""
Workflow-Enhanced Conversational MCP Orchestrator

Advanced implementation with workflow automation capabilities that:
1. Maintains all Enhanced Conversational Orchestrator features
2. Adds workflow capture, parameterization, and replay functionality
3. Implements pattern recognition and learning from successful interactions
4. Provides deterministic workflow execution without LLM intervention
5. Includes comprehensive workflow management and CLI interface

This transforms the orchestrator from reactive tool execution to proactive automation platform
that learns and codifies successful patterns for reliable, repeatable execution.

Author: Agent-Space Team
Version: 3.0 Workflow Enhanced
"""

import os
import sys
import time
import json
import yaml
import re
import asyncio
import logging
import traceback
from typing import Dict, Any, List, Optional, Tuple, AsyncGenerator, Union
from contextlib import AsyncExitStack
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
from dotenv import load_dotenv
from pathlib import Path
import tempfile

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'BrowserAgent', 'clients', 'gemini'))

from google import genai
from google.genai import types

# Import MCP components
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import Tool

# Load environment variables
load_dotenv()

# Configuration with enhanced defaults
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:12306/mcp")
MCP_SERVER_COMMAND = os.getenv("MCP_SERVER_COMMAND", '"C:\\Users\\RanVic\\cdp-use\\.venv\\Scripts\\python.exe" "C:\\Users\\RanVic\\cdp-use\\examples\\mcp_browser_control.py" --server-only')
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ENABLE_VISUAL_CONTEXT = os.getenv("ENABLE_VISUAL_CONTEXT", "true").lower() == "true"
ENABLE_INTERACTIVE_CONTEXT = os.getenv("ENABLE_INTERACTIVE_CONTEXT", "true").lower() == "true"
MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", str(1024 * 1024)))  # 1MB
AUTO_SCREENSHOT_INTERVAL = int(os.getenv("AUTO_SCREENSHOT_INTERVAL", "0"))
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "20"))

# Enhanced configuration options
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "100000"))
ENABLE_STREAMING = os.getenv("ENABLE_STREAMING", "true").lower() == "true"
ENABLE_TOOL_VALIDATION = os.getenv("ENABLE_TOOL_VALIDATION", "true").lower() == "true" 
ENABLE_ERROR_RECOVERY = os.getenv("ENABLE_ERROR_RECOVERY", "true").lower() == "true"
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
TOOL_EXECUTION_TIMEOUT = int(os.getenv("TOOL_EXECUTION_TIMEOUT", "60"))

# Workflow-specific configuration
WORKFLOWS_DIR = os.getenv("WORKFLOWS_DIR", "./workflows")
ENABLE_WORKFLOW_LEARNING = os.getenv("ENABLE_WORKFLOW_LEARNING", "true").lower() == "true"
WORKFLOW_PATTERN_MIN_LENGTH = int(os.getenv("WORKFLOW_PATTERN_MIN_LENGTH", "3"))
AUTO_SUGGEST_WORKFLOWS = os.getenv("AUTO_SUGGEST_WORKFLOWS", "true").lower() == "true"
WORKFLOW_EXECUTION_MODE = os.getenv("WORKFLOW_EXECUTION_MODE", "interactive")  # interactive, automatic, mixed

# Setup enhanced logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Classification of error severity levels"""
    INFO = "info"
    WARNING = "warning" 
    RECOVERABLE = "recoverable"
    CRITICAL = "critical"
    FATAL = "fatal"


class ToolExecutionStatus(Enum):
    """Tool execution status tracking"""
    PENDING = "pending"
    VALIDATING = "validating"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class WorkflowExecutionStatus(Enum):
    """Workflow execution status tracking"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


# =====================================================
# WORKFLOW CORE DATA MODELS
# =====================================================

@dataclass
class RetryPolicy:
    """Retry policy configuration for workflow steps"""
    max_attempts: int = 3
    backoff_strategy: str = "exponential"  # exponential, linear, fixed
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number"""
        if self.backoff_strategy == "exponential":
            delay = self.initial_delay * (self.backoff_multiplier ** attempt)
        elif self.backoff_strategy == "linear":
            delay = self.initial_delay * (attempt + 1)
        else:  # fixed
            delay = self.initial_delay
            
        return min(delay, self.max_delay)


@dataclass
class StepValidation:
    """Validation configuration for workflow steps"""
    success_condition: Optional[str] = None  # JavaScript-like condition
    timeout_seconds: Optional[int] = None
    retry_on_condition: Optional[str] = None
    expected_output_type: Optional[str] = None


@dataclass
class WorkflowParameter:
    """Workflow input parameter definition"""
    name: str
    type: str  # string, integer, float, boolean, array, object
    required: bool = True
    default: Any = None
    description: str = ""
    validation: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self, value: Any) -> Tuple[bool, Optional[str]]:
        """Validate parameter value"""
        # Type validation
        if self.type == "string" and not isinstance(value, str):
            return False, f"Expected string, got {type(value).__name__}"
        elif self.type == "integer" and not isinstance(value, int):
            return False, f"Expected integer, got {type(value).__name__}"
        elif self.type == "float" and not isinstance(value, (int, float)):
            return False, f"Expected float, got {type(value).__name__}"
        elif self.type == "boolean" and not isinstance(value, bool):
            return False, f"Expected boolean, got {type(value).__name__}"
        elif self.type == "array" and not isinstance(value, list):
            return False, f"Expected array, got {type(value).__name__}"
        elif self.type == "object" and not isinstance(value, dict):
            return False, f"Expected object, got {type(value).__name__}"
            
        # Custom validation rules
        if self.validation:
            if "pattern" in self.validation and isinstance(value, str):
                if not re.match(self.validation["pattern"], value):
                    return False, f"Value does not match pattern {self.validation['pattern']}"
            
            if "min" in self.validation and isinstance(value, (int, float)):
                if value < self.validation["min"]:
                    return False, f"Value {value} is less than minimum {self.validation['min']}"
                    
            if "max" in self.validation and isinstance(value, (int, float)):
                if value > self.validation["max"]:
                    return False, f"Value {value} is greater than maximum {self.validation['max']}"
                    
            if "enum" in self.validation:
                if value not in self.validation["enum"]:
                    return False, f"Value {value} not in allowed values {self.validation['enum']}"
        
        return True, None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowParameter':
        """Create from dictionary"""
        return cls(**data)


@dataclass 
class WorkflowStep:
    """Individual workflow step definition"""
    id: str
    tool: str
    description: str
    parameters: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)
    retry_policy: Optional[RetryPolicy] = None
    validation: Optional[StepValidation] = None
    conditional: Optional[str] = None  # Condition for step execution
    
    def resolve_parameters(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve parameter templates with context values"""
        resolved = {}
        
        for key, value in self.parameters.items():
            if isinstance(value, str) and "{{" in value and "}}" in value:
                # Template substitution
                template = value
                for var_name, var_value in context.items():
                    template = template.replace(f"{{{{{var_name}}}}}", str(var_value))
                resolved[key] = template
            else:
                resolved[key] = value
                
        return resolved
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        if self.retry_policy:
            result["retry_policy"] = asdict(self.retry_policy)
        if self.validation:
            result["validation"] = asdict(self.validation)
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowStep':
        """Create from dictionary"""
        if "retry_policy" in data and data["retry_policy"]:
            data["retry_policy"] = RetryPolicy(**data["retry_policy"])
        if "validation" in data and data["validation"]:
            data["validation"] = StepValidation(**data["validation"])
        return cls(**data)


@dataclass
class ErrorHandlingConfig:
    """Error handling configuration for workflows"""
    global_retry_limit: int = 3
    timeout_seconds: int = 300
    recovery_strategies: List[Dict[str, Any]] = field(default_factory=list)
    continue_on_error: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ErrorHandlingConfig':
        """Create from dictionary"""
        return cls(**data)


@dataclass
class WorkflowOutput:
    """Workflow output configuration"""
    name: str
    source: str  # Reference to step result or workflow property
    format: str = "json"
    transformation: Optional[str] = None  # JavaScript-like transformation
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowOutput':
        """Create from dictionary"""
        return cls(**data)


@dataclass
class WorkflowDefinition:
    """Defines a reusable workflow"""
    name: str
    version: str
    description: str
    parameters: List[WorkflowParameter]
    steps: List[WorkflowStep]
    error_handling: ErrorHandlingConfig
    outputs: List[WorkflowOutput]
    metadata: Dict[str, Any] = field(default_factory=dict)
    author: str = "agent_learning"
    created_at: datetime = field(default_factory=datetime.now)
    
    @classmethod
    def from_execution_history(cls, history: List['ToolExecutionResult'], 
                             user_intent: str, name: str) -> 'WorkflowDefinition':
        """Extract workflow from successful tool execution chain"""
        # Create workflow steps from execution history
        steps = []
        parameters = []
        
        for i, result in enumerate(history):
            if result.status == ToolExecutionStatus.COMPLETED:
                step_id = f"step_{i+1}_{result.tool_name}"
                
                # Extract parameters that could be templated
                step_params = {}
                for arg_name, arg_value in result.arguments.items():
                    if isinstance(arg_value, str) and (
                        arg_value.startswith(('http://', 'https://')) or
                        '/' in arg_value or '\\' in arg_value
                    ):
                        # This looks like a URL or file path - make it a parameter
                        param_name = f"{result.tool_name}_{arg_name}"
                        step_params[arg_name] = f"{{{{{param_name}}}}}"
                        
                        # Add to workflow parameters if not already present
                        if not any(p.name == param_name for p in parameters):
                            param_type = "string"
                            validation = {}
                            if arg_value.startswith(('http://', 'https://')):
                                validation["pattern"] = "^https?://.+"
                                
                            parameters.append(WorkflowParameter(
                                name=param_name,
                                type=param_type,
                                description=f"Parameter for {result.tool_name}",
                                validation=validation,
                                default=arg_value
                            ))
                    else:
                        step_params[arg_name] = arg_value
                
                # Create workflow step
                step = WorkflowStep(
                    id=step_id,
                    tool=result.tool_name,
                    description=f"Execute {result.tool_name}",
                    parameters=step_params,
                    depends_on=[f"step_{i}_{history[i-1].tool_name}"] if i > 0 else [],
                    retry_policy=RetryPolicy(max_attempts=2)
                )
                steps.append(step)
        
        # Create default outputs
        outputs = [
            WorkflowOutput(
                name="execution_log",
                source="workflow.execution_log",
                format="json"
            )
        ]
        
        # If last step produces results, add as output
        if steps and history:
            last_result = history[-1]
            if last_result.result:
                outputs.append(WorkflowOutput(
                    name="final_result", 
                    source=f"{steps[-1].id}.result",
                    format="json"
                ))
        
        return cls(
            name=name,
            version="1.0",
            description=user_intent or "Automatically generated workflow",
            parameters=parameters,
            steps=steps,
            error_handling=ErrorHandlingConfig(),
            outputs=outputs,
            metadata={
                "source": "execution_history",
                "original_tool_count": len(history),
                "success_rate": len([r for r in history if r.status == ToolExecutionStatus.COMPLETED]) / len(history) if history else 0
            }
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        result = {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
            "parameters": [p.to_dict() for p in self.parameters],
            "steps": [s.to_dict() for s in self.steps],
            "error_handling": self.error_handling.to_dict(),
            "outputs": [o.to_dict() for o in self.outputs],
            "metadata": self.metadata
        }
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowDefinition':
        """Create from dictionary"""
        parameters = [WorkflowParameter.from_dict(p) for p in data.get("parameters", [])]
        steps = [WorkflowStep.from_dict(s) for s in data.get("steps", [])]
        error_handling = ErrorHandlingConfig.from_dict(data.get("error_handling", {}))
        outputs = [WorkflowOutput.from_dict(o) for o in data.get("outputs", [])]
        
        created_at = datetime.now()
        if "created_at" in data:
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except:
                pass
        
        return cls(
            name=data["name"],
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
            author=data.get("author", "agent_learning"),
            created_at=created_at,
            parameters=parameters,
            steps=steps,
            error_handling=error_handling,
            outputs=outputs,
            metadata=data.get("metadata", {})
        )


@dataclass
class ToolExecutionResult:
    """Enhanced tool execution result with metadata"""
    tool_name: str
    arguments: Dict[str, Any]
    status: ToolExecutionStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    retry_count: int = 0
    context_updates: List[str] = field(default_factory=list)
    state_changes: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass 
class SystemState:
    """Comprehensive system state tracking"""
    current_directory: Optional[str] = None
    file_system_cache: Dict[str, Any] = field(default_factory=dict)
    browser_state: Dict[str, Any] = field(default_factory=dict)
    executed_commands: deque = field(default_factory=lambda: deque(maxlen=100))
    environment_vars: Dict[str, str] = field(default_factory=dict)
    session_start_time: datetime = field(default_factory=datetime.now)
    tool_execution_history: List[ToolExecutionResult] = field(default_factory=list)
    context_cache: Dict[str, Any] = field(default_factory=dict)
    last_error: Optional[str] = None
    
    # Workflow-specific state
    workflow_execution_history: List['WorkflowExecutionResult'] = field(default_factory=list)
    current_workflow_session: Optional['WorkflowSession'] = None
    learned_patterns: List['WorkflowPattern'] = field(default_factory=list)
    
    def update_from_tool_result(self, result: ToolExecutionResult):
        """Update system state from tool execution result"""
        self.tool_execution_history.append(result)
        
        # Update context cache based on tool type
        if result.tool_name == "navigate" and result.status == ToolExecutionStatus.COMPLETED:
            if result.arguments.get("url"):
                self.browser_state["current_url"] = result.arguments["url"]
                
        elif result.tool_name == "get_page_content" and result.result:
            self.browser_state["last_content"] = result.result
            
        elif result.tool_name in ["list_directory", "read_file"] and result.result:
            if result.arguments.get("path"):
                self.file_system_cache[result.arguments["path"]] = result.result
                
        # Update last error if failed
        if result.status == ToolExecutionStatus.FAILED and result.error:
            self.last_error = result.error


# =====================================================
# WORKFLOW EXECUTION MODELS  
# =====================================================

@dataclass
class WorkflowExecutionContext:
    """Context for workflow execution"""
    workflow: WorkflowDefinition
    parameters: Dict[str, Any]
    start_time: datetime
    step_results: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    execution_log: List[str] = field(default_factory=list)
    
    def get_variables(self) -> Dict[str, Any]:
        """Get all available variables for template resolution"""
        variables = dict(self.parameters)
        variables.update(self.variables)
        variables.update(self.step_results)
        return variables
    
    def log(self, message: str):
        """Add message to execution log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.execution_log.append(f"[{timestamp}] {message}")


@dataclass
class WorkflowExecutionResult:
    """Result of workflow execution"""
    workflow_name: str
    success: bool
    execution_time: timedelta
    steps_executed: int
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    partial_outputs: Dict[str, Any] = field(default_factory=dict)
    execution_log: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class WorkflowSession:
    """Tracks a workflow recording/learning session"""
    name: str
    description: str
    start_time: datetime
    tool_executions: List[ToolExecutionResult] = field(default_factory=list)
    user_intent: Optional[str] = None
    is_recording: bool = True
    
    def add_tool_execution(self, result: ToolExecutionResult):
        """Add tool execution to session"""
        self.tool_executions.append(result)


@dataclass
class WorkflowPattern:
    """Detected workflow pattern"""
    name: str
    tools_sequence: List[str]
    frequency: int
    success_rate: float
    confidence_score: float
    example_executions: List[List[ToolExecutionResult]]
    suggested_parameters: List[WorkflowParameter]


@dataclass
class WorkflowCandidate:
    """Candidate for workflow creation"""
    name: str
    description: str
    tool_chain: List[ToolExecutionResult]
    confidence_score: float
    suggested_parameters: List[WorkflowParameter]
    estimated_reusability: float


class WorkflowExecutionError(Exception):
    """Exception raised during workflow execution"""
    pass


# =====================================================
# WORKFLOW LEARNING ENGINE
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
            
        # Check for subsequence match
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
            
        # Deduplicate and merge similar parameters
        return self._merge_parameters(parameters)
        
    def _analyze_tool_arguments(self, result: ToolExecutionResult) -> List[WorkflowParameter]:
        """Analyze tool arguments to identify parameterizable values"""
        parameters = []
        
        for arg_name, arg_value in result.arguments.items():
            # Identify URLs
            if isinstance(arg_value, str) and arg_value.startswith(('http://', 'https://')):
                parameters.append(WorkflowParameter(
                    name=f"{result.tool_name}_{arg_name}",
                    type="string",
                    description=f"URL for {result.tool_name}",
                    validation={"pattern": "^https?://.+"},
                    default=arg_value
                ))
                
            # Identify file paths
            elif isinstance(arg_value, str) and ('/' in arg_value or '\\' in arg_value):
                parameters.append(WorkflowParameter(
                    name=f"{result.tool_name}_{arg_name}",
                    type="string", 
                    description=f"File path for {result.tool_name}",
                    default=arg_value
                ))
                
            # Identify numeric values that might be configurable
            elif isinstance(arg_value, (int, float)) and arg_value > 0:
                parameters.append(WorkflowParameter(
                    name=f"{result.tool_name}_{arg_name}",
                    type="integer" if isinstance(arg_value, int) else "float",
                    description=f"Numeric parameter for {result.tool_name}",
                    validation={"min": 0},
                    default=arg_value
                ))
                
            # Identify text content that might be templatable
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
                # Keep the one with more specific validation
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
        
        # Group related tool chains
        tool_chains = self._group_tool_chains(execution_history)
        
        # Identify patterns
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
        # Criteria for workflow candidacy:
        # 1. Multiple related tools (min length)
        # 2. Clear input/output flow
        # 3. Repeatable pattern
        # 4. Parameterizable inputs
        
        if len(chain) < self.min_chain_length:
            return False
            
        # Check for known patterns
        matching_patterns = self.pattern_analyzer.analyze_chain_for_patterns(chain)
        
        if not matching_patterns:
            # Even without known patterns, consider chains with parameterizable inputs
            parameters = self.parameter_extractor.extract_parameters(chain)
            return len(parameters) >= 1
            
        return True
    
    async def _create_workflow_candidate(self, chain: List[ToolExecutionResult]) -> WorkflowCandidate:
        """Create workflow candidate from tool chain"""
        
        # Extract parameters
        suggested_parameters = self.parameter_extractor.extract_parameters(chain)
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(chain, suggested_parameters)
        
        # Generate candidate name
        tool_names = [r.tool_name for r in chain]
        name = f"workflow_{tool_names[0]}_to_{tool_names[-1]}"
        
        # Generate description
        description = f"Automated workflow: {' → '.join(tool_names[:3])}{'...' if len(tool_names) > 3 else ''}"
        
        return WorkflowCandidate(
            name=name,
            description=description,
            tool_chain=chain,
            confidence_score=confidence_score,
            suggested_parameters=suggested_parameters,
            estimated_reusability=confidence_score * 0.8  # Rough estimate
        )
    
    def _calculate_confidence_score(self, chain: List[ToolExecutionResult], 
                                  parameters: List[WorkflowParameter]) -> float:
        """Calculate confidence score for workflow candidacy"""
        base_score = 0.5
        
        # Boost for pattern recognition
        matching_patterns = self.pattern_analyzer.analyze_chain_for_patterns(chain)
        if matching_patterns:
            base_score += 0.2
            
        # Boost for parameterizability 
        if parameters:
            base_score += min(0.3, len(parameters) * 0.1)
            
        # Boost for chain length (up to reasonable limit)
        length_boost = min(0.2, (len(chain) - self.min_chain_length) * 0.05)
        base_score += length_boost
        
        # Penalty for failed steps in chain
        failed_count = sum(1 for r in chain if r.status == ToolExecutionStatus.FAILED)
        if failed_count > 0:
            base_score -= failed_count * 0.1
            
        return max(0.0, min(1.0, base_score))


# =====================================================
# WORKFLOW EXECUTION ENGINE
# =====================================================

class WorkflowValidator:
    """Validates workflow definitions and parameters"""
    
    def validate_workflow_definition(self, workflow: WorkflowDefinition) -> Tuple[bool, List[str]]:
        """Validate workflow definition for correctness"""
        errors = []
        
        # Check required fields
        if not workflow.name or not workflow.name.strip():
            errors.append("Workflow name is required")
            
        if not workflow.steps:
            errors.append("Workflow must have at least one step")
            
        # Validate step dependencies
        step_ids = {step.id for step in workflow.steps}
        for step in workflow.steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    errors.append(f"Step {step.id} depends on non-existent step {dep}")
                    
        # Check for circular dependencies
        if self._has_circular_dependencies(workflow.steps):
            errors.append("Circular dependencies detected in workflow steps")
            
        return len(errors) == 0, errors
    
    def validate_parameters(self, workflow: WorkflowDefinition, 
                          parameters: Dict[str, Any]) -> 'ValidationResult':
        """Validate provided parameters against workflow definition"""
        errors = []
        warnings = []
        
        # Check required parameters
        for param in workflow.parameters:
            if param.required and param.name not in parameters:
                if param.default is not None:
                    parameters[param.name] = param.default
                    warnings.append(f"Using default value for {param.name}: {param.default}")
                else:
                    errors.append(f"Required parameter {param.name} is missing")
            elif param.name in parameters:
                # Validate parameter value
                is_valid, error = param.validate(parameters[param.name])
                if not is_valid:
                    errors.append(f"Parameter {param.name}: {error}")
                    
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    def _has_circular_dependencies(self, steps: List[WorkflowStep]) -> bool:
        """Check for circular dependencies using DFS"""
        # Build dependency graph
        graph = {step.id: step.depends_on for step in steps}
        
        # Track visit states: 0=unvisited, 1=visiting, 2=visited
        states = {step_id: 0 for step_id in graph}
        
        def has_cycle(node_id: str) -> bool:
            if states[node_id] == 1:  # Currently visiting - cycle detected
                return True
            if states[node_id] == 2:  # Already visited
                return False
                
            states[node_id] = 1  # Mark as visiting
            
            for dep in graph.get(node_id, []):
                if dep in states and has_cycle(dep):
                    return True
                    
            states[node_id] = 2  # Mark as visited
            return False
        
        return any(has_cycle(step_id) for step_id in graph if states[step_id] == 0)


@dataclass
class ValidationResult:
    """Result of validation operation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


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
            # Simple condition evaluation
            # In a production system, you'd want a safer evaluator
            variables = context.get_variables()
            
            # Replace variables in condition
            for var_name, var_value in variables.items():
                condition = condition.replace(f"{{{{{var_name}}}}}", str(var_value))
                
            # Basic condition patterns
            if "==" in condition:
                left, right = condition.split("==", 1)
                return left.strip().strip('"') == right.strip().strip('"')
            elif "!=" in condition:
                left, right = condition.split("!=", 1)
                return left.strip().strip('"') != right.strip().strip('"')
            elif condition.lower() in ['true', 'false']:
                return condition.lower() == 'true'
                
            return True  # Default to true for unrecognized conditions
            
        except Exception as e:
            logger.warning(f"Error evaluating condition '{condition}': {e}")
            return True  # Default to true on error


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
        
        # Validate workflow definition
        is_valid, validation_errors = self.validator.validate_workflow_definition(workflow)
        if not is_valid:
            return WorkflowExecutionResult(
                workflow_name=workflow.name,
                success=False, 
                execution_time=datetime.now() - start_time,
                steps_executed=0,
                error=f"Workflow validation failed: {'; '.join(validation_errors)}"
            )
        
        # Validate parameters
        validation_result = self.validator.validate_parameters(workflow, parameters)
        if not validation_result.is_valid:
            return WorkflowExecutionResult(
                workflow_name=workflow.name,
                success=False,
                execution_time=datetime.now() - start_time,
                steps_executed=0,
                error=f"Parameter validation failed: {'; '.join(validation_result.errors)}"
            )
        
        # Create execution context
        context = WorkflowExecutionContext(
            workflow=workflow,
            parameters=parameters,
            start_time=start_time
        )
        
        context.log(f"Starting workflow execution: {workflow.name}")
        
        try:
            # Calculate execution order
            execution_order = self._calculate_execution_order(workflow.steps)
            
            # Execute steps
            executed_count = 0
            for step in execution_order:
                if await self._execute_step(step, context):
                    executed_count += 1
                else:
                    # Step failed or was skipped
                    if not workflow.error_handling.continue_on_error:
                        break
                        
            # Process outputs
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
        """Calculate step execution order based on dependencies using topological sort"""
        # Build dependency graph
        step_dict = {step.id: step for step in steps}
        in_degree = {step.id: 0 for step in steps}
        
        for step in steps:
            for dep in step.depends_on:
                if dep in in_degree:
                    in_degree[step.id] += 1
                    
        # Topological sort
        queue = deque([step_id for step_id, degree in in_degree.items() if degree == 0])
        result = []
        
        while queue:
            step_id = queue.popleft()
            step = step_dict[step_id]
            result.append(step)
            
            # Reduce in-degree for dependent steps
            for other_step in steps:
                if step_id in other_step.depends_on:
                    in_degree[other_step.id] -= 1
                    if in_degree[other_step.id] == 0:
                        queue.append(other_step.id)
                        
        return result
            
    async def _execute_step(self, step: WorkflowStep, context: WorkflowExecutionContext) -> bool:
        """Execute individual workflow step"""
        
        context.log(f"Executing step: {step.id} ({step.tool})")
        
        # Check dependencies
        if not self.state_manager.can_execute_step(step, context):
            error_msg = f"Dependencies not satisfied for step {step.id}"
            context.log(f"❌ {error_msg}")
            raise WorkflowExecutionError(error_msg)
            
        # Check conditional execution
        if step.conditional and not self.state_manager.evaluate_condition(step.conditional, context):
            context.log(f"⏭️  Skipping step {step.id} due to condition: {step.conditional}")
            return True  # Consider as successful skip
            
        # Resolve parameters with template substitution
        resolved_params = step.resolve_parameters(context.get_variables())
        context.log(f"Resolved parameters: {resolved_params}")
        
        # Execute with retry logic
        retry_policy = step.retry_policy or RetryPolicy()
        
        for attempt in range(retry_policy.max_attempts):
            try:
                context.log(f"Attempt {attempt + 1}/{retry_policy.max_attempts}")
                
                # Execute tool via MCP
                result = await self.mcp_session.call_tool(step.tool, resolved_params)
                
                # Validate result if validation defined
                if step.validation and not self._validate_step_result(step.validation, result):
                    raise WorkflowExecutionError(f"Step validation failed for {step.id}")
                    
                # Store result in context
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
            # Check success condition
            if validation.success_condition:
                # Simple validation - in production, use safer evaluator
                condition = validation.success_condition
                
                # Replace 'result' with actual result in condition
                if "result" in condition:
                    condition = condition.replace("result", str(result))
                    
                # Basic condition evaluation
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
                    
            return True  # No validation or validation passed
            
        except Exception as e:
            logger.warning(f"Error in step validation: {e}")
            return True  # Default to pass on validation error
    
    def _process_outputs(self, output_configs: List[WorkflowOutput], 
                        context: WorkflowExecutionContext) -> Dict[str, Any]:
        """Process workflow outputs from execution context"""
        outputs = {}
        
        for output_config in output_configs:
            try:
                if output_config.source == "workflow.execution_log":
                    outputs[output_config.name] = context.execution_log
                elif output_config.source.startswith("workflow."):
                    # Workflow-level properties
                    prop_name = output_config.source.split(".", 1)[1]
                    if prop_name == "execution_time":
                        outputs[output_config.name] = (datetime.now() - context.start_time).total_seconds()
                elif "." in output_config.source:
                    # Step result reference
                    step_id, result_path = output_config.source.split(".", 1)
                    if step_id in context.step_results:
                        result_data = context.step_results[step_id]
                        if result_path == "result":
                            outputs[output_config.name] = result_data
                        else:
                            # Navigate nested result
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
# WORKFLOW MANAGEMENT SYSTEM  
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
        
        # Also scan storage directory
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
        
        # Keep only recent history to prevent memory growth
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


# =====================================================
# WORKFLOW RECORDING MODE
# =====================================================

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
        
        # Clear current tool execution history to start fresh
        self.orchestrator.system_state.tool_execution_history.clear()
        
        logger.info(f"🎬 Started workflow recording: {session_name}")
        return f"🎬 Recording started: {session_name}. All subsequent tool executions will be captured for workflow creation."
        
    async def stop_recording_and_create_workflow(self, user_intent: str = "") -> Optional[WorkflowDefinition]:
        """Stop recording and attempt to create workflow"""
        if not self.recording_session:
            return None
            
        # Analyze recorded session
        candidates = await self.learning_engine.analyze_session_for_workflows()
        
        if not candidates:
            logger.info("No workflow patterns detected in recording session")
            self.recording_session = None
            return None
            
        # Use best candidate for workflow creation
        best_candidate = max(candidates, key=lambda c: c.confidence_score)
        
        # Create workflow definition  
        workflow = WorkflowDefinition.from_execution_history(
            best_candidate.tool_chain,
            user_intent or self.recording_session.description,
            self.recording_session.name
        )
        
        # Save workflow
        await self.workflow_library.save_workflow(workflow)
        
        # Clear recording session
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
            
        # Analyze recent tool execution history
        recent_history = self.orchestrator.system_state.tool_execution_history[-20:]
        
        if len(recent_history) < WORKFLOW_PATTERN_MIN_LENGTH:
            return []
            
        # Look for patterns in recent history
        candidates = await self.learning_engine.analyze_session_for_workflows()
        
        # Filter to high-confidence candidates
        high_confidence = [c for c in candidates if c.confidence_score > 0.7]
        
        return high_confidence


# =====================================================
# WORKFLOW CLI INTERFACE
# =====================================================

class WorkflowCLI:
    """Command-line interface for workflow operations"""
    
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.library = WorkflowLibrary()
        self.executor = WorkflowExecutor(orchestrator.mcp_session) if orchestrator.mcp_session else None
        self.recording_mode = WorkflowRecordingMode(orchestrator)
        
    async def process_workflow_command(self, command: str) -> str:
        """Process workflow management command"""
        command = command.strip()
        
        try:
            if command == "workflow help" or command == "workflow":
                return self._get_help_text()
            elif command == "workflow list":
                return await self._list_workflows()
            elif command.startswith("workflow run "):
                workflow_name = command[13:].strip()
                return await self._run_workflow_interactive(workflow_name)
            elif command.startswith("workflow show "):
                workflow_name = command[14:].strip()
                return await self._show_workflow(workflow_name)
            elif command.startswith("workflow delete "):
                workflow_name = command[16:].strip()
                return await self._delete_workflow(workflow_name)
            elif command.startswith("workflow search "):
                query = command[16:].strip()
                return await self._search_workflows(query)
            elif command == "workflow record start":
                return await self._start_recording_interactive()
            elif command == "workflow record stop":
                return await self._stop_recording_interactive()
            elif command == "workflow record status":
                return self._get_recording_status()
            elif command == "workflow stats":
                return await self._show_workflow_stats()
            elif command == "workflow suggest":
                return await self._suggest_workflows()
            else:
                return f"Unknown workflow command: {command}. Type 'workflow help' for available commands."
                
        except Exception as e:
            logger.error(f"Error processing workflow command: {e}")
            return f"❌ Error: {e}"
    
    def _get_help_text(self) -> str:
        """Get help text for workflow commands"""
        return """
🔧 Workflow Management System

Available Commands:
• workflow list                    - List all available workflows
• workflow run <name>              - Execute a workflow interactively
• workflow show <name>             - Show workflow definition
• workflow delete <name>           - Delete a workflow
• workflow search <query>          - Search workflows by name/description
• workflow record start           - Start recording for workflow creation
• workflow record stop            - Stop recording and create workflow
• workflow record status          - Check recording status
• workflow stats                  - Show workflow execution statistics
• workflow suggest                - Get workflow suggestions based on activity
• workflow help                   - Show this help message

Examples:
  workflow run web_data_extraction
  workflow search "web scraping"
  workflow record start
        """
    
    async def _list_workflows(self) -> str:
        """List available workflows"""
        workflows = await self.library.list_workflows()
        
        if not workflows:
            return "📝 No workflows available. Start recording to create your first workflow!"
            
        result = "📋 Available Workflows:\n\n"
        
        for name in workflows:
            try:
                workflow = await self.library.load_workflow(name)
                if workflow:
                    stats = await self.library.get_workflow_stats(name)
                    result += f"• {name}\n"
                    result += f"  Description: {workflow.description}\n"
                    result += f"  Steps: {len(workflow.steps)}, Parameters: {len(workflow.parameters)}\n"
                    if stats["executions"] > 0:
                        result += f"  Executions: {stats['executions']}, Success Rate: {stats['success_rate']:.1%}\n"
                    result += "\n"
            except Exception as e:
                result += f"• {name} (Error loading: {e})\n"
                
        return result.strip()
    
    async def _run_workflow_interactive(self, workflow_name: str) -> str:
        """Run workflow with interactive parameter input"""
        if not self.executor:
            return "❌ Workflow executor not available (MCP session not connected)"
            
        workflow = await self.library.load_workflow(workflow_name)
        if not workflow:
            return f"❌ Workflow '{workflow_name}' not found"
            
        try:
            # For now, use default values for all parameters
            # In a full interactive mode, you'd prompt for each parameter
            parameters = {}
            for param in workflow.parameters:
                if param.default is not None:
                    parameters[param.name] = param.default
                else:
                    # Use reasonable defaults based on type
                    if param.type == "string":
                        parameters[param.name] = ""
                    elif param.type == "integer":
                        parameters[param.name] = 0
                    elif param.type == "float":
                        parameters[param.name] = 0.0
                    elif param.type == "boolean":
                        parameters[param.name] = False
                    elif param.type == "array":
                        parameters[param.name] = []
                    elif param.type == "object":
                        parameters[param.name] = {}
                        
            # Execute workflow
            result = await self.executor.execute_workflow(workflow, parameters)
            
            # Record execution
            self.library.record_execution(result)
            
            if result.success:
                output = f"✅ Workflow '{workflow_name}' completed successfully in {result.execution_time.total_seconds():.1f}s\n\n"
                output += f"Steps executed: {result.steps_executed}/{len(workflow.steps)}\n"
                
                if result.outputs:
                    output += "\n📤 Outputs:\n"
                    for name, value in result.outputs.items():
                        if isinstance(value, list) and len(value) > 5:
                            output += f"• {name}: {len(value)} items\n"
                        else:
                            output += f"• {name}: {value}\n"
                            
                return output
            else:
                return f"❌ Workflow '{workflow_name}' failed: {result.error}"
                
        except Exception as e:
            return f"❌ Error executing workflow: {e}"
    
    async def _show_workflow(self, workflow_name: str) -> str:
        """Show workflow definition details"""
        workflow = await self.library.load_workflow(workflow_name)
        if not workflow:
            return f"❌ Workflow '{workflow_name}' not found"
            
        output = f"📋 Workflow: {workflow.name}\n"
        output += f"Version: {workflow.version}\n"
        output += f"Description: {workflow.description}\n"
        output += f"Author: {workflow.author}\n"
        output += f"Created: {workflow.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        if workflow.parameters:
            output += "📥 Parameters:\n"
            for param in workflow.parameters:
                output += f"• {param.name} ({param.type})"
                if param.required:
                    output += " *required*"
                if param.default is not None:
                    output += f" = {param.default}"
                output += f"\n  {param.description}\n"
            output += "\n"
            
        output += f"🔄 Steps ({len(workflow.steps)}):\n"
        for i, step in enumerate(workflow.steps, 1):
            output += f"{i}. {step.id} - {step.tool}\n"
            output += f"   {step.description}\n"
            if step.depends_on:
                output += f"   Depends on: {', '.join(step.depends_on)}\n"
        
        return output
    
    async def _delete_workflow(self, workflow_name: str) -> str:
        """Delete a workflow"""
        success = await self.library.delete_workflow(workflow_name)
        if success:
            return f"✅ Deleted workflow: {workflow_name}"
        else:
            return f"❌ Failed to delete workflow: {workflow_name}"
    
    async def _search_workflows(self, query: str) -> str:
        """Search workflows by query"""
        workflows = await self.library.search_workflows(query)
        
        if not workflows:
            return f"🔍 No workflows found matching '{query}'"
            
        output = f"🔍 Found {len(workflows)} workflows matching '{query}':\n\n"
        for workflow in workflows:
            output += f"• {workflow.name}\n"
            output += f"  {workflow.description}\n\n"
            
        return output.strip()
    
    async def _start_recording_interactive(self) -> str:
        """Start workflow recording interactively"""
        if self.recording_mode.is_recording():
            return "⚠️  Already recording a workflow session"
            
        session_name = f"session_{int(time.time())}"
        return await self.recording_mode.start_recording(session_name, "Interactive recording session")
    
    async def _stop_recording_interactive(self) -> str:
        """Stop workflow recording and create workflow"""
        if not self.recording_mode.is_recording():
            return "⚠️  No recording session active"
            
        workflow = await self.recording_mode.stop_recording_and_create_workflow("User-requested workflow")
        
        if workflow:
            return f"✅ Created workflow: {workflow.name} with {len(workflow.steps)} steps"
        else:
            return "❌ No workflow patterns detected in recording session"
    
    def _get_recording_status(self) -> str:
        """Get current recording status"""
        if self.recording_mode.is_recording():
            session = self.recording_mode.recording_session
            duration = datetime.now() - session.start_time
            tool_count = len(self.orchestrator.system_state.tool_execution_history)
            
            return f"🎬 Recording active: {session.name}\n" \
                   f"Duration: {duration.total_seconds():.0f}s\n" \
                   f"Tools executed: {tool_count}"
        else:
            return "⏹️  No recording session active"
    
    async def _show_workflow_stats(self) -> str:
        """Show workflow execution statistics"""
        workflows = await self.library.list_workflows()
        
        if not workflows:
            return "📊 No workflows available"
            
        output = "📊 Workflow Statistics:\n\n"
        
        for name in workflows:
            stats = await self.library.get_workflow_stats(name)
            if stats["executions"] > 0:
                output += f"• {name}\n"
                output += f"  Executions: {stats['executions']}\n"
                output += f"  Success Rate: {stats['success_rate']:.1%}\n"
                output += f"  Avg Duration: {stats['avg_duration']:.1f}s\n"
                output += f"  Last Run: {stats.get('last_execution', 'Never')}\n\n"
                
        return output.strip() or "📊 No execution statistics available"
    
    async def _suggest_workflows(self) -> str:
        """Get workflow suggestions"""
        candidates = await self.recording_mode.auto_suggest_workflows()
        
        if not candidates:
            return "💡 No workflow suggestions available based on recent activity"
            
        output = "💡 Workflow Suggestions:\n\n"
        
        for candidate in candidates:
            output += f"• {candidate.name}\n"
            output += f"  Description: {candidate.description}\n"
            output += f"  Confidence: {candidate.confidence_score:.1%}\n"
            output += f"  Tools: {' → '.join([r.tool_name for r in candidate.tool_chain[:3]])}\n"
            if len(candidate.tool_chain) > 3:
                output += "...\n"
            output += "\n"
            
        output += "To create a workflow from these patterns, use 'workflow record start/stop'"
        
        return output


# =====================================================
# ENHANCED SYSTEM COMPONENTS (from original orchestrator)
# =====================================================

class SystemMessageBuilder:
    """Builds comprehensive, context-aware system messages"""
    
    def __init__(self, available_tools: List[Tool], state: SystemState):
        self.available_tools = available_tools
        self.state = state
        
    def build_comprehensive_system_message(self) -> str:
        """Build enhanced system message with context and guidelines"""
        
        base_personality = """You are Jovera Browser, an advanced personal browser assistant with sophisticated tool execution capabilities and workflow automation. You have been granted full permission to access and control the user's browser and computer system.

Your core capabilities include:
- Intelligent web browsing and interaction
- Advanced error handling and recovery  
- Progressive problem-solving with context awareness
- Proactive assistance and suggestion generation
- Multi-step operation coordination
- Workflow learning and automation"""

        tool_guidelines = self._build_tool_usage_guidelines()
        execution_patterns = self._build_execution_patterns() 
        context_awareness = self._build_context_awareness()
        error_handling = self._build_error_handling_guidelines()
        workflow_features = self._build_workflow_guidelines()
        gemini_optimizations = self._build_gemini_optimizations()
        
        system_message = f"""{base_personality}

{tool_guidelines}

{execution_patterns}

{context_awareness}

{error_handling}

{workflow_features}

{gemini_optimizations}

Remember: You are operating as the user's authorized personal assistant. Be proactive, intelligent, and thorough in your assistance."""
        
        return system_message
    
    def _build_tool_usage_guidelines(self) -> str:
        """Build tool-specific usage guidelines"""
        tool_names = [tool.name for tool in self.available_tools]
        
        guidelines = f"""
TOOL USAGE GUIDELINES:

Available Tools: {', '.join(tool_names)}

Core Principles:
1. SEQUENTIAL EXECUTION: Execute tools one at a time unless explicitly parallel
2. EXPLAIN FIRST: Always explain your reasoning before calling tools  
3. VALIDATE INPUTS: Verify parameters make sense before execution
4. HANDLE ERRORS: If a tool fails, explain why and try alternatives
5. SHOW PROGRESS: Keep the user informed of your progress
6. CHAIN LOGICALLY: When tools have dependencies, execute in proper order

Tool Chaining Patterns:
- Navigation → Screenshot → Interactive Elements (for web tasks)
- List Directory → Read File (for file exploration)  
- Take Screenshot → Get Interactive Elements (for UI analysis)
- Validate → Execute → Verify (for critical operations)"""

        return guidelines
    
    def _build_execution_patterns(self) -> str:
        """Build execution pattern guidelines"""
        return """
EXECUTION PATTERNS:

Before Tool Execution:
- State your intention and plan
- Validate prerequisites are met
- Check current state for context

During Tool Execution:  
- Monitor for errors or unexpected results
- Adapt strategy based on intermediate results
- Maintain awareness of state changes

After Tool Execution:
- Verify results meet expectations
- Update understanding of current state
- Plan next steps based on new information

Multi-Step Operations:
- Break complex tasks into logical steps
- Execute steps sequentially with validation
- Provide progress updates between steps
- Handle failures gracefully with recovery"""
    
    def _build_context_awareness(self) -> str:
        """Build context awareness guidelines"""
        current_context = []
        
        if self.state.current_directory:
            current_context.append(f"Current directory: {self.state.current_directory}")
            
        if self.state.browser_state.get("current_url"):
            current_context.append(f"Current URL: {self.state.browser_state['current_url']}")
            
        if self.state.last_error:
            current_context.append(f"Last error: {self.state.last_error}")
            
        recent_tools = [r.tool_name for r in self.state.tool_execution_history[-5:]]
        if recent_tools:
            current_context.append(f"Recent tools: {' → '.join(recent_tools)}")
            
        context_info = '\n'.join(f"- {ctx}" for ctx in current_context) if current_context else "- No specific context available"
        
        return f"""
CONTEXT AWARENESS:

Current Session Context:
{context_info}

State Management:
- Track file system changes and browser navigation
- Remember previous tool results for context
- Maintain awareness of user goals and progress
- Use historical context to inform decisions

Context Usage:
- Reference previous results when relevant  
- Avoid repeating unnecessary operations
- Build upon established context
- Provide continuity across interactions"""
    
    def _build_error_handling_guidelines(self) -> str:
        """Build error handling and recovery guidelines"""
        return """
ERROR HANDLING & RECOVERY:

Error Response Protocol:
1. ACKNOWLEDGE: Clearly state what went wrong
2. ANALYZE: Explain the likely cause of the error
3. ADAPT: Propose alternative approaches
4. EXECUTE: Try recovery strategies
5. ESCALATE: If all else fails, ask for user guidance

Recovery Strategies:
- Retry with modified parameters
- Use alternative tools for same goal
- Break down complex operations into simpler steps
- Verify prerequisites before retry attempts
- Provide fallback options to user

Error Classifications:
- Transient (network, timeout) → Retry automatically
- Parameter (invalid input) → Fix and retry  
- State (prerequisite not met) → Address prerequisite
- Critical (system failure) → Escalate to user"""
    
    def _build_workflow_guidelines(self) -> str:
        """Build workflow automation guidelines"""
        return """
WORKFLOW AUTOMATION FEATURES:

Pattern Recognition:
- Automatically detect repeatable tool sequences
- Learn from successful interaction patterns
- Suggest workflow creation for common tasks
- Build reusable automation templates

Workflow Commands:
- "workflow list" - Show available workflows
- "workflow run <name>" - Execute saved workflow  
- "workflow record start/stop" - Capture new workflows
- "workflow suggest" - Get workflow recommendations

Learning Mode:
- All tool executions are analyzed for patterns
- Successful sequences become workflow candidates
- Parameters are automatically extracted and templated
- Workflows can be saved and reused without LLM intervention

Proactive Suggestions:
- Suggest workflows when patterns are detected
- Recommend automation for repetitive tasks
- Offer to save successful tool sequences
- Help optimize and improve existing workflows"""
    
    def _build_gemini_optimizations(self) -> str:
        """Build Gemini-specific optimization guidelines"""
        return """
GEMINI OPTIMIZATION PATTERNS:

Thinking Process:
- Use step-by-step reasoning for complex tasks
- Explain your decision-making process clearly
- Consider multiple approaches before choosing
- Validate assumptions before proceeding

Tool Call Structure:
- One primary tool per response when possible
- Group related tools logically when parallel execution makes sense
- Provide clear rationale for tool selection
- Include error handling in your planning

Response Quality:
- Be specific and actionable in your explanations
- Provide context for why you're taking certain actions
- Offer alternatives when appropriate
- Synthesize results into coherent narrative

Workflow Integration:
- Recognize when tasks could be automated
- Suggest workflow creation for valuable patterns
- Use workflows when appropriate instead of manual execution
- Learn from each interaction to improve future performance"""


class ToolValidator:
    """Validates tool calls before execution"""
    
    def __init__(self, state: SystemState):
        self.state = state
        
    def validate_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate a tool call before execution"""
        
        if not ENABLE_TOOL_VALIDATION:
            return True, None
            
        try:
            if tool_name == "read_file":
                return self._validate_read_file(arguments)
            elif tool_name == "navigate":
                return self._validate_navigate(arguments)
            elif tool_name == "click_element_by_index":
                return self._validate_click_element_by_index(arguments)
            
            return True, None  # No specific validation for other tools
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def _validate_read_file(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate read_file tool call"""
        file_path = args.get("path") or args.get("filePath")
        
        if not file_path:
            return False, "File path is required"
            
        # Check if file exists in our cache or suggest alternatives
        if not os.path.exists(file_path) and file_path not in self.state.file_system_cache:
            # Try to suggest similar files
            dir_name = os.path.dirname(file_path)
            if os.path.exists(dir_name):
                similar_files = [f for f in os.listdir(dir_name) 
                               if f.lower().startswith(os.path.basename(file_path).lower()[:3])]
                if similar_files:
                    return False, f"File not found. Similar files: {', '.join(similar_files[:3])}"
            return False, f"File not found: {file_path}"
            
        return True, None
        
    def _validate_navigate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate navigate tool call"""
        url = args.get("url")
        
        if not url:
            return False, "URL is required"
            
        # Basic URL validation
        if not (url.startswith("http://") or url.startswith("https://") or url.startswith("file://")):
            if not url.startswith("www."):
                return False, "URL must start with http://, https://, file://, or www."
            args["url"] = f"https://{url}"  # Auto-fix www URLs
                
        return True, None
        
    def _validate_click_element_by_index(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate click element by index"""
        element_index = args.get("element_index")
        
        if element_index is None:
            return False, "Element index is required"
            
        if not isinstance(element_index, int) or element_index < 0:
            return False, "Element index must be a non-negative integer"
            
        return True, None


class ErrorRecoveryEngine:
    """Handles error analysis and recovery strategies"""
    
    def __init__(self, state: SystemState):
        self.state = state
        
    def analyze_error(self, tool_name: str, error: str, context: Dict[str, Any]) -> Tuple[ErrorSeverity, List[str]]:
        """Analyze error and generate recovery suggestions"""
        
        error_lower = error.lower()
        suggestions = []
        
        # Classify error severity
        if any(keyword in error_lower for keyword in ["timeout", "network", "connection"]):
            severity = ErrorSeverity.RECOVERABLE
            suggestions.extend([
                "Retry the operation after a brief delay",
                "Check network connectivity", 
                "Try with increased timeout"
            ])
            
        elif any(keyword in error_lower for keyword in ["not found", "file not found", "404"]):
            severity = ErrorSeverity.WARNING
            suggestions.extend([
                "Verify the path or URL is correct",
                "Check if the resource exists",
                "Try listing the parent directory"
            ])
            
        elif any(keyword in error_lower for keyword in ["permission", "access denied", "forbidden"]):
            severity = ErrorSeverity.CRITICAL
            suggestions.extend([
                "Check file/directory permissions",
                "Try running with elevated privileges",
                "Verify authentication credentials"
            ])
            
        elif any(keyword in error_lower for keyword in ["syntax", "invalid", "malformed"]):
            severity = ErrorSeverity.WARNING
            suggestions.extend([
                "Check parameter format and syntax",
                "Validate input data structure",
                "Review parameter documentation"
            ])
            
        else:
            severity = ErrorSeverity.RECOVERABLE
            suggestions.extend([
                "Retry the operation",
                "Check system resources",
                "Verify prerequisites are met"
            ])
            
        # Tool-specific recovery suggestions
        tool_suggestions = self._get_tool_specific_suggestions(tool_name, error_lower)
        suggestions.extend(tool_suggestions)
        
        return severity, suggestions
        
    def _get_tool_specific_suggestions(self, tool_name: str, error_lower: str) -> List[str]:
        """Get tool-specific recovery suggestions"""
        suggestions = []
        
        if tool_name == "navigate":
            suggestions.extend([
                "Verify URL format and accessibility",
                "Check if website is online"
            ])
                
        elif tool_name == "click_element_by_index":
            suggestions.extend([
                "Refresh interactive elements map",
                "Verify element index is within range"
            ])
                
        elif tool_name == "read_file":
            suggestions.extend([
                "Check file path and permissions",
                "Verify file exists and is readable"
            ])
                
        return suggestions


class ContextManager:
    """Manages conversation context with intelligent optimization"""
    
    def __init__(self, max_tokens: int = MAX_CONTEXT_TOKENS):
        self.max_tokens = max_tokens
        self.token_estimate_ratio = 4  # Rough chars per token estimate
        
    def optimize_context(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Optimize context to fit within token limits while preserving critical information"""
        
        # Estimate current token usage
        estimated_tokens = self._estimate_tokens(messages)
        
        if estimated_tokens <= self.max_tokens:
            return messages
            
        logger.info(f"Context optimization needed: {estimated_tokens} > {self.max_tokens} tokens")
        
        # Preserve critical messages
        optimized = []
        
        # Always keep system message
        system_msg = next((msg for msg in messages if msg.get("role") == "system"), None)
        if system_msg:
            optimized.append(system_msg)
            
        # Keep recent user input and assistant responses (last 3 exchanges)
        recent_messages = messages[-6:]  # Last 3 user-assistant pairs
        
        # Compress or summarize older tool chains
        older_messages = messages[1:-6] if len(messages) > 7 else []
        
        if older_messages:
            summarized = self._summarize_tool_chains(older_messages)
            optimized.extend(summarized)
            
        # Add recent messages
        optimized.extend(recent_messages)
        
        # Final token check
        final_tokens = self._estimate_tokens(optimized)
        logger.info(f"Context optimized: {estimated_tokens} → {final_tokens} tokens")
        
        return optimized
        
    def _estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Rough token estimation"""
        total_chars = 0
        for msg in messages:
            total_chars += len(str(msg.get("content", "")))
        return total_chars // self.token_estimate_ratio
        
    def _summarize_tool_chains(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Summarize tool execution chains to preserve key outcomes"""
        
        # Group messages into tool chains (assistant + tool results)
        chains = []
        current_chain = []
        
        for msg in messages:
            if msg.get("role") == "assistant":
                if current_chain:
                    chains.append(current_chain)
                current_chain = [msg]
            elif msg.get("role") == "tool":
                current_chain.append(msg)
                
        if current_chain:
            chains.append(current_chain)
            
        # Summarize each chain
        summarized = []
        for chain in chains:
            summary = self._create_chain_summary(chain)
            summarized.append(summary)
            
        return summarized
        
    def _create_chain_summary(self, chain: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a summary of a tool execution chain"""
        
        if not chain:
            return {"role": "assistant", "content": "[Empty chain]"}
            
        assistant_msg = chain[0] if chain[0].get("role") == "assistant" else None
        tool_results = [msg for msg in chain if msg.get("role") == "tool"]
        
        # Extract key information
        tools_used = []
        successful_tools = []
        failed_tools = []
        
        for tool_msg in tool_results:
            tool_name = tool_msg.get("name", "unknown")
            tools_used.append(tool_name)
            
            if tool_msg.get("content", {}).get("isError", False):
                failed_tools.append(tool_name)
            else:
                successful_tools.append(tool_name)
                
        # Create summary
        summary_parts = []
        if tools_used:
            summary_parts.append(f"Used tools: {', '.join(tools_used)}")
        if successful_tools:
            summary_parts.append(f"Success: {', '.join(successful_tools)}")
        if failed_tools:
            summary_parts.append(f"Failed: {', '.join(failed_tools)}")
            
        summary_content = f"[Tool chain summary: {'; '.join(summary_parts)}]"
        
        return {"role": "assistant", "content": summary_content}


class ToolChainOrchestrator:
    """Orchestrates sequential tool execution with intelligent chaining"""
    
    def __init__(self, mcp_session: ClientSession, state: SystemState):
        self.mcp_session = mcp_session
        self.state = state
        self.validator = ToolValidator(state)
        self.recovery_engine = ErrorRecoveryEngine(state)
        
    async def execute_tool_chain_sequentially(self, tool_calls: List[Dict[str, Any]]) -> List[ToolExecutionResult]:
        """Execute tool calls sequentially with error handling and recovery"""
        
        results = []
        
        for i, tool_call in enumerate(tool_calls):
            logger.info(f"Executing tool {i+1}/{len(tool_calls)}: {tool_call['function']['name']}")
            
            result = await self._execute_single_tool_with_recovery(tool_call)
            results.append(result)
            
            # Update system state
            self.state.update_from_tool_result(result)
            
            # If critical failure and not configured to continue, stop execution
            if result.status == ToolExecutionStatus.FAILED and not ENABLE_ERROR_RECOVERY:
                logger.warning(f"Tool execution failed, stopping chain: {result.error}")
                break
                    
        return results
        
    async def _execute_single_tool_with_recovery(self, tool_call: Dict[str, Any]) -> ToolExecutionResult:
        """Execute a single tool with validation, retry, and recovery"""
        
        tool_name = tool_call["function"]["name"]
        arguments = tool_call["function"]["arguments"]
        
        result = ToolExecutionResult(
            tool_name=tool_name,
            arguments=arguments,
            status=ToolExecutionStatus.PENDING
        )
        
        # Validation phase
        result.status = ToolExecutionStatus.VALIDATING
        is_valid, validation_error = self.validator.validate_tool_call(tool_name, arguments)
        
        if not is_valid:
            result.status = ToolExecutionStatus.FAILED
            result.error = f"Validation failed: {validation_error}"
            return result
            
        # Execution phase with retry logic
        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                result.status = ToolExecutionStatus.EXECUTING
                start_time = time.time()
                
                # Execute via MCP
                mcp_result = await asyncio.wait_for(
                    self.mcp_session.call_tool(tool_name, arguments),
                    timeout=TOOL_EXECUTION_TIMEOUT
                )
                
                # Process result
                processed_result = self._process_mcp_result(mcp_result)
                
                result.result = processed_result
                result.status = ToolExecutionStatus.COMPLETED
                result.execution_time = time.time() - start_time
                result.retry_count = attempt
                
                logger.info(f"✅ Tool {tool_name} executed successfully")
                return result
                
            except asyncio.TimeoutError:
                error_msg = f"Tool {tool_name} timed out after {TOOL_EXECUTION_TIMEOUT}s"
                result.error = error_msg
                logger.warning(f"⏰ {error_msg}")
                
            except Exception as e:
                error_msg = f"Tool {tool_name} failed: {str(e)}"
                result.error = error_msg
                logger.warning(f"❌ {error_msg}")
                
                # Analyze error and get recovery suggestions
                if ENABLE_ERROR_RECOVERY:
                    severity, suggestions = self.recovery_engine.analyze_error(
                        tool_name, str(e), {"attempt": attempt, "arguments": arguments}
                    )
                    
                    if severity in [ErrorSeverity.RECOVERABLE, ErrorSeverity.WARNING] and attempt < MAX_RETRY_ATTEMPTS - 1:
                        logger.info(f"🔄 Retrying {tool_name} (attempt {attempt + 2}/{MAX_RETRY_ATTEMPTS})")
                        await asyncio.sleep(min(2 ** attempt, 10))  # Exponential backoff
                        continue
                        
            # If we get here, all retries exhausted
            result.status = ToolExecutionStatus.FAILED
            result.retry_count = attempt + 1
            break
                
        return result
        
    def _process_mcp_result(self, mcp_result) -> Dict[str, Any]:
        """Process raw MCP result into standardized format"""
        
        try:
            if hasattr(mcp_result, 'content'):
                if isinstance(mcp_result.content, list) and mcp_result.content:
                    content = mcp_result.content[0]
                    if hasattr(content, 'text'):
                        try:
                            return json.loads(content.text)
                        except json.JSONDecodeError:
                            return {"text": content.text}
                    else:
                        return {"content": str(content)}
                else:
                    return {"content": str(mcp_result.content)}
            else:
                return {"result": str(mcp_result)}
                
        except Exception as e:
            logger.warning(f"Error processing MCP result: {e}")
            return {"error": f"Failed to process result: {str(e)}"}


class StreamingResponseManager:
    """Manages streaming responses with progress updates"""
    
    def __init__(self):
        self.enable_streaming = ENABLE_STREAMING
        
    async def stream_tool_execution(self, tool_calls: List[Dict[str, Any]], executor_func) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream tool execution progress"""
        
        if not self.enable_streaming:
            # Non-streaming mode - execute all and return
            results = await executor_func(tool_calls)
            yield {"type": "completion", "results": results}
            return
            
        # Streaming mode - provide progress updates
        yield {"type": "planning", "content": f"Planning to execute {len(tool_calls)} tool(s)..."}
        
        for i, tool_call in enumerate(tool_calls):
            tool_name = tool_call["function"]["name"]
            
            yield {
                "type": "tool_start", 
                "content": f"Executing {tool_name} ({i+1}/{len(tool_calls)})...",
                "tool_name": tool_name,
                "progress": i / len(tool_calls)
            }
            
            # Execute single tool
            result = await executor_func([tool_call])
            
            yield {
                "type": "tool_complete",
                "content": f"Completed {tool_name}",
                "result": result[0] if result else None,
                "progress": (i + 1) / len(tool_calls)
            }
            
        yield {"type": "synthesis", "content": "Synthesizing results..."}


# =====================================================
# WORKFLOW-ENHANCED CONVERSATIONAL ORCHESTRATOR
# =====================================================

class WorkflowEnhancedConversationalOrchestrator:
    """
    Workflow-Enhanced Conversational Orchestrator with automation capabilities.
    
    Maintains all Enhanced Conversational Orchestrator features while adding:
    - Workflow capture, parameterization, and replay functionality  
    - Pattern recognition and learning from successful interactions
    - Deterministic workflow execution without LLM intervention
    - Comprehensive workflow management and CLI interface
    """
    
    def __init__(self):
        # Core components
        self.messages = []
        self.mcp_session = None
        self.exit_stack = AsyncExitStack()
        self.genai_client = None
        self.available_tools = []
        
        # Enhanced components
        self.system_state = SystemState()
        self.context_manager = ContextManager()
        self.streaming_manager = StreamingResponseManager()
        
        # Workflow components
        self.workflow_recording = None
        self.workflow_cli = None
        
        # Will be initialized after MCP connection
        self.tool_orchestrator = None
        self.system_message_builder = None
        
        # Internal state
        self._conversation_id = f"conv_{int(time.time())}"
        self._tool_call_count = 0
        
    async def initialize(self):
        """Initialize all components including workflow features"""
        logger.info("🚀 Initializing Workflow-Enhanced Conversational Orchestrator...")
        
        # Initialize Gemini client
        if GEMINI_API_KEY:
            self.genai_client = genai.Client(api_key=GEMINI_API_KEY)
            logger.info("✅ Gemini client initialized")
        else:
            logger.error("❌ GEMINI_API_KEY not found in environment variables")
            raise ValueError("GEMINI_API_KEY is required")
        
        # Connect to MCP server
        await self._connect_to_mcp_server()
        
        # Load available tools
        await self._load_mcp_tools()
        
        # Initialize enhanced components that require tools/session
        self.tool_orchestrator = ToolChainOrchestrator(self.mcp_session, self.system_state)
        self.system_message_builder = SystemMessageBuilder(self.available_tools, self.system_state)
        
        # Initialize workflow components
        self.workflow_recording = WorkflowRecordingMode(self)
        self.workflow_cli = WorkflowCLI(self)
        
        # Build and set initial system message
        system_content = self.system_message_builder.build_comprehensive_system_message()
        self.messages = [{"role": "system", "content": system_content}]
        
        logger.info(f"✅ Workflow-enhanced orchestrator initialized with {len(self.available_tools)} tools")
        logger.info("🎯 Features enabled: " + 
                   f"Streaming={ENABLE_STREAMING}, " +
                   f"Validation={ENABLE_TOOL_VALIDATION}, " +  
                   f"Recovery={ENABLE_ERROR_RECOVERY}, " +
                   f"Workflows={ENABLE_WORKFLOW_LEARNING}")
        
    async def _connect_to_mcp_server(self):
        """Connect to MCP server using configured transport"""
        transport_type = MCP_TRANSPORT.lower()
        
        # Auto-detect transport type  
        if transport_type == "auto":
            if MCP_SERVER_URL and ("http://" in MCP_SERVER_URL or "https://" in MCP_SERVER_URL):
                transport_type = "http"
            elif MCP_SERVER_COMMAND:
                transport_type = "stdio"
            else:
                raise ValueError("Cannot auto-detect transport type. Set MCP_TRANSPORT explicitly.")
        
        # Connect using stdio transport
        if transport_type == "stdio" and MCP_SERVER_COMMAND:
            await self._connect_stdio_transport()
        # Connect using HTTP transport
        elif transport_type == "http" and MCP_SERVER_URL:
            await self._connect_http_transport()
        else:
            raise ValueError(f"Invalid transport configuration. Transport: {transport_type}, URL: {MCP_SERVER_URL}, Command: {MCP_SERVER_COMMAND}")
            
    async def _connect_stdio_transport(self):
        """Connect using stdio transport"""
        import shlex
        
        if isinstance(MCP_SERVER_COMMAND, str):
            cmd_parts = shlex.split(MCP_SERVER_COMMAND)
        else:
            cmd_parts = MCP_SERVER_COMMAND
            
        command = cmd_parts[0] if cmd_parts else "python"
        args = cmd_parts[1:] if len(cmd_parts) > 1 else []
        
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        
        self.mcp_session = await self.exit_stack.enter_async_context(
            ClientSession(stdio_transport[0], stdio_transport[1])
        )
        
        await self.mcp_session.initialize()
        logger.info(f"✅ Connected to MCP server via stdio: {MCP_SERVER_COMMAND}")
        
    async def _connect_http_transport(self):
        """Connect using HTTP transport"""
        http_transport = await self.exit_stack.enter_async_context(
            streamablehttp_client(MCP_SERVER_URL)
        )
        
        self.mcp_session = await self.exit_stack.enter_async_context(
            ClientSession(http_transport[0], http_transport[1])
        )
        
        await self.mcp_session.initialize()
        logger.info(f"✅ Connected to MCP server via HTTP: {MCP_SERVER_URL}")
        
    async def _load_mcp_tools(self):
        """Load available tools from MCP server"""
        try:
            tools_result = await self.mcp_session.list_tools()
            self.available_tools = tools_result.tools
            
            tool_names = [tool.name for tool in self.available_tools]
            logger.info(f"📊 Loaded {len(self.available_tools)} tools: {', '.join(tool_names)}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load MCP tools: {e}")
            raise
    
    async def _get_enhanced_context(self, user_input: str) -> Optional[str]:
        """Get enhanced context information including visual and interactive context"""
        context_parts = []
        
        try:
            # Check if this is a workflow command
            if user_input.strip().startswith("workflow"):
                return None  # Workflow commands don't need visual context
                
            # Get visual context if enabled and likely needed
            if ENABLE_VISUAL_CONTEXT and any(keyword in user_input.lower() 
                                           for keyword in ["see", "show", "what", "screenshot", "page", "website", "click", "element"]):
                try:
                    # Try to get screenshot first
                    screenshot_result = await self.mcp_session.call_tool("take_screenshot", {})
                    if screenshot_result and hasattr(screenshot_result, 'content'):
                        context_parts.append("📸 Current page screenshot captured")
                        
                        # Also get interactive elements if enabled
                        if ENABLE_INTERACTIVE_CONTEXT:
                            try:
                                elements_result = await self.mcp_session.call_tool("get_interactive_elements", {})
                                if elements_result and hasattr(elements_result, 'content'):
                                    context_parts.append("🎯 Interactive elements mapped")
                            except Exception as e:
                                logger.debug(f"Could not get interactive elements: {e}")
                                
                except Exception as e:
                    logger.debug(f"Could not get screenshot: {e}")
                    context_parts.append("📋 Visual context requested but screenshot unavailable")
                    
            # Add browser state context if available
            if self.system_state.browser_state.get("current_url"):
                context_parts.append(f"🌐 Current page: {self.system_state.browser_state['current_url']}")
                
            # Add file system context if relevant
            if any(keyword in user_input.lower() for keyword in ["file", "directory", "folder", "read", "write"]):
                if self.system_state.current_directory:
                    context_parts.append(f"📁 Working directory: {self.system_state.current_directory}")
                    
        except Exception as e:
            logger.warning(f"Error getting enhanced context: {e}")
            
        return "\n".join(context_parts) if context_parts else None
            
    async def _get_context_with_fallback(self, user_input) -> tuple[Optional[str], str]:
        """Get context with fallback handling"""
        context = await self._get_enhanced_context(user_input)
        context_desc = "Enhanced context available" if context else "No additional context needed"
        return context, context_desc
        
    def _convert_tools_to_gemini_format(self) -> List[types.Tool]:
        """Convert MCP tools to Gemini format"""
        gemini_tools = []
        
        for tool in self.available_tools:
            try:
                # Convert MCP tool schema to Gemini function declaration
                function_declaration = types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description or f"Execute {tool.name}",
                    parameters=tool.inputSchema or {}
                )
                
                gemini_tool = types.Tool(
                    function_declarations=[function_declaration]
                )
                gemini_tools.append(gemini_tool)
                
            except Exception as e:
                logger.warning(f"Failed to convert tool {tool.name}: {e}")
                
        return gemini_tools
        
    async def process_user_input(self, user_input: str) -> str:
        """
        Enhanced conversational loop with workflow support:
        
        1. Enhanced context gathering
        2. Sequential tool execution with iterative conversation loop
        3. Intelligent error recovery
        4. Progressive responses
        5. Context optimization
        6. Workflow learning and suggestion capabilities
        """
        
        # Handle workflow commands first
        if user_input.strip().startswith("workflow"):
            return await self.workflow_cli.process_workflow_command(user_input.strip())
        
        # Step 1: Enhance user input with context
        context = await self._get_enhanced_context(user_input)
        
        if context:
            enhanced_input = f"{context}\n\nUser: {user_input}"
            logger.info("🔗 Enhanced context included")
        else:
            enhanced_input = user_input
            logger.warning("⚠️ No context available")
            
        self.messages.append({
            "role": "user",
            "content": enhanced_input
        })
        
        # Step 2: Optimize context if needed
        self.messages = self.context_manager.optimize_context(self.messages)
        
        logger.info(f"📝 User input processed (messages: {len(self.messages)})")
        
        # Core enhanced conversation loop (critical for multi-step execution)
        max_iterations = MAX_ITERATIONS
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            logger.debug(f"🔄 Enhanced conversation loop iteration {iteration}")
            
            try:
                # Prepare tools and config
                tools = self._convert_tools_to_gemini_format()
                
                config = types.GenerateContentConfig(
                    tools=tools if tools else None,
                    temperature=0.7,  # Slightly lower for more consistent behavior
                    max_output_tokens=2048,
                )
                
                # Create optimized content from messages  
                contents = self._create_gemini_contents()
                
                # Log final prompt for debugging
                if DEBUG:
                    self._log_enhanced_prompt(contents, config)
                
                # Generate response
                response = await self.genai_client.aio.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=contents,
                    config=config
                )
                
                # Process response
                if not response.candidates or not response.candidates[0].content:
                    logger.error("No response generated from Gemini")
                    return "Error: No response generated"
                
                candidate = response.candidates[0]
                content = candidate.content
                
                # Extract tool calls and assistant content
                tool_calls = []
                assistant_content = ""
                
                for part in content.parts:
                    if hasattr(part, 'text') and part.text:
                        assistant_content += part.text
                    elif hasattr(part, 'function_call') and part.function_call:
                        func_call = part.function_call
                        tool_calls.append({
                            "id": f"call_{iteration}_{func_call.name}",
                            "type": "function", 
                            "function": {
                                "name": func_call.name,
                                "arguments": dict(func_call.args) if func_call.args else {}
                            }
                        })
                
                # Add assistant response to messages
                assistant_msg = {"role": "assistant"}
                if assistant_content:
                    assistant_msg["content"] = assistant_content
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                    
                self.messages.append(assistant_msg)
                
                # Execute tool calls if present (enhanced sequential execution)
                if tool_calls:
                    logger.info(f"🔧 Executing {len(tool_calls)} tool call(s) sequentially")
                    
                    # Execute with enhanced orchestrator
                    execution_results = await self.tool_orchestrator.execute_tool_chain_sequentially(tool_calls)
                    
                    # Record executions for workflow learning
                    if self.workflow_recording.is_recording():
                        for result in execution_results:
                            self.workflow_recording.current_session.add_tool_execution(result)
                    
                    # Add tool results to messages
                    for i, result in enumerate(execution_results):
                        tool_call = tool_calls[i]
                        
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "name": result.tool_name,
                            "content": json.dumps({
                                "result": result.result,
                                "success": result.status == ToolExecutionStatus.COMPLETED,
                                "error": result.error,
                                "execution_time": result.execution_time,
                                "retry_count": result.retry_count
                            })
                        })
                        
                    self._tool_call_count += len(tool_calls)
                    
                    # Get updated context after tool execution  
                    post_tool_context = await self._get_enhanced_context("Tools executed, analyzing current state...")
                    
                    if post_tool_context:
                        self.messages.append({
                            "role": "user",
                            "content": f"{post_tool_context}\n\n[Tools executed successfully. Please continue based on the current state.]"
                        })
                        logger.info("🔄 Post-tool context captured")
                    
                    # Continue loop for next iteration (CRITICAL: this keeps the conversation going)
                    continue
                else:
                    # No tool calls - final response
                    logger.info(f"✅ Enhanced response generated (iteration {iteration})")
                    
                    # Check for workflow suggestions before returning
                    suggestion_text = ""
                    if ENABLE_WORKFLOW_LEARNING and len(self.system_state.tool_execution_history) >= WORKFLOW_PATTERN_MIN_LENGTH:
                        if any(r.status == ToolExecutionStatus.COMPLETED for r in self.system_state.tool_execution_history[-3:]):
                            suggestions = await self.workflow_recording.auto_suggest_workflows()
                            if suggestions and len(suggestions) > 0 and suggestions[0].confidence_score > 0.8:
                                suggestion_text = f"\n\n💡 **Workflow Suggestion**: I detected a repeatable pattern in your recent actions. " \
                                                f"Would you like me to save this as a workflow? Type `workflow record start` to begin capturing patterns."
                    
                    return (assistant_content or "Response completed (no text content)") + suggestion_text
                    
            except Exception as e:
                logger.error(f"Error in enhanced conversation loop iteration {iteration}: {e}")
                
                # Enhanced error handling
                if ENABLE_ERROR_RECOVERY and iteration < max_iterations - 1:
                    self.messages.append({
                        "role": "user",
                        "content": f"An error occurred: {str(e)}. Please try a different approach or break down the task into smaller steps."
                    })
                    continue
                else:
                    return f"Error: {str(e)}"
                    
        # Safety limit reached
        logger.warning(f"Reached maximum iterations ({max_iterations})")
        return "Response completed (reached iteration limit)"
        
    def _create_gemini_contents(self) -> List[types.Content]:
        """Create Gemini contents from conversation messages"""
        contents = []
        
        for message in self.messages:
            role = message["role"]
            content_text = message.get("content", "")
            
            # Map roles to Gemini format
            if role == "system":
                # System messages are typically included in the first user message
                continue
            elif role == "user":
                # Include system message content in first user message if present
                if len(contents) == 0 and self.messages[0].get("role") == "system":
                    system_content = self.messages[0].get("content", "")
                    content_text = f"{system_content}\n\nUser: {content_text}"
                
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part(text=content_text)]
                ))
                
            elif role == "assistant":
                contents.append(types.Content(
                    role="model", 
                    parts=[types.Part(text=content_text)]
                ))
                
            elif role == "tool":
                # Tool results are included as model responses
                tool_name = message.get("name", "tool")
                tool_content = message.get("content", {})
                
                if isinstance(tool_content, dict):
                    tool_text = f"Tool {tool_name} result: {json.dumps(tool_content, indent=2)}"
                else:
                    tool_text = f"Tool {tool_name} result: {tool_content}"
                    
                contents.append(types.Content(
                    role="model",
                    parts=[types.Part(text=tool_text)]
                ))
        
        return contents
        
    def _log_enhanced_prompt(self, contents: List[types.Content], config: types.GenerateContentConfig):
        """Log enhanced prompt information for debugging"""
        if not DEBUG:
            return
            
        logger.debug("🔍 Enhanced Prompt Analysis:")
        logger.debug(f"  - Contents: {len(contents)} items")
        logger.debug(f"  - Tools available: {len(config.tools) if config.tools else 0}")
        logger.debug(f"  - Temperature: {config.temperature}")
        logger.debug(f"  - Max tokens: {config.max_output_tokens}")
        
        # Log recent conversation context
        if len(contents) >= 2:
            last_user = next((c for c in reversed(contents) if c.role == "user"), None)
            if last_user and last_user.parts:
                user_text = last_user.parts[0].text[:200] + "..." if len(last_user.parts[0].text) > 200 else last_user.parts[0].text
                logger.debug(f"  - Last user input: {user_text}")
        
        # Log system state
        logger.debug(f"  - Tool execution history: {len(self.system_state.tool_execution_history)} items")
        logger.debug(f"  - Current browser URL: {self.system_state.browser_state.get('current_url', 'None')}")
        logger.debug(f"  - Recording workflow: {self.workflow_recording.is_recording() if self.workflow_recording else False}")
        
    async def run_interactive_session(self):
        """Run interactive session with workflow support"""
        print("🎉 Welcome to the Workflow-Enhanced Conversational Orchestrator!")
        print("🚀 Advanced browser automation with workflow learning capabilities")
        print()
        
        self._print_system_status()
        print()
        print("💬 Type your requests or commands. Special commands:")
        print("   • 'workflow help' - Show workflow commands")
        print("   • 'workflow list' - List available workflows") 
        print("   • 'workflow record start' - Start recording workflow")
        print("   • 'status' - Show system status")
        print("   • 'quit' or 'exit' - Exit the session")
        print("   • 'clear' - Clear conversation history")
        print()
        
        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                    
                # Handle special commands
                if user_input.lower() in ['quit', 'exit']:
                    print("👋 Goodbye!")
                    break
                elif user_input.lower() == 'status':
                    self._print_system_status()
                    continue
                elif user_input.lower() == 'clear':
                    # Rebuild system message and clear conversation
                    system_content = self.system_message_builder.build_comprehensive_system_message()
                    self.messages = [{"role": "system", "content": system_content}]
                    print("🧹 Conversation history cleared")
                    continue
                
                # Process input
                print("🤖 Assistant: ", end="", flush=True)
                response = await self.process_user_input(user_input)
                print(response)
                print()
                
            except KeyboardInterrupt:
                print("\n👋 Session interrupted. Type 'quit' to exit or continue...")
            except Exception as e:
                print(f"\n❌ Error: {e}")
                logger.error(f"Interactive session error: {e}")
                
    def _print_system_status(self):
        """Print current system status"""
        print("📊 System Status:")
        print(f"   🔗 MCP Connection: {'✅ Connected' if self.mcp_session else '❌ Disconnected'}")
        print(f"   🤖 Gemini Client: {'✅ Ready' if self.genai_client else '❌ Not initialized'}")
        print(f"   🛠️  Available Tools: {len(self.available_tools)}")
        print(f"   📝 Conversation Length: {len(self.messages)} messages")
        print(f"   🎯 Tool Executions: {len(self.system_state.tool_execution_history)}")
        
        # Workflow status
        if self.workflow_recording:
            if self.workflow_recording.is_recording():
                session = self.workflow_recording.recording_session
                duration = datetime.now() - session.start_time
                print(f"   🎬 Recording: ✅ Active ({duration.total_seconds():.0f}s)")
            else:
                print(f"   🎬 Recording: ⏹️  Stopped")
                
        # Recent activity
        if self.system_state.tool_execution_history:
            recent_tools = [r.tool_name for r in self.system_state.tool_execution_history[-3:]]
            print(f"   🔄 Recent Tools: {' → '.join(recent_tools)}")
            
        # Browser state
        if self.system_state.browser_state.get("current_url"):
            print(f"   🌐 Current URL: {self.system_state.browser_state['current_url']}")
        
    async def cleanup(self):
        """Clean up resources"""
        logger.info("🧹 Cleaning up resources...")
        
        try:
            # Save any ongoing workflow recording
            if self.workflow_recording and self.workflow_recording.is_recording():
                logger.info("💾 Saving ongoing workflow recording...")
                await self.workflow_recording.stop_recording_and_create_workflow("Session cleanup")
                
            # Close MCP session
            await self.exit_stack.aclose()
            logger.info("✅ Cleanup completed")
            
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")


async def main():
    """Enhanced main entry point with workflow support"""
    orchestrator = WorkflowEnhancedConversationalOrchestrator()
    
    try:
        await orchestrator.initialize()
        await orchestrator.run_interactive_session()
    except KeyboardInterrupt:
        print("\n👋 Session interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.error(traceback.format_exc())
        print(f"\n❌ Fatal error: {e}")
    finally:
        await orchestrator.cleanup()


if __name__ == "__main__":
    # Check for API key
    if not GEMINI_API_KEY:
        print("❌ Error: GEMINI_API_KEY environment variable is required")
        print("Please set your Gemini API key and try again.")
        sys.exit(1)
    
    # Create workflows directory if it doesn't exist
    Path(WORKFLOWS_DIR).mkdir(exist_ok=True)
    
    asyncio.run(main())