#!/usr/bin/env python3
"""
Data models and type definitions for Workflow-Enhanced Orchestrator

Contains all dataclasses, enums, and data structures used across the system.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from collections import deque

from config import CONTINUE_ON_ERROR


# =====================================================
# ENUMERATIONS
# =====================================================

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
    continue_on_error: bool = CONTINUE_ON_ERROR
    
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


@dataclass
class ValidationResult:
    """Result of validation operation"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# =====================================================
# EXCEPTIONS
# =====================================================

class WorkflowExecutionError(Exception):
    """Exception raised during workflow execution"""
    pass
