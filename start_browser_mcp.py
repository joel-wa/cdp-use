#!/usr/bin/env python3
"""
Seamless CDP Browser MCP Server Startup

This script automatically:
1. Starts Chrome with debugging if needed
2. Starts the MCP server
3. Handles cleanup on exit

Usage:
  python start_browser_mcp.py           # Start Chrome + MCP server
  python start_browser_mcp.py --help    # Show usage
"""

import subprocess
import sys
import time
import json
import urllib.request
import urllib.error
import atexit
import signal
import os

try:
    import dotenv
    dotenv.load_dotenv()
except ImportError:
    pass # dotenv not installed, assume env vars are set manually

CHROME_PATH = os.getenv("GOOGLE_CHROME_PATH", "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe")
USER_PROFILE = os.getenv("USER_PROFILE_PATH") or "C:\\temp\\chrome_mcp_debug"

def is_chrome_running():
    """Check if Chrome debugging is already available"""
    try:
        with urllib.request.urlopen('http://localhost:9222/json', timeout=2) as response:
            if response.status == 200:
                data = response.read().decode()
                tabs = json.loads(data)
                print(f"[OK] Chrome already running with {len(tabs)} tab(s)")
                return True
    except:
        return False
    return False

def start_chrome_debug():
    """Start Chrome with debugging"""
    import platform
    
    # Get additional arguments from environment
    extra_args = [arg for arg in os.getenv("CHROME_ARGS", "").split() if arg]
    
    # Determine Chrome path
    chrome_path = None
    if os.getenv("GOOGLE_CHROME_PATH"):
        chrome_path = os.getenv("GOOGLE_CHROME_PATH")
    elif platform.system() == "Windows":
        chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    else:
        # macOS/Linux
        chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if not os.path.exists(chrome_path):
            chrome_path = "google-chrome"  # Linux default

    cmd = [
        chrome_path,
        "--remote-debugging-port=9222",
        f"--user-data-dir={USER_PROFILE}",
        "--no-first-run",
        "--no-default-browser-check"
    ] + extra_args
    
    try:
        print(f"[START] Starting Chrome with debugging... (Path: {chrome_path})")
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Wait for Chrome to be ready
        for i in range(15):
            time.sleep(1)
            if is_chrome_running():
                print(f"[OK] Chrome ready (PID: {process.pid})")
                return process
            if i == 0:
                print("⏳ Waiting for Chrome to start...")
        
        print("[ERROR] Chrome started but debugging not accessible")
        return None
        
    except Exception as e:
        print(f"[ERROR] Failed to start Chrome: {e}")
        return None

def start_mcp_server():
    """Start the MCP server"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    server_script = os.path.join(script_dir, "examples", "mcp_browser_control.py")
    
    # Use virtual environment if available
    venv_python = os.path.join(script_dir, ".venv", "Scripts", "python.exe")
    python_executable = venv_python if os.path.exists(venv_python) else sys.executable
    
    # Use -u for unbuffered output to ensure logs are visible in Docker
    cmd = [python_executable, "-u", server_script, "--server-only"]
    
    print("[START] Starting MCP Browser Control Server...")
    print("[INFO] Server will communicate via stdin/stdout")
    print("[INFO] Connect using an MCP client or press Ctrl+C to stop")
    print("="*60)
    
    try:
        # Set PYTHONPATH to include the current directory
        env = os.environ.copy()
        env['PYTHONPATH'] = script_dir + os.pathsep + env.get('PYTHONPATH', '')
        
        # Run and wait
        result = subprocess.run(cmd, check=False, env=env, cwd=script_dir)
        if result.returncode != 0:
            print(f"\n[ERROR] Server exited with code {result.returncode}")
        else:
            print(f"\n[INFO] Server exited cleanly (code 0)")
            
    except KeyboardInterrupt:
        print("\n[STOP] Server stopped by user")
    except Exception as e:
        print(f"\n[ERROR] Server error: {e}")

def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print(__doc__)
        return
    
    print("=" * 60)
    print("[INFO] CDP Browser MCP Server - Seamless Startup")
    print("=" * 60)
    
    chrome_process = None
    
    try:
        # Check if Chrome is already running
        if not is_chrome_running():
            chrome_process = start_chrome_debug()
            if not chrome_process:
                print("⚠️  Could not start Chrome. Please start manually:")
                print("   chrome --remote-debugging-port=9222 --user-data-dir=C:\\temp\\chrome_debug")
                response = input("Continue without auto-starting Chrome? (y/N): ")
                if response.lower() != 'y':
                    return
        
        # Register cleanup function
        if chrome_process:
            def cleanup():
                print("\n🧹 Cleaning up Chrome process...")
                try:
                    chrome_process.terminate()
                    chrome_process.wait(timeout=5)
                except:
                    chrome_process.kill()
            
            atexit.register(cleanup)
            signal.signal(signal.SIGINT, lambda s, f: cleanup() or sys.exit(0))
        
        # Start MCP server
        start_mcp_server()
        
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
    finally:
        if chrome_process:
            try:
                chrome_process.terminate()
                chrome_process.wait(timeout=5)
            except:
                chrome_process.kill()

if __name__ == "__main__":
    main()