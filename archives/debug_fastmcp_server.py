#!/usr/bin/env python3

import sys
from mcp.server import FastMCP

# Create a FastMCP server
server = FastMCP("debug-server")

@server.tool()
def test_tool() -> str:
    """A simple test tool"""
    return "Test tool executed"

if __name__ == "__main__":
    print("🔧 Starting FastMCP debug server...", file=sys.stderr)
    server.run()