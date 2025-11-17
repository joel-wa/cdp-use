# Architecture Documentation

## System Overview

The Workflow-Enhanced Conversational Orchestrator follows a **layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────┐
│   User Interface Layer          │  CLI & Interactive Sessions
├─────────────────────────────────┤
│   Orchestration Layer           │  Main Coordinator
├─────────────────────────────────┤
│   Workflow Subsystem            │  Learning & Execution
├─────────────────────────────────┤
│   Tool Execution Subsystem      │  Validation & Recovery
├─────────────────────────────────┤
│   Foundation Layer              │  Models & Configuration
└─────────────────────────────────┘
```

## Module Breakdown

### 1. Configuration Module (`config.py`)

**Purpose**: Centralized configuration management

**Responsibilities**:
- Environment variable loading
- Feature flags
- Execution limits and timeouts
- Logging setup

**Key Configurations**:
- `GEMINI_API_KEY`: API key for Gemini
- `MCP_SERVER_COMMAND`: Command to start MCP server
- `WORKFLOWS_DIR`: Directory for workflow storage
- `MAX_RETRY_ATTEMPTS`: Maximum retry attempts for failed operations

### 2. Data Models (`models.py`)

**Purpose**: Core data structures and types

**Key Classes**:
- `WorkflowDefinition`: Complete workflow specification
- `WorkflowStep`: Individual workflow step
- `WorkflowParameter`: Input parameter definition
- `ToolExecutionResult`: Result of tool execution
- `SystemState`: Global system state

**Enumerations**:
- `ErrorSeverity`: Error classification
- `ToolExecutionStatus`: Tool execution states
- `WorkflowExecutionStatus`: Workflow execution states

### 3. Workflow Engine (`workflow_engine.py`)

**Purpose**: Workflow learning, validation, and execution

**Components**:

#### Pattern Analyzer
- Identifies repeatable tool sequences
- Matches against known patterns (web, file, automation)
- Calculates pattern confidence scores

#### Parameter Extractor
- Extracts parameterizable values from tool executions
- Identifies URLs, file paths, numeric values
- Merges and deduplicates parameters

#### Learning Engine
- Analyzes execution history for workflow candidates
- Groups related tool chains
- Calculates confidence scores

#### Workflow Validator
- Validates workflow definitions
- Checks for circular dependencies
- Validates input parameters

#### Workflow Executor
- Executes workflows without LLM intervention
- Handles step dependencies
- Implements retry logic

#### Workflow Library
- Manages workflow storage (YAML)
- CRUD operations for workflows
- Tracks execution statistics

### 4. Tool Execution (`tool_execution.py`)

**Purpose**: Tool orchestration, validation, and error recovery

**Components**:

#### Tool Validator
- Pre-execution validation
- Parameter checking
- Resource verification

#### Error Recovery Engine
- Error classification by severity
- Recovery strategy generation
- Tool-specific suggestions

#### Context Manager
- Token usage optimization
- Message summarization
- Context window management

#### Tool Chain Orchestrator
- Sequential tool execution
- Retry logic with exponential backoff
- State management

#### Streaming Response Manager
- Progress updates during execution
- Real-time feedback
- Streaming vs batch modes

### 5. Workflow CLI (`workflow_cli.py`)

**Purpose**: Command-line interface for workflow operations

**Commands**:
- `workflow list`: List available workflows
- `workflow run <name>`: Execute workflow
- `workflow show <name>`: Display workflow details
- `workflow delete <name>`: Remove workflow
- `workflow search <query>`: Search workflows
- `workflow record start/stop`: Record new workflows
- `workflow stats`: Show execution statistics
- `workflow suggest`: Get workflow suggestions

### 6. Main Orchestrator (`orchestrator.py`)

**Purpose**: Main coordination and integration

**Responsibilities**:
- MCP server connection management
- Gemini API integration
- Message flow coordination
- Component initialization
- Interactive session management

## Design Patterns

### 1. **Layered Architecture**
Clear separation between UI, business logic, and data layers

### 2. **Strategy Pattern**
Error recovery strategies chosen dynamically based on error type

### 3. **Chain of Responsibility**
Tool execution chains with sequential processing

### 4. **Repository Pattern**
Workflow Library abstracts storage operations

### 5. **State Pattern**
System state transitions during workflow execution

### 6. **Builder Pattern**
System message construction with configurable components

## Data Flow

### Workflow Creation Flow
```
User Action → Learning Engine → Pattern Analysis → 
Parameter Extraction → Workflow Definition → Library Storage
```

### Workflow Execution Flow
```
Load Workflow → Validate → Resolve Parameters → 
Calculate Order → Execute Steps → Process Outputs
```

### Tool Execution Flow
```
Tool Call → Validate → Execute (MCP) → 
Process Result → Update State → Return
```

## Extension Points

### Adding New Patterns
Extend `PatternAnalyzer` with new pattern definitions:
```python
self.custom_patterns = [
    ["tool1", "tool2", "tool3"]
]
```

### Custom Validators
Add tool-specific validation in `ToolValidator`:
```python
def _validate_custom_tool(self, args):
    # Your validation logic
    return is_valid, error_message
```

### Error Recovery Strategies
Extend `ErrorRecoveryEngine` with custom strategies:
```python
def _handle_custom_error(self, error):
    # Your recovery logic
    return severity, suggestions
```

## Performance Considerations

### Context Optimization
- Automatic summarization of old messages
- Token estimation and pruning
- Recent message preservation

### Workflow Execution
- Topological sorting for optimal step order
- Parallel execution potential (future)
- Retry with exponential backoff

### Storage
- YAML-based workflow storage
- In-memory caching
- Lazy loading of workflows

## Security Considerations

- Parameter validation before execution
- File path sanitization
- URL validation
- Permission checking

## Testing Strategy

### Unit Tests
- Individual component testing
- Mock MCP server responses
- Parameter validation tests

### Integration Tests
- End-to-end workflow execution
- Multi-step tool chains
- Error recovery scenarios

### Performance Tests
- Context optimization benchmarks
- Workflow execution timing
- Memory usage profiling

## Future Enhancements

1. **Parallel Step Execution**: Execute independent steps concurrently
2. **Workflow Versioning**: Track workflow changes over time
3. **Visual Workflow Editor**: GUI for workflow creation
4. **Advanced Pattern Learning**: ML-based pattern recognition
5. **Workflow Templates**: Pre-built workflow library
6. **Distributed Execution**: Run workflows across multiple nodes

## Deployment

### Development
```bash
python orchestrator.py
```

### Production
Consider:
- Container deployment (Docker)
- Environment variable management
- Log aggregation
- Monitoring and alerting
- Backup strategies for workflows

## Monitoring

### Key Metrics
- Workflow success rate
- Average execution time
- Tool failure rate
- Context optimization frequency
- Pattern detection accuracy

### Logging Levels
- DEBUG: Detailed execution traces
- INFO: General operation logs
- WARNING: Recoverable errors
- ERROR: Critical failures
- CRITICAL: System failures

## Troubleshooting

### Common Issues

**Workflow Fails to Load**
- Check YAML syntax
- Verify file permissions
- Ensure all required fields present

**Tool Execution Timeout**
- Increase `TOOL_EXECUTION_TIMEOUT`
- Check MCP server responsiveness
- Review network connectivity

**Pattern Not Detected**
- Verify chain length >= `WORKFLOW_PATTERN_MIN_LENGTH`
- Check tool execution success rate
- Review pattern definitions

**Context Overflow**
- Reduce `MAX_CONTEXT_TOKENS` if needed
- Enable context optimization
- Review message summarization logic
