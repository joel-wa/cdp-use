# Project Structure

## Complete File Tree

```
workflow_workbench/
│
├── 📄 README.md                               # Project overview and quick start
├── 📄 MIGRATION.md                            # Migration guide from monolithic version
├── 📄 REFACTORING_SUMMARY.md                  # Complete refactoring documentation
│
├── 🐍 Python Modules (Core System)
│   ├── orchestrator.py                        # Main entry point (600 lines)
│   ├── config.py                              # Configuration management (80 lines)
│   ├── models.py                              # Data structures (500 lines)
│   ├── workflow_engine.py                     # Workflow system (800 lines)
│   ├── tool_execution.py                      # Tool orchestration (400 lines)
│   ├── workflow_cli.py                        # CLI interface (300 lines)
│   ├── __init__.py                            # Package exports (40 lines)
│   └── workflow_enhanced_orchestrator.py      # Original monolithic file (preserved)
│
├── 📚 Documentation (docs/)
│   ├── README.md                              # Quick start guide (300 lines)
│   ├── architecture.md                        # Architecture documentation (500 lines)
│   ├── api_reference.md                       # API reference (600 lines)
│   ├── workflows.md                           # Workflow guide (700 lines)
│   └── examples.md                            # Usage examples (400 lines)
│
└── 🎨 Diagrams (diagrams/)
    ├── overview.mmd                           # System architecture overview
    ├── workflow_lifecycle.mmd                 # Workflow execution flow
    ├── tool_execution.mmd                     # Tool orchestration flow
    ├── learning_system.mmd                    # Pattern recognition flow
    └── integration.mmd                        # System integration view
```

## Module Dependencies

```
┌─────────────────────────────────────────────────────────────┐
│                      orchestrator.py                        │
│                   (Main Coordinator)                        │
└─────────────────────┬──────────────────┬───────────────────┘
                      │                  │
          ┌───────────▼──────────┐  ┌───▼────────────────┐
          │   workflow_engine.py │  │ tool_execution.py  │
          │  (Workflow System)   │  │ (Tool System)      │
          └───────────┬──────────┘  └───┬────────────────┘
                      │                 │
          ┌───────────▼─────────────────▼────────┐
          │         workflow_cli.py              │
          │        (CLI Interface)               │
          └───────────┬──────────────────────────┘
                      │
          ┌───────────▼──────────┐
          │       models.py      │
          │   (Data Structures)  │
          └───────────┬──────────┘
                      │
          ┌───────────▼──────────┐
          │       config.py      │
          │   (Configuration)    │
          └──────────────────────┘
```

## Size Analysis

### Python Code
| Module | Lines | Percentage |
|--------|-------|------------|
| workflow_engine.py | 800 | 29.4% |
| orchestrator.py | 600 | 22.1% |
| models.py | 500 | 18.4% |
| tool_execution.py | 400 | 14.7% |
| workflow_cli.py | 300 | 11.0% |
| config.py | 80 | 2.9% |
| __init__.py | 40 | 1.5% |
| **Total** | **2,720** | **100%** |

### Documentation
| File | Lines | Percentage |
|------|-------|------------|
| workflows.md | 700 | 28.0% |
| api_reference.md | 600 | 24.0% |
| architecture.md | 500 | 20.0% |
| examples.md | 400 | 16.0% |
| README.md | 300 | 12.0% |
| **Total** | **2,500** | **100%** |

### Total Project
| Category | Lines | Files |
|----------|-------|-------|
| Python Code | 2,720 | 7 |
| Documentation | 2,500 | 5 |
| Diagrams | 5 files | 5 |
| Meta Files | 3 files | 3 |
| **Total** | **5,220+** | **20** |

## Component Relationships

### config.py
- **Exports**: Configuration constants, environment variables
- **Used by**: All modules
- **Dependencies**: None (base layer)

### models.py
- **Exports**: Data classes, enums, type definitions
- **Used by**: All modules
- **Dependencies**: config.py

