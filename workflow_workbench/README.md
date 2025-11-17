# Workflow-Enhanced Conversational MCP Orchestrator

A powerful Python framework for building conversational AI agents with browser automation capabilities, workflow learning, and deterministic execution.

## 🌟 Features

- **Conversational AI**: Natural language interaction powered by Google Gemini
- **Browser Automation**: Full web automation via Model Context Protocol (MCP)
- **Workflow Learning**: Automatically detect and learn from repeatable patterns
- **Deterministic Execution**: Replay workflows without LLM intervention
- **Error Recovery**: Intelligent error handling with retry and fallback strategies
- **Visual Context**: Enhanced context with screenshots and interactive elements
- **CLI Management**: Comprehensive command-line interface for workflows

## 📁 Project Structure

```
workflow_workbench/
├── orchestrator.py         # Main entry point
├── config.py               # Configuration management
├── models.py               # Data models and types
├── workflow_engine.py      # Workflow learning and execution
├── tool_execution.py       # Tool orchestration and error recovery
├── workflow_cli.py         # CLI interface
├── __init__.py             # Package exports
├── docs/                   # Documentation
│   ├── README.md           # Quick start guide
│   ├── architecture.md     # System architecture
│   ├── api_reference.md    # API documentation
│   ├── workflows.md        # Workflow guide
│   └── examples.md         # Usage examples
├── diagrams/               # Visual documentation
│   ├── overview.mmd        # System overview
│   ├── workflow_lifecycle.mmd
│   ├── tool_execution.mmd
│   ├── learning_system.mmd
│   └── integration.mmd
├── workflows/              # Workflow definitions (YAML)
├── MIGRATION.md            # Migration guide
└── README.md               # This file
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Google Gemini API key
- MCP server (browser automation)

### Installation

1. **Clone or create the workspace**:
```bash
cd workflow_workbench
```

2. **Install dependencies**:
```bash
pip install google-generativeai mcp python-dotenv pyyaml
```

3. **Configure environment**:
Create a `.env` file:
```bash
GEMINI_API_KEY=your_gemini_api_key
MCP_SERVER_COMMAND=python -m my-mcp-server
```

### Run the Orchestrator

```bash
python orchestrator.py
```

This starts an interactive session where you can:
- Give natural language instructions
- Automate browser tasks
- Record and replay workflows
- Manage workflow library

## 💬 Basic Usage

### Interactive Session

```
🎉 Welcome to the Workflow-Enhanced Conversational Orchestrator!

You: Navigate to example.com and extract the page title
🤖 Assistant: [Navigates to site and extracts title]

You: workflow record start
🤖 Assistant: Started recording workflow session...

You: Fill the contact form
🤖 Assistant: [Records actions while filling form]

You: workflow record stop
🤖 Assistant: Workflow saved as 'contact_form_fill'
```

### Workflow Commands

```bash
# List all workflows
workflow list

# Show workflow details
workflow show workflow_name

# Run a workflow
workflow run workflow_name

# Delete a workflow
workflow delete workflow_name

# Search workflows
workflow search keyword

# View workflow statistics
workflow stats workflow_name

# Get workflow suggestions
workflow suggest
```

## 📖 Documentation

Comprehensive documentation is available in the `docs/` directory:

- **[Quick Start](docs/README.md)** - Get started quickly
- **[Architecture](docs/architecture.md)** - Understand the system design
- **[API Reference](docs/api_reference.md)** - Detailed API documentation
- **[Workflow Guide](docs/workflows.md)** - Learn about workflows
- **[Examples](docs/examples.md)** - Practical usage examples

## 🎨 Visual Documentation

View Mermaid diagrams in the `diagrams/` directory:

- **[System Overview](diagrams/overview.mmd)** - High-level architecture
- **[Workflow Lifecycle](diagrams/workflow_lifecycle.mmd)** - Workflow execution flow
- **[Tool Execution](diagrams/tool_execution.mmd)** - Tool orchestration
- **[Learning System](diagrams/learning_system.mmd)** - Pattern recognition
- **[Integration](diagrams/integration.mmd)** - System integration

## 🔧 Configuration

Key configuration options in `config.py`:

```python
# API Configuration
GEMINI_API_KEY          # Required: Your Gemini API key
GEMINI_MODEL            # Model to use (default: gemini-2.0-flash-exp)

