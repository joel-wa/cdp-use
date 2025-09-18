#!/usr/bin/env python3
"""
Quick start script for the CDP Browser Control MCP Server

This provides a simple entry point to run the MCP server.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from cdp_use.mcp_server import main

if __name__ == "__main__":
    asyncio.run(main())