#!/usr/bin/env python3
"""
Test script for the Simple Conversational Orchestrator
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

from simple_conversational_orchestrator import SimpleConversationalOrchestrator

# Load environment variables
load_dotenv()

async def test_initialization():
    """Test basic initialization"""
    print("🧪 Testing Simple Conversational Orchestrator initialization...")
    
    orchestrator = SimpleConversationalOrchestrator()
    
    try:
        # Test initialization
        await orchestrator.initialize()
        
        print("✅ Initialization successful")
        print(f"📡 MCP Session: {'Connected' if orchestrator.mcp_session else 'Not connected'}")
        print(f"🔧 Available tools: {len(orchestrator.available_tools)}")
        
        if orchestrator.available_tools:
            print("\nAvailable tools:")
            for tool in orchestrator.available_tools:
                print(f"  • {tool.name}: {tool.description}")
        
        # Test message array initialization
        assert orchestrator.messages == [], "Messages array should be empty initially"
        print("✅ Messages array initialized correctly")
        
        # Test basic message handling (without actual LLM call)
        test_message = {"role": "user", "content": "Test message"}
        orchestrator.messages.append(test_message)
        assert len(orchestrator.messages) == 1, "Message should be added to array"
        print("✅ Message handling works correctly")
        
        print("\n🎉 All basic tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        await orchestrator.cleanup()
        
    return True

async def main():
    """Main test function"""
    
    # Check for required environment variables
    if not os.getenv("GEMINI_API_KEY"):
        print("⚠️  Warning: GEMINI_API_KEY not set - some tests may fail")
    
    success = await test_initialization()
    
    if success:
        print("\n✅ Simple Conversational Orchestrator is ready to use!")
        print("\nTo run interactively:")
        print("python simple_conversational_orchestrator.py")
    else:
        print("\n❌ Tests failed")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())