#!/usr/bin/env python3

import asyncio
import os
import sys

# Add the project root to Python path
sys.path.insert(0, r"C:\Users\RanVic\cdp-use")

async def test_fastmcp_orchestrator():
    """Test the FastMCP server with the Gemini orchestrator"""
    
    # Set up environment for FastMCP server
    os.environ["MCP_SERVER_COMMAND"] = f'"{sys.executable}" "C:\\Users\\RanVic\\cdp-use\\fastmcp_browser_server.py"'
    
    print(f"🧪 Testing FastMCP with orchestrator...")
    print(f"📋 MCP_SERVER_COMMAND: {os.environ['MCP_SERVER_COMMAND']}")
    
    # Import and create orchestrator
    from LLMOrchestration.gemini_mcp_orchestrator import GeminiMCPOrchestrator
    
    orchestrator = GeminiMCPOrchestrator()
    
    try:
        print("🔌 Initializing orchestrator...")
        await orchestrator.initialize()
        
        print("✅ Orchestrator initialized!")
        
        # List available tools
        if orchestrator.mcp_session:
            tools = await orchestrator.mcp_session.list_tools()
            print(f"📋 Found {len(tools.tools)} tools:")
            for tool in tools.tools:
                print(f"  - {tool.name}")
        else:
            print("❌ No MCP session available")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        if orchestrator:
            try:
                await orchestrator.cleanup()
            except:
                pass

if __name__ == "__main__":
    asyncio.run(test_fastmcp_orchestrator())