#!/usr/bin/env python3

import asyncio
import subprocess
import sys
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

async def test_fastmcp_connection():
    """Test connection to FastMCP debug server"""
    
    print("🧪 Testing FastMCP server connection...")
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[r"C:\Users\RanVic\cdp-use\debug_fastmcp_server.py"]
    )
    
    print(f"Command: {server_params.command}")
    print(f"Args: {server_params.args}")
    
    try:
        print("📡 Starting stdio transport...")
        async with stdio_client(server_params) as (read, write):
            print("✅ Got stdio streams")
            
            print("🔗 Creating MCP session...")
            async with ClientSession(read, write) as session:
                print("✅ Created session")
                
                print("🚀 Initializing session...")
                await session.initialize()
                print("✅ Session initialized!")
                
                print("📋 Listing tools...")
                tools = await session.list_tools()
                print(f"✅ Found {len(tools.tools)} tools:")
                for tool in tools.tools:
                    print(f"  - {tool.name}: {tool.description}")
                
                print("🔧 Calling test tool...")
                result = await session.call_tool("test_tool", {})
                print(f"✅ Tool result: {result}")
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_fastmcp_connection())