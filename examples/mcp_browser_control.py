#!/usr/bin/env python3
"""
Example usage of the CDP Browser Control MCP Server

This example demonstrates how to run the MCP server that provides browser
automation capabilities for AI agents.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
import os
import platform
import shutil
import tempfile

def find_chrome_command():
    """Return a Chrome/Chromium executable command or None."""
    # Explicit override
    env_path = os.environ.get("CHROME_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    system = platform.system()
    if system == "Windows":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
    elif system == "Darwin":
        c = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.isfile(c):
            return c
    else:
        for name in ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]:
            p = shutil.which(name)
            if p:
                return p
    return None

def start_chrome_with_debugging():
    """Start Chrome with remote debugging enabled (cross-platform)."""
    print("Starting Chrome with remote debugging...")
    chrome_path = find_chrome_command()
    if not chrome_path:
        print("❌ Chrome not found. Set CHROME_PATH env var or install Chrome.")
        return None

    user_data_dir = os.path.join(tempfile.gettempdir(), "chrome-mcp-profile")

    common_flags = [
        "--remote-debugging-port=9222",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows",
        f'--user-data-dir="{user_data_dir}"',
    ]

    cmd = [chrome_path] + common_flags

    try:
        process = subprocess.Popen(
            " ".join(cmd),
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(f"✅ Chrome started (PID {process.pid}) using: {chrome_path}")
        print("🌐 Remote debugging: http://localhost:9222")
        return process
    except Exception as e:
        print(f"❌ Failed to start Chrome: {e}")
        return None

async def main():
    """Main function to demonstrate the MCP server"""
    
    print("=" * 60)
    print("CDP Browser Control MCP Server Example")
    print("=" * 60)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("""
Usage: python examples/mcp_browser_control.py [options]

Options:
  --help              Show this help message
  --list-tools        List all available browser control tools
  --start-chrome      Start Chrome with debugging and exit
  --server-only       Start only the MCP server (assumes Chrome is running)

Examples:
  # Start Chrome and run the server
  python examples/mcp_browser_control.py
  
  # Just start Chrome with debugging
  python examples/mcp_browser_control.py --start-chrome
  
  # List available tools
  python examples/mcp_browser_control.py --list-tools
  
  # Start server only (Chrome must be running on port 9222)  
  python examples/mcp_browser_control.py --server-only

For AI Agents:
  Use this server as an MCP tool by running it and connecting via stdio.
  The server provides browser automation capabilities through these tools:
  - navigate: Go to any URL
  - click_element: Click elements using CSS selectors
  - type_text: Type text into focused elements
  - take_screenshot: Capture page screenshots
  - execute_javascript: Run JavaScript code
  - get_page_content: Extract HTML content
  - wait_for_element: Wait for elements to appear
        """)
        return
    
    if len(sys.argv) > 1 and sys.argv[1] == "--list-tools":
        from cdp_use.mcp_server import TOOLS
        print("Available Browser Control Tools:")
        print("-" * 40)
        for i, tool in enumerate(TOOLS, 1):
            print(f"{i}. {tool.name}")
            print(f"   Description: {tool.description}")
            required_params = tool.inputSchema.get("required", [])
            if required_params:
                print(f"   Required: {', '.join(required_params)}")
            print()
        return
    
    if len(sys.argv) > 1 and sys.argv[1] == "--start-chrome":
        chrome_process = start_chrome_with_debugging()
        if chrome_process:
            print("Chrome is running. You can now start the MCP server with:")
            print("python examples/mcp_browser_control.py --server-only")
        return
    
    server_only = len(sys.argv) > 1 and sys.argv[1] == "--server-only"
    
    chrome_process = None
    if not server_only:
        # Start Chrome with debugging
        chrome_process = start_chrome_with_debugging()
        if not chrome_process:
            print("⚠️  Continuing without starting Chrome...")
            print("📝 Make sure Chrome is running with: --remote-debugging-port=9222")
        else:
            # Wait a moment for Chrome to start
            await asyncio.sleep(2)
    
    print("\n🚀 Starting MCP Browser Control Server...", file=sys.stderr)
    print("📡 Server will communicate via stdin/stdout", file=sys.stderr)
    print("🔧 Available tools: navigate, click_element, type_text, take_screenshot, execute_javascript, get_page_content, wait_for_element", file=sys.stderr)
    print("📊 Available resources: browser://current-page, browser://page-source", file=sys.stderr)
    print("\n" + "="*50, file=sys.stderr)
    print("Server is ready for MCP client connections!", file=sys.stderr)
    print("="*50, file=sys.stderr)
    
    try:
        # Import and start the MCP server
        from cdp_use.mcp_server import BrowserMCPServer
        
        server = BrowserMCPServer()
        await server.serve()
        
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"\n❌ Server error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        # Clean up Chrome process
        if chrome_process:
            print("🧹 Cleaning up Chrome process...", file=sys.stderr)
            chrome_process.terminate()
            chrome_process.wait()

if __name__ == "__main__":
    asyncio.run(main())