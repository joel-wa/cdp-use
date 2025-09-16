#!/usr/bin/env python3

import asyncio
import os
import sys

# Add the project root to Python path
sys.path.insert(0, r"C:\Users\RanVic\cdp-use")

async def test_browser_automation():
    """Test browser automation with FastMCP"""
    
    # Set up environment for FastMCP server
    os.environ["MCP_SERVER_COMMAND"] = f'"{sys.executable}" "C:\\Users\\RanVic\\cdp-use\\examples\\mcp_browser_control.py" --server-only'
    
    print(f"🌐 Testing browser automation with FastMCP...")
    
    # Import and create orchestrator
    from gemini_mcp_orchestrator import GeminiMCPOrchestrator
    # from LLMOrchestration.gemini_mcp_orchestrator import GeminiMCPOrchestrator
    
    orchestrator = GeminiMCPOrchestrator()
    
    try:
        print("🔌 Initializing orchestrator...")
        await orchestrator.initialize()
        
        if orchestrator.mcp_session:
            print("✅ MCP session available!")
            
            # Test a simple tool call
            print("🧪 Testing get_page_content tool...")
            result = await orchestrator.mcp_session.call_tool("get_page_content", {})
            
            print(f"📄 Tool result type: {type(result)}")
            if hasattr(result, 'content') and result.content:
                content_text = str(result.content[0].text) if result.content else "No content"
                print(f"📄 Content preview: {content_text[:1000]}...")
            
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
    asyncio.run(test_browser_automation())