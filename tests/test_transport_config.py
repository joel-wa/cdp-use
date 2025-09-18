#!/usr/bin/env python3
"""
Quick test to validate stdio transport configuration
"""

import os
import sys

# Test just the import and basic configuration parsing
sys.path.insert(0, "LLMOrchestration")

def test_configuration():
    """Test the configuration parsing without connecting"""
    
    print("🧪 Testing MCP transport configuration...")
    
    # Set test environment variables
    test_configs = [
        {
            "name": "HTTP Transport",
            "env": {
                "MCP_TRANSPORT": "http",
                "MCP_SERVER_URL": "http://127.0.0.1:12306/mcp"
            }
        },
        {
            "name": "Stdio Transport", 
            "env": {
                "MCP_TRANSPORT": "stdio",
                "MCP_SERVER_COMMAND": "python examples/mcp_browser_control.py --server-only"
            }
        },
        {
            "name": "Auto-detect (stdio)",
            "env": {
                "MCP_TRANSPORT": "auto",
                "MCP_SERVER_COMMAND": "python examples/mcp_browser_control.py --server-only"
            }
        },
        {
            "name": "Auto-detect (http)",
            "env": {
                "MCP_TRANSPORT": "auto",
                "MCP_SERVER_URL": "http://127.0.0.1:12306/mcp"
            }
        }
    ]
    
    for config in test_configs:
        print(f"\n📋 Testing {config['name']}...")
        
        # Clear existing env vars
        for key in ["MCP_TRANSPORT", "MCP_SERVER_URL", "MCP_SERVER_COMMAND"]:
            if key in os.environ:
                del os.environ[key]
        
        # Set test env vars
        for key, value in config["env"].items():
            os.environ[key] = value
            
        try:
            # Import the module to test configuration parsing
            from gemini_mcp_orchestrator import MCP_TRANSPORT, MCP_SERVER_URL, MCP_SERVER_COMMAND
            
            print(f"   ✅ Transport: {MCP_TRANSPORT}")
            if MCP_SERVER_URL:
                print(f"   🌐 HTTP URL: {MCP_SERVER_URL}")
            if MCP_SERVER_COMMAND:
                print(f"   📋 Stdio Command: {MCP_SERVER_COMMAND}")
                
        except Exception as e:
            print(f"   ❌ Configuration error: {e}")
            
        # Remove from sys.modules to force re-import
        if 'gemini_mcp_orchestrator' in sys.modules:
            del sys.modules['gemini_mcp_orchestrator']
    
    print("\n✅ Configuration tests completed!")
    print("\nTo use with the CDP browser control server:")
    print('export MCP_TRANSPORT="stdio"')
    print('export MCP_SERVER_COMMAND="python examples/mcp_browser_control.py --server-only"')
    print('export GEMINI_API_KEY="your-api-key"')

if __name__ == "__main__":
    test_configuration()