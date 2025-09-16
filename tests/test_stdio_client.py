#!/usr/bin/env python3
"""
Test the stdio client connection to the CDP MCP server
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the LLMOrchestration directory to the path
sys.path.append(str(Path(__file__).parent / "LLMOrchestration"))

from gemini_mcp_orchestrator import GeminiMCPOrchestrator

async def test_stdio_connection():
    """Test connecting to the CDP MCP server via stdio"""
    
    # Set environment variables for stdio transport
    os.environ["MCP_TRANSPORT"] = "stdio"
    os.environ["MCP_SERVER_COMMAND"] = "python examples/mcp_browser_control.py --server-only"
    os.environ["GEMINI_API_KEY"] = "test-key"  # Dummy key for connection test
    
    print("🧪 Testing stdio connection to CDP MCP server...")
    
    orchestrator = GeminiMCPOrchestrator()
    
    try:
        await orchestrator.initialize()
        
        if orchestrator.mcp_session:
            print("✅ Successfully connected via stdio!")
            print(f"🔧 Available tools: {len(orchestrator.available_tools)}")
            
            # List the tools
            for i, tool in enumerate(orchestrator.available_tools, 1):
                print(f"  {i}. {tool.name}: {tool.description}")
            
        else:
            print("❌ Failed to connect via stdio")
            
    except Exception as e:
        print(f"❌ Error during connection test: {e}")
    
    finally:
        await orchestrator.cleanup()

if __name__ == "__main__":
    asyncio.run(test_stdio_connection())