#!/usr/bin/env python3
"""
Configuration module for Workflow-Enhanced Conversational Orchestrator

Centralized configuration management for all system components.
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =====================================================
# GEMINI API CONFIGURATION
# =====================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# =====================================================
# MCP SERVER CONFIGURATION
# =====================================================

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:12306/mcp")
MCP_SERVER_COMMAND = os.getenv(
    "MCP_SERVER_COMMAND",
    '"C:\\Users\\RanVic\\cdp-use\\.venv\\Scripts\\python.exe" '
    '"C:\\Users\\RanVic\\cdp-use\\examples\\mcp_browser_control.py" --server-only'
)
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")

# =====================================================
# FEATURE FLAGS
# =====================================================

DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ENABLE_VISUAL_CONTEXT = os.getenv("ENABLE_VISUAL_CONTEXT", "true").lower() == "true"
ENABLE_INTERACTIVE_CONTEXT = os.getenv("ENABLE_INTERACTIVE_CONTEXT", "true").lower() == "true"
ENABLE_STREAMING = os.getenv("ENABLE_STREAMING", "true").lower() == "true"
ENABLE_TOOL_VALIDATION = os.getenv("ENABLE_TOOL_VALIDATION", "true").lower() == "true"
ENABLE_ERROR_RECOVERY = os.getenv("ENABLE_ERROR_RECOVERY", "true").lower() == "true"
ENABLE_WORKFLOW_LEARNING = os.getenv("ENABLE_WORKFLOW_LEARNING", "true").lower() == "true"
AUTO_SUGGEST_WORKFLOWS = os.getenv("AUTO_SUGGEST_WORKFLOWS", "true").lower() == "true"

# =====================================================
# EXECUTION LIMITS & TIMEOUTS
# =====================================================

MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", str(1024 * 1024)))  # 1MB
AUTO_SCREENSHOT_INTERVAL = int(os.getenv("AUTO_SCREENSHOT_INTERVAL", "0"))
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "20"))
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "100000"))
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
TOOL_EXECUTION_TIMEOUT = int(os.getenv("TOOL_EXECUTION_TIMEOUT", "60"))

# =====================================================
# WORKFLOW CONFIGURATION
# =====================================================

WORKFLOWS_DIR = os.getenv("WORKFLOWS_DIR", "./workflows")
WORKFLOW_PATTERN_MIN_LENGTH = int(os.getenv("WORKFLOW_PATTERN_MIN_LENGTH", "1"))
WORKFLOW_EXECUTION_MODE = os.getenv("WORKFLOW_EXECUTION_MODE", "interactive")  # interactive, automatic, mixed

# =====================================================
# ERROR HANDLING
# =====================================================

CONTINUE_ON_ERROR = True

# =====================================================
# LOGGING SETUP
# =====================================================

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
