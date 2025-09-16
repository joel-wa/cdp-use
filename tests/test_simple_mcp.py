#!/usr/bin/env python3
"""
Simple test to connect to MCP server via stdio
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, ".")

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

async def test_mcp_connection():
    """Simple test of MCP stdio connection"""
    
    print("🧪 Testing direct MCP stdio connection...")
    
    # Configure server parameters
    current_dir = Path(__file__).parent
    python_exe = current_dir / ".venv" / "Scripts" / "python.exe"
    mcp_script = current_dir / "examples" / "mcp_browser_control.py"
    
    server_params = StdioServerParameters(
        command=str(python_exe),
        args=[str(mcp_script), "--server-only"]
    )
    
    print(f"Command: {server_params.command}")
    print(f"Args: {server_params.args}")
    
    try:
        # Start the stdio transport
        print("📡 Starting stdio transport...")
        async with stdio_client(server_params) as (read, write):
            print("✅ Got stdio streams")
            
            # Create MCP session
            print("🔗 Creating MCP session...")
            async with ClientSession(read, write) as session:
                print("✅ Created session")
                
                # Initialize session
                print("🚀 Initializing session...")
                await session.initialize()
                print("✅ Session initialized!")
                
                # List tools
                print("📋 Listing available tools...")
                tools_response = await session.list_tools()
                print(f"✅ Found {len(tools_response.tools) if tools_response.tools else 0} tools")
                
                if tools_response.tools:
                    for tool in tools_response.tools:
                        print(f"   - {tool.name}: {tool.description}")
                
                print("🎉 Test successful!")
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mcp_connection())