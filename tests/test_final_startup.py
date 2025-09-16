#!/usr/bin/env python3
"""
Test script to verify the seamless startup process works correctly
"""
import subprocess
import sys
import time
import os

def test_startup():
    """Test the seamless startup process"""
    print("[TEST] Testing seamless Chrome + MCP server startup...")
    
    # Change to the project directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    
    try:
        # Start the process
        process = subprocess.Popen(
            [sys.executable, "start_browser_mcp.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give it a few seconds to start up
        time.sleep(3)
        
        # Check if process is still running
        if process.poll() is None:
            print("[OK] Server started successfully and is running")
            
            # Terminate the process
            process.terminate()
            try:
                process.wait(timeout=5)
                print("[OK] Server stopped cleanly")
            except subprocess.TimeoutExpired:
                process.kill()
                print("[WARN] Server had to be force-killed")
                
            return True
        else:
            # Process has terminated, check output
            stdout, stderr = process.communicate()
            print(f"[ERROR] Server process terminated early")
            if stderr:
                print(f"[ERROR] stderr: {stderr}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Failed to start server: {e}")
        return False

if __name__ == "__main__":
    success = test_startup()
    print(f"\n[RESULT] Test {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)