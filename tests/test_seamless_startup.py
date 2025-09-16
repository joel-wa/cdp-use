#!/usr/bin/env python3

import subprocess
import sys
import time
import os

def test_seamless_startup():
    """Test the seamless startup process"""
    print("🧪 Testing seamless CDP Browser MCP startup...")
    
    # Kill any existing Chrome
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], 
                      capture_output=True, check=False)
        print("🧹 Cleared any existing Chrome processes")
    except:
        pass
    
    # Test the startup script
    script_path = os.path.join(os.path.dirname(__file__), 'examples', 'mcp_browser_control.py')
    
    print("🚀 Starting enhanced MCP server...")
    print("   This should automatically start Chrome and then the server")
    print("   Press Ctrl+C after you see 'Server is ready' message")
    print("=" * 60)
    
    try:
        # Run for a limited time to show startup
        process = subprocess.Popen([
            sys.executable, script_path
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
        universal_newlines=True, bufsize=1)
        
        # Monitor output for a few seconds
        start_time = time.time()
        while time.time() - start_time < 15:  # Monitor for 15 seconds
            output = process.stdout.readline()
            if output:
                print(output.rstrip())
                if "Server is ready" in output:
                    print("\n✅ Startup completed successfully!")
                    break
        
        # Clean shutdown
        process.terminate()
        process.wait(timeout=5)
        
    except KeyboardInterrupt:
        print("\n🛑 Test stopped by user")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
    
    print("\n📋 Summary:")
    print("   - Enhanced startup handles Chrome automatically")
    print("   - Better error messages when Chrome not available") 
    print("   - Seamless integration for MCP clients")
    print("   - Use 'python start_browser_mcp.py' for full experience")

if __name__ == "__main__":
    test_seamless_startup()