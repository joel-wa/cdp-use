#!/usr/bin/env python3

import asyncio
import subprocess
import sys
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

async def test_examples_server():
    """Test the examples MCP browser server"""
    
    print("🧪 Testing examples/mcp_browser_control.py server...")
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[r"C:\Users\RanVic\cdp-use\examples\mcp_browser_control.py", "--server-only"]
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
                
                # Test a simple tool call
                print("🧪 Testing get_page_content...")
                result = await session.call_tool("get_page_content", {})
                
                if hasattr(result, 'content') and result.content:
                    content_text = str(result.content[0].text) if result.content else "No content"
                    print(f"📄 Content preview: {content_text[:100]}...")
                    print("✅ Tool call successful!")
                else:
                    print(f"📄 Result: {result}")
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_examples_server())