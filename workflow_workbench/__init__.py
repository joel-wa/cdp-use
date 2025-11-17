#!/usr/bin/env python3
"""
Workflow Workbench - Workflow-Enhanced Conversational Orchestrator

A modular orchestration system for MCP-based browser automation with
workflow learning, execution, and management capabilities.
"""

__version__ = "3.0.0"
__author__ = "Agent-Space Team"

# Core exports
from .config import *
from .models import *
from .workflow_engine import *
from .tool_execution import *
from .workflow_cli import WorkflowCLI

__all__ = [
    # Configuration
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "MCP_SERVER_URL",
    "WORKFLOWS_DIR",
    
    # Core Models
    "WorkflowDefinition",
    "WorkflowStep",
    "WorkflowParameter",
    "SystemState",
    "ToolExecutionResult",
    "ToolExecutionStatus",
    "WorkflowExecutionStatus",
    
    # Workflow Engine
    "WorkflowExecutor",
    "WorkflowLibrary",
    "WorkflowLearningEngine",
    "WorkflowRecordingMode",
    
    # Tool Execution
    "ToolChainOrchestrator",
    "ToolValidator",
    "ErrorRecoveryEngine",
    "ContextManager",
    
    # CLI
    "WorkflowCLI",
]
