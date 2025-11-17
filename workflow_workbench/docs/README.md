# Workflow-Enhanced Conversational Orchestrator

## Overview

The Workflow-Enhanced Conversational Orchestrator is an advanced MCP-based automation system that combines intelligent browser control with workflow learning and execution capabilities.

## Key Features

- **Workflow Learning**: Automatically detect patterns in tool execution and suggest workflows
- **Deterministic Execution**: Run workflows without LLM intervention for reliable automation
- **Error Recovery**: Intelligent error handling with retry policies and recovery strategies
- **Context Management**: Optimize conversation context for efficient token usage
- **Pattern Recognition**: Identify repeatable automation patterns from execution history
- **CLI Interface**: Comprehensive command-line tools for workflow management

## Quick Start

### Installation

```bash
cd workflow_workbench
pip install -r requirements.txt
```

### Configuration

Set up your `.env` file:

```bash
GEMINI_API_KEY=your_api_key_here
MCP_SERVER_COMMAND="python path/to/mcp_browser_control.py --server-only"
WORKFLOWS_DIR=./workflows
```

### Basic Usage

```python
from workflow_workbench import WorkflowEnhancedConversationalOrchestrator

# Initialize orchestrator
orchestrator = WorkflowEnhancedConversationalOrchestrator()
await orchestrator.initialize()

# Run interactive session
await orchestrator.run_interactive_session()
```

### Workflow Commands

```bash
workflow list                    # List all workflows
workflow run <name>             # Execute a workflow
workflow record start           # Start recording
workflow record stop            # Stop and create workflow
workflow suggest                # Get workflow suggestions
```

## Architecture

See [architecture.md](architecture.md) for detailed system design and [diagrams](../diagrams/) for visual representations.

## Module Structure

- **config.py**: Configuration management
- **models.py**: Data structures and types
- **workflow_engine.py**: Workflow learning and execution
- **tool_execution.py**: Tool orchestration and validation
- **workflow_cli.py**: Command-line interface
- **orchestrator.py**: Main coordination layer

## Documentation

- [Architecture Documentation](architecture.md)
- [API Reference](api_reference.md)
- [Workflow Guide](workflows.md)
- [Usage Examples](examples.md)

## Visual Guides

- [System Overview](../diagrams/overview.mmd)
- [Workflow Lifecycle](../diagrams/workflow_lifecycle.mmd)
- [Tool Execution](../diagrams/tool_execution.mmd)
- [Learning System](../diagrams/learning_system.mmd)
- [Integration Map](../diagrams/integration.mmd)

## Contributing

Contributions welcome! Please see the architecture documentation to understand the system design before making changes.

## License

MIT License - See LICENSE file for details

## Author

Agent-Space Team
Version: 3.0 Workflow Enhanced