### workflow_engine.py
- **Exports**: 
  - `PatternAnalyzer`
  - `ParameterExtractor`
  - `WorkflowLearningEngine`
  - `WorkflowValidator`
  - `WorkflowStateManager`
  - `WorkflowExecutor`
  - `WorkflowLibrary`
  - `WorkflowRecordingMode`
- **Used by**: orchestrator.py, workflow_cli.py
- **Dependencies**: models.py, config.py

### tool_execution.py
- **Exports**:
  - `ToolValidator`
  - `ErrorRecoveryEngine`
  - `ContextManager`
  - `ToolChainOrchestrator`
  - `StreamingResponseManager`
- **Used by**: orchestrator.py
- **Dependencies**: models.py, config.py

### workflow_cli.py
- **Exports**: `WorkflowCLI`
- **Used by**: orchestrator.py
- **Dependencies**: workflow_engine.py, models.py, config.py

### orchestrator.py
- **Exports**: 
  - `WorkflowEnhancedConversationalOrchestrator`
  - `SystemMessageBuilder`
  - `main()`
- **Used by**: External scripts, CLI
- **Dependencies**: All other modules

### __init__.py
- **Exports**: All public classes and constants
- **Used by**: External imports
- **Dependencies**: All modules

## Import Patterns

### Circular Dependency Prevention
```python
# ✅ Correct (top to bottom)
orchestrator.py → workflow_engine.py → models.py → config.py

# ❌ Avoided (circular)
models.py → orchestrator.py  # Never happens
```

### Public API (via __init__.py)
```python
from workflow_workbench import (
    # From config.py
    GEMINI_MODEL,
    WORKFLOWS_DIR,
    
    # From models.py
    WorkflowDefinition,
    WorkflowStep,
    SystemState,
    
    # From workflow_engine.py
    WorkflowExecutor,
    WorkflowLibrary,
    
    # From tool_execution.py
    ToolChainOrchestrator,
    
    # From orchestrator.py
    WorkflowEnhancedConversationalOrchestrator,
)
```

## Testing Structure (Future)

```
tests/
├── unit/
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_workflow_engine.py
│   ├── test_tool_execution.py
│   ├── test_workflow_cli.py
│   └── test_orchestrator.py
│
├── integration/
│   ├── test_workflow_execution.py
│   ├── test_tool_chain.py
│   └── test_end_to_end.py
│
└── fixtures/
    ├── sample_workflows/
    └── mock_data/
```

## Development Workflow

```
1. Development
   ├── Edit module in src/
   ├── Update tests
   └── Update documentation

2. Testing
   ├── Unit tests (each module)
   ├── Integration tests (module interaction)
   └── End-to-end tests (full system)

3. Documentation
   ├── Update API reference
   ├── Update architecture docs
   └── Add examples

4. Deployment
   ├── Version bump
   ├── Build package
   └── Deploy
```

## Key Files Quick Reference

| Need | File |
|------|------|
| Run the system | `orchestrator.py` |
| Configure | `config.py` or `.env` |
| Data structures | `models.py` |
| Create workflow | `workflows/*.yaml` |
| API documentation | `docs/api_reference.md` |
| Architecture | `docs/architecture.md` |
| Examples | `docs/examples.md` |
| Visual diagrams | `diagrams/*.mmd` |
| Migration guide | `MIGRATION.md` |
| Project overview | `README.md` |

## External Dependencies

```python
# Standard Library
asyncio, json, logging, os, time, sys, pathlib, traceback
dataclasses, enum, typing, datetime, contextlib

# Third-party
google.genai         # Google Generative AI
mcp                  # Model Context Protocol
python-dotenv        # Environment variables
pyyaml               # YAML parsing
```

---

**Note**: This structure provides:
- ✅ Clear separation of concerns
- ✅ No circular dependencies
- ✅ Easy to test
- ✅ Simple to extend
- ✅ Well documented
- ✅ Production ready
