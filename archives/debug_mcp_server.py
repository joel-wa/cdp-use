#!/usr/bin/env python3

import asyncio
import sys
from mcp.server.stdio import stdio_server
from mcp.server import Server

async def main():
    """Debug MCP server startup"""
    print("🔧 Starting debug MCP server...", file=sys.stderr)
    
    # Create a simple server
    server = Server("debug-server")
    
    @server.list_tools()
    async def list_tools():
        return [
            {
                "name": "test_tool",
                "description": "A test tool",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    
    @server.call_tool()
    async def test_tool(arguments: dict):
        return [{"type": "text", "text": "Test tool executed"}]
    
    print("🔧 Server created with tools", file=sys.stderr)
    
    async with stdio_server() as streams:
        print("🔧 Starting stdio server...", file=sys.stderr)
        from mcp.server import InitializationOptions
        init_options = InitializationOptions(
            server_name="debug-server",
            server_version="1.0.0",
            capabilities=server.get_capabilities()
        )
        await server.run(streams[0], streams[1], init_options)

if __name__ == "__main__":
    asyncio.run(main())