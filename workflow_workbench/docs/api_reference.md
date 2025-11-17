# API Reference

## Core Classes

### WorkflowDefinition

Complete specification of a reusable workflow.

```python
@dataclass
class WorkflowDefinition:
    name: str
    version: str
    description: str
    parameters: List[WorkflowParameter]
    steps: List[WorkflowStep]
    error_handling: ErrorHandlingConfig
    outputs: List[WorkflowOutput]
    metadata: Dict[str, Any]
    author: str
    created_at: datetime
```

**Methods**:
- `from_execution_history(history, user_intent, name)`: Create workflow from tool chain
- `to_dict()`: Serialize to dictionary
- `from_dict(data)`: Deserialize from dictionary

**Example**:
```python
workflow = WorkflowDefinition.from_execution_history(
    tool_chain,
    "Extract data from webpage",
    "web_data_extraction"
)
```

### WorkflowExecutor

Executes workflows deterministically without LLM intervention.

```python
class WorkflowExecutor:
    def __init__(self, mcp_session: ClientSession)
    
    async def execute_workflow(
        self, 
        workflow: WorkflowDefinition,
        parameters: Dict[str, Any]
    ) -> WorkflowExecutionResult
```

**Methods**:
- `execute_workflow(workflow, parameters)`: Execute complete workflow
- `_execute_step(step, context)`: Execute individual step
- `_calculate_execution_order(steps)`: Topological sort of steps

**Example**:
```python
executor = WorkflowExecutor(mcp_session)
result = await executor.execute_workflow(workflow, {
    "url": "https://example.com",
    "selector": ".data-class"
})
```

### WorkflowLibrary

Manages workflow storage and retrieval.

```python
class WorkflowLibrary:
    def __init__(self, storage_path: str = WORKFLOWS_DIR)
    
    async def save_workflow(self, workflow: WorkflowDefinition)
    async def load_workflow(self, name: str) -> Optional[WorkflowDefinition]
    async def list_workflows(self) -> List[str]
    async def delete_workflow(self, name: str) -> bool
    async def search_workflows(self, query: str) -> List[WorkflowDefinition]
    async def get_workflow_stats(self, name: str) -> Dict[str, Any]
```

**Example**:
```python
library = WorkflowLibrary()
await library.save_workflow(workflow)
all_workflows = await library.list_workflows()
```

### WorkflowLearningEngine

Learns workflows from execution patterns.

```python
class WorkflowLearningEngine:
    def __init__(self, orchestrator)
    
    async def analyze_session_for_workflows(self) -> List[WorkflowCandidate]
```

**Methods**:
- `analyze_session_for_workflows()`: Identify workflow candidates
- `_group_tool_chains(history)`: Group related tool executions
- `_is_workflow_candidate(chain)`: Determine if chain is suitable
- `_calculate_confidence_score(chain, parameters)`: Score candidacy

**Example**:
```python
learning_engine = WorkflowLearningEngine(orchestrator)
candidates = await learning_engine.analyze_session_for_workflows()
for candidate in candidates:
    print(f"{candidate.name}: {candidate.confidence_score:.2f}")
```

### ToolChainOrchestrator

Orchestrates sequential tool execution.

```python
class ToolChainOrchestrator:
    def __init__(self, mcp_session: ClientSession, state: SystemState)
    
    async def execute_tool_chain_sequentially(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> List[ToolExecutionResult]
```

**Methods**:
- `execute_tool_chain_sequentially(tool_calls)`: Execute tools in sequence
- `_execute_single_tool_with_recovery(tool_call)`: Execute with retry logic

**Example**:
```python
orchestrator = ToolChainOrchestrator(mcp_session, system_state)
results = await orchestrator.execute_tool_chain_sequentially([
    {"function": {"name": "navigate", "arguments": {"url": "https://example.com"}}},
    {"function": {"name": "get_page_content", "arguments": {}}}
])
```

### ToolValidator

Validates tool calls before execution.

```python
class ToolValidator:
    def __init__(self, state: SystemState)
    
    def validate_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]
```

**Methods**:
- `validate_tool_call(tool_name, arguments)`: Validate tool parameters
- `_validate_read_file(args)`: File-specific validation
- `_validate_navigate(args)`: URL validation
- `_validate_click_element_by_index(args)`: Element index validation

**Example**:
```python
validator = ToolValidator(system_state)
is_valid, error = validator.validate_tool_call("navigate", {
    "url": "https://example.com"
})
```

### WorkflowCLI

Command-line interface for workflow management.

```python
class WorkflowCLI:
    def __init__(self, orchestrator)
    
    async def process_workflow_command(self, command: str) -> str
```

