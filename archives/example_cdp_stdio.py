#!/usr/bin/env python3
"""
Example: Using Gemini MCP Orchestrator with CDP Browser Control Server

This example demonstrates how to connect the Gemini MCP Orchestrator to the 
CDP browser control server using stdio transport.

Prerequisites:
1. Set your GEMINI_API_KEY environment variable
2. Make sure Chrome is installed and accessible
3. Install required dependencies: pip install -r requirements.txt

Usage:
    python example_cdp_stdio.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add LLMOrchestration to path
sys.path.insert(0, str(Path(__file__).parent / "LLMOrchestration"))

async def main():
    """Main function to run the CDP browser control example"""
    
    # Check for required environment variables
    api_key = os.getenv("GEMINI_API_KEY","AIzaSyDQQE7g0ae-5XHP0-1jNd8sueAH6xW7ok0")
    if not api_key:
        print("❌ Error: Please set GEMINI_API_KEY environment variable")
        print("   You can get an API key from: https://makersuite.google.com/app/apikey")
        return
    
    # Configure for stdio transport with CDP server
    os.environ["MCP_TRANSPORT"] = "stdio"
    
    # Use absolute path for the Python executable
    current_dir = Path(__file__).parent
    python_exe = current_dir / ".venv" / "Scripts" / "python.exe"
    mcp_script = current_dir / "examples" / "mcp_browser_control.py"
    
    os.environ["MCP_SERVER_COMMAND"] = f'"{python_exe}" "{mcp_script}" --server-only'
    os.environ["DEBUG"] = "true"  # Enable debug logging
    
    print("🚀 CDP Browser Control with Gemini MCP Orchestrator")
    print("=" * 60)
    print("📡 Transport: stdio")
    print("🔧 MCP Server: CDP Browser Control Server") 
    print("🤖 AI Model: Gemini")
    print("=" * 60)
    
    try:
        from gemini_mcp_orchestrator import GeminiMCPOrchestrator
        
        orchestrator = GeminiMCPOrchestrator()
        
        print("\n🔗 Initializing connection...")
        await orchestrator.initialize()
        
        if orchestrator.mcp_session:
            print("✅ Successfully connected to CDP MCP server!")
            print(f"🔧 Available browser tools: {len(orchestrator.available_tools)}")
            
            # Show available tools
            print("\nAvailable browser control tools:")
            for i, tool in enumerate(orchestrator.available_tools, 1):
                print(f"  {i}. {tool.name}: {tool.description}")
            
            print("\n🎯 Starting interactive session...")
            print("You can now give commands like:")
            print("- Navigate to google.com")
            print("- Take a screenshot of the current page")
            print("- Search for 'Python tutorials'")
            print("- Click the search button")
            
            # Start interactive session
            await orchestrator.run_interactive_session()
            
        else:
            print("❌ Failed to connect to CDP MCP server")
            print("💡 Make sure the CDP server can be started with:")
            print("   python examples/mcp_browser_control.py --server-only")
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure you're running from the cdp-use directory")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            await orchestrator.cleanup()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(main())