# MCP Configuration
MCP_TRANSPORT           # Transport type: stdio, http, or auto
MCP_SERVER_URL          # HTTP server URL (if using HTTP transport)
MCP_SERVER_COMMAND      # Command to start MCP server (stdio)

# Feature Flags
ENABLE_STREAMING        # Enable streaming responses
ENABLE_TOOL_VALIDATION  # Validate tools before execution
ENABLE_ERROR_RECOVERY   # Intelligent error recovery
ENABLE_WORKFLOW_LEARNING # Automatic workflow learning
ENABLE_VISUAL_CONTEXT   # Include screenshots in context
ENABLE_INTERACTIVE_CONTEXT # Map interactive elements

# Execution Limits
MAX_ITERATIONS          # Max conversation iterations
MAX_RETRY_ATTEMPTS      # Max tool retry attempts
TOOL_TIMEOUT            # Tool execution timeout (seconds)
```

## 🏗️ Architecture

### Layered Design

```
┌─────────────────────────────────────┐
│     User Interface (CLI)            │
├─────────────────────────────────────┤
│     Main Orchestrator               │
├─────────────────────────────────────┤
│  Workflow Engine │ Tool Execution   │
├─────────────────────────────────────┤
│         Data Models                 │
├─────────────────────────────────────┤
│         Configuration               │
└─────────────────────────────────────┘
```

### Key Components

- **Orchestrator**: Main coordinator, handles conversation loop
- **Workflow Engine**: Learning, validation, execution, library management
- **Tool Execution**: Orchestration, validation, error recovery, context optimization
- **Models**: Data structures and type definitions
- **Config**: Centralized configuration management

## 📝 Example Workflows

### Web Scraping

```yaml
name: product_extraction
description: Extract product details from e-commerce site

parameters:
  - name: product_url
    type: string
    required: true

steps:
  - id: navigate
    tool: navigate
    parameters:
      url: "{{product_url}}"
  
  - id: extract_title
    tool: execute_javascript
    parameters:
      expression: "document.querySelector('.title')?.textContent"
```

### Form Automation

```yaml
name: contact_form_submission
description: Automatically fill and submit contact form

steps:
  - id: navigate
    tool: navigate
    parameters:
      url: "https://example.com/contact"
  
  - id: fill_name
    tool: type_text
    parameters:
      selector: "#name"
      text: "{{user_name}}"
  
  - id: submit
    tool: click_element
    parameters:
      selector: "button[type='submit']"
```

## 🧪 Testing

Run tests (when available):
```bash
python -m pytest tests/
```

## 🤝 Contributing

This is a refactored project structure. Key principles:

1. **Keep it Simple**: Avoid over-engineering
2. **Maintain Modularity**: Each module has clear responsibility
3. **Document Everything**: Code, architecture, and usage
4. **Test Thoroughly**: Ensure reliability

## 📄 License

[Your License Here]

## 🔗 Related Projects

- [Model Context Protocol](https://github.com/modelcontextprotocol)
- [Google Generative AI](https://ai.google.dev/)

## ⚠️ Migration from Monolithic Version

If you're migrating from the original monolithic `workflow_enhanced_orchestrator.py`, see **[MIGRATION.md](MIGRATION.md)** for detailed instructions.

## 🆘 Support

- **Issues**: Report bugs or request features via GitHub issues
- **Documentation**: Check `docs/` directory for comprehensive guides
- **Examples**: See `docs/examples.md` for practical usage patterns

## 🎯 Roadmap

- [ ] Unit test suite
- [ ] Integration test suite
- [ ] Performance benchmarks
- [ ] Plugin system for custom tools
- [ ] Web UI for workflow management
- [ ] Workflow marketplace/sharing
- [ ] Multi-agent orchestration
- [ ] Advanced debugging tools

## 📊 Status

- **Version**: 3.0.0
- **Status**: Refactored from monolithic (2,955 lines → 6 modules)
- **Stability**: Production-ready
- **Maintenance**: Active development

---

**Built with ❤️ for the conversational AI and automation community**
