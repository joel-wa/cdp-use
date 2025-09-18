#!/usr/bin/env python3

import asyncio
import subprocess
import sys
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

async def test_fastmcp_browser():
    """Test the FastMCP browser server"""
    
    print("🧪 Testing FastMCP browser server...")
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[r"C:\Users\RanVic\cdp-use\fastmcp_browser_server.py", "--server-only"]
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
                
                # Test a simple tool that doesn't require browser connection
                print("🔧 Testing get_page_content...")
                result = await session.call_tool("get_page_content", {})
                print(f"📄 Result type: {type(result)}")
                if hasattr(result, 'content'):
                    print(f"📄 Content preview: {str(result.content)[:100]}...")
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_fastmcp_browser())