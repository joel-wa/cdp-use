#!/usr/bin/env python3
"""
Example usage of the CDP Browser Control MCP Server.

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
import time
import urllib.request
import urllib.error

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
        print("[ERROR] Chrome not found. Set CHROME_PATH env var or install Chrome.")
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
        print(f"[OK] Chrome started (PID {process.pid}) using: {chrome_path}")
        print("[INFO] Remote debugging: http://localhost:9222")
        return process
    except Exception as e:
        print(f"[ERROR] Failed to start Chrome: {e}")
        return None

def is_chrome_debugging_ready(port=9222, timeout=10):
    """Check if Chrome debugging port is accessible"""
    for attempt in range(timeout):
        try:
            with urllib.request.urlopen(f'http://localhost:{port}/json', timeout=1) as response:
                if response.status == 200:
                    data = response.read().decode()
                    tabs = json.loads(data)
                    print(f"[OK] Chrome debugging ready with {len(tabs)} tab(s)", file=sys.stderr)
                    return True
        except (urllib.error.URLError, urllib.error.HTTPError, ConnectionRefusedError):
            if attempt == 0:
                print(f"[WAIT] Waiting for Chrome debugging on port {port}...", file=sys.stderr)
            time.sleep(1)
    return False

def ensure_chrome_running():
    """Ensure Chrome is running with debugging, start if necessary"""
    # First check if Chrome is already running with debugging
    if is_chrome_debugging_ready(timeout=2):
        print("[INFO] Chrome debugging already available", file=sys.stderr)
        return True
    
    print("[START] Starting Chrome with debugging...", file=sys.stderr)
    chrome_process = start_chrome_with_debugging()
    
    if not chrome_process:
        print("[ERROR] Failed to start Chrome", file=sys.stderr)
        return False
    
    # Wait for Chrome to be ready
    if is_chrome_debugging_ready(timeout=15):
        return True
    else:
        print("[ERROR] Chrome started but debugging port not accessible", file=sys.stderr)
        print("[INFO] Try manually starting Chrome with: chrome --remote-debugging-port=9222", file=sys.stderr)
        return False

def main():
    """Main function to demonstrate the MCP server"""
    chrome_process = None
    
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
  --transport=MODE    Transport mode: stdio (default) or sse
  --port=PORT         Port for SSE transport (default: 8000)

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
    
    # Ensure Chrome is running with debugging (unless server-only mode)
    if not server_only:
        if not ensure_chrome_running():
            print("[WARN] Continuing without Chrome - some tools may not work", file=sys.stderr)
            print("[INFO] You can manually start Chrome with:", file=sys.stderr)
            print("   chrome --remote-debugging-port=9222 --user-data-dir=C:\\temp\\chrome_debug", file=sys.stderr)
    
    print("\n[START] Starting MCP Browser Control Server...", file=sys.stderr)
    print("[INFO] Server will communicate via stdin/stdout", file=sys.stderr)
    print("[INFO] Available tools: navigate, click_element, type_text, take_screenshot, execute_javascript, get_page_content, wait_for_element", file=sys.stderr)
    print("[INFO] Available resources: browser://current-page, browser://page-source", file=sys.stderr)
    print("\n" + "="*50, file=sys.stderr)
    print("Server is ready for MCP client connections!", file=sys.stderr)
    print("="*50, file=sys.stderr)
    
    try:
        # Import and start the FastMCP server
        from cdp_use.mcp_server_fastmcp import BrowserFastMCPServer
        
        # Remove arguments handled by this script so FastMCP doesn't see them
        # We don't clear sys.argv completely to preserve script name etc.
        # Remove arguments handled by this script so FastMCP doesn't see them
        # We don't clear sys.argv completely to preserve script name etc.
        if "--server-only" in sys.argv:
            sys.argv.remove("--server-only")
            
        transport = "stdio"
        port = 8000
        
        # Simple manual argument parsing to avoid argparse conflicts with other tools
        args_to_remove = []
        for arg in sys.argv:
            if arg.startswith("--transport="):
                transport = arg.split("=")[1]
                args_to_remove.append(arg)
            elif arg.startswith("--port="):
                try:
                    port = int(arg.split("=")[1])
                    args_to_remove.append(arg)
                except ValueError:
                    print(f"[WARN] Invalid port: {arg}, using 8000", file=sys.stderr)

        for arg in args_to_remove:
            sys.argv.remove(arg)
        
        server = BrowserFastMCPServer()
        server.run(transport=transport, port=port)
        
    except KeyboardInterrupt:
        print("\n[STOP] Server stopped by user", file=sys.stderr)
    except Exception as e:
        print(f"\n[ERROR] Server error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        # Clean up Chrome process
        if chrome_process:
            print("[CLEANUP] Cleaning up Chrome process...", file=sys.stderr)
            chrome_process.terminate()
            chrome_process.wait()

if __name__ == "__main__":
    main()