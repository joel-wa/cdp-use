#!/usr/bin/env python3
"""
Test script to verify MCP integration in Gemini MCP Orchestrator
"""

import asyncio
import sys
import os

# Add paths for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from gemini_mcp_orchestrator import GeminiMCPOrchestrator
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_mcp_connection():
    """Test MCP connection and tool loading"""
    orchestrator = GeminiMCPOrchestrator()
    
    try:
        print("🧪 Testing MCP integration...")
        
        # Initialize orchestrator
        await orchestrator.initialize()
        
        # Check MCP connection
        if orchestrator.mcp_session:
            print("✅ MCP session established")
        else:
            print("❌ No MCP session")
        
        # Check tools
        print(f"🔧 Available tools: {len(orchestrator.available_tools)}")
        for tool in orchestrator.available_tools[:3]:
            print(f"  - {tool.name}: {tool.description}")
        
        # Test a simple goal if tools are available
        if orchestrator.available_tools:
            print("\n🎯 Testing simple goal execution...")
            result = await orchestrator.run_goal("Take a screenshot")
            print(f"Result status: {result.get('final', {}).get('goal_status', 'Unknown')}")
        
        print("✅ Test completed")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        logger.error(f"Test error: {e}")
    finally:
        await orchestrator.cleanup()

if __name__ == "__main__":
    asyncio.run(test_mcp_connection())