**Commands**:
- `workflow list`: List all workflows
- `workflow run <name>`: Execute workflow
- `workflow show <name>`: Display workflow details
- `workflow delete <name>`: Remove workflow
- `workflow search <query>`: Search workflows
- `workflow record start`: Begin recording
- `workflow record stop`: End recording and create workflow
- `workflow stats`: Show statistics
- `workflow suggest`: Get suggestions

**Example**:
```python
cli = WorkflowCLI(orchestrator)
response = await cli.process_workflow_command("workflow list")
print(response)
```

## Data Models

### WorkflowParameter

Input parameter definition for workflows.

```python
@dataclass
class WorkflowParameter:
    name: str
    type: str  # string, integer, float, boolean, array, object
    required: bool = True
    default: Any = None
    description: str = ""
    validation: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self, value: Any) -> Tuple[bool, Optional[str]]
```

**Example**:
```python
param = WorkflowParameter(
    name="url",
    type="string",
    required=True,
    description="Target URL to navigate",
    validation={"pattern": "^https?://.+"}
)
is_valid, error = param.validate("https://example.com")
```

### WorkflowStep

Individual step in a workflow.

```python
@dataclass
class WorkflowStep:
    id: str
    tool: str
    description: str
    parameters: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)
    retry_policy: Optional[RetryPolicy] = None
    validation: Optional[StepValidation] = None
    conditional: Optional[str] = None
    
    def resolve_parameters(self, context: Dict[str, Any]) -> Dict[str, Any]
```

**Example**:
```python
step = WorkflowStep(
    id="step_1_navigate",
    tool="navigate",
    description="Navigate to target URL",
    parameters={"url": "{{target_url}}"},
    retry_policy=RetryPolicy(max_attempts=3)
)
```

### ToolExecutionResult

Result of tool execution with metadata.

```python
@dataclass
class ToolExecutionResult:
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
```

### SystemState

Global system state tracking.

```python
@dataclass
class SystemState:
    current_directory: Optional[str] = None
    file_system_cache: Dict[str, Any] = field(default_factory=dict)
    browser_state: Dict[str, Any] = field(default_factory=dict)
    executed_commands: deque = field(default_factory=lambda: deque(maxlen=100))
    environment_vars: Dict[str, str] = field(default_factory=dict)
    session_start_time: datetime = field(default_factory=datetime.now)
    tool_execution_history: List[ToolExecutionResult] = field(default_factory=list)
    workflow_execution_history: List[WorkflowExecutionResult] = field(default_factory=list)
    
    def update_from_tool_result(self, result: ToolExecutionResult)
```

## Enumerations

### ToolExecutionStatus

```python
class ToolExecutionStatus(Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
```

### WorkflowExecutionStatus

```python
class WorkflowExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
```

### ErrorSeverity

```python
class ErrorSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    RECOVERABLE = "recoverable"
    CRITICAL = "critical"
    FATAL = "fatal"
```

## Configuration

### Environment Variables

```python
# Gemini Configuration
GEMINI_API_KEY: str
GEMINI_MODEL: str = "gemini-2.5-flash"

# MCP Configuration
MCP_SERVER_URL: str
MCP_SERVER_COMMAND: str
MCP_TRANSPORT: str = "stdio"

# Feature Flags
DEBUG: bool = False
ENABLE_VISUAL_CONTEXT: bool = True
ENABLE_TOOL_VALIDATION: bool = True
ENABLE_ERROR_RECOVERY: bool = True
ENABLE_WORKFLOW_LEARNING: bool = True
AUTO_SUGGEST_WORKFLOWS: bool = True

# Execution Limits
MAX_ITERATIONS: int = 20
MAX_RETRY_ATTEMPTS: int = 3
TOOL_EXECUTION_TIMEOUT: int = 60
MAX_CONTEXT_TOKENS: int = 100000

# Workflow Configuration
WORKFLOWS_DIR: str = "./workflows"
WORKFLOW_PATTERN_MIN_LENGTH: int = 3
WORKFLOW_EXECUTION_MODE: str = "interactive"
```

## Error Handling

### WorkflowExecutionError

```python
class WorkflowExecutionError(Exception):
    """Exception raised during workflow execution"""
    pass
```

**Usage**:
```python
if not dependencies_satisfied:
    raise WorkflowExecutionError("Dependencies not met for step")
```

## Type Hints

All public APIs use comprehensive type hints for better IDE support and type checking:

```python
from typing import Dict, Any, List, Optional, Tuple, AsyncGenerator

async def execute_workflow(
    workflow: WorkflowDefinition,
    parameters: Dict[str, Any]
) -> WorkflowExecutionResult:
    ...
```
