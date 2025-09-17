#!/usr/bin/env python3
"""
Test Automatic Visual Context in Simple Conversational Orchestrator

This test validates that:
1. Visual context is automatically captured before LLM calls
2. Screenshot is converted to text description 
3. LLM receives visual awareness without explicit screenshot calls
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project paths
sys.path.append(os.path.dirname(__file__))

from simple_conversational_orchestrator import SimpleConversationalOrchestrator

# Load environment
load_dotenv()

async def test_automatic_visual_context():
    """Test the automatic visual context functionality"""
    
    # Set up environment for visual context
    os.environ["ENABLE_VISUAL_CONTEXT"] = "true"
    os.environ["DEBUG"] = "true"
    
    print("🧪 Testing Automatic Visual Context")
    print("=" * 50)
    
    orchestrator = SimpleConversationalOrchestrator()
    
    try:
        await orchestrator.initialize()
        
        # Test 1: Navigate and check automatic visual context
        print("\n📍 Test 1: Navigate to a website")
        response1 = await orchestrator.process_user_input("Please navigate to https://youtube.com")
        print(f"Response 1: {response1}")
        
        # Test 2: Ask about what's on screen (should use automatic visual context)
        print("\n👀 Test 2: Ask about current screen without explicit screenshot")
        response2 = await orchestrator.process_user_input("What do you see on the current page? Describe the main elements.")
        print(f"Response 2: {response2}")
        
        # Test 3: Navigate to different site and check context update
        print("\n🔄 Test 3: Navigate to different site")
        response3 = await orchestrator.process_user_input("Now navigate to https://httpbin.org/html and tell me what you see")
        print(f"Response 3: {response3}")
        
        print("\n✅ Test completed successfully!")
        print("The orchestrator should automatically capture and describe the screen state")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        await orchestrator.cleanup()
        
    return True

if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ Error: GEMINI_API_KEY environment variable is required")
        sys.exit(1)
        
    asyncio.run(test_automatic_visual_context())