#!/usr/bin/env python3
"""
Test script for the MCP Browser Control Server

This script tests the basic functionality of the MCP server.
"""

import asyncio
import json
import sys
from cdp_use.mcp_server import BrowserMCPServer, TOOLS

async def test_server_creation():
    """Test that the server can be created successfully"""
    print("🧪 Testing server creation...")
    
    try:
        server = BrowserMCPServer()
        print(f"✅ Server created: {server.server.name}")
        print(f"✅ Tools registered: {len(TOOLS)}")
        return True
    except Exception as e:
        print(f"❌ Server creation failed: {e}")
        return False

async def test_tool_definitions():
    """Test that all tools are properly defined"""
    print("\n🧪 Testing tool definitions...")
    
    required_tools = {
        "navigate", "click_element", "type_text", "take_screenshot", 
        "execute_javascript", "get_page_content", "wait_for_element"
    }
    
    tool_names = {tool.name for tool in TOOLS}
    
    if required_tools <= tool_names:
        print(f"✅ All required tools present: {tool_names}")
        return True
    else:
        missing = required_tools - tool_names
        print(f"❌ Missing tools: {missing}")
        return False

async def test_tool_schemas():
    """Test that all tools have valid input schemas"""
    print("\n🧪 Testing tool input schemas...")
    
    try:
        for tool in TOOLS:
            schema = tool.inputSchema
            assert isinstance(schema, dict), f"Tool {tool.name} schema is not dict"
            assert "type" in schema, f"Tool {tool.name} schema missing type"
            assert "properties" in schema, f"Tool {tool.name} schema missing properties"
            
            # Check required fields
            if "required" in schema:
                assert isinstance(schema["required"], list), f"Tool {tool.name} required field is not list"
        
        print("✅ All tool schemas are valid")
        return True
    except Exception as e:
        print(f"❌ Schema validation failed: {e}")
        return False

def test_imports():
    """Test that all required imports work"""
    print("🧪 Testing imports...")
    
    try:
        # Test MCP imports
        from mcp.server import Server
        from mcp.types import Tool, Resource
        from mcp.server.stdio import stdio_server
        from mcp.server.models import InitializationOptions
        print("✅ MCP imports successful")
        
        # Test CDP imports
        from cdp_use.client import CDPClient
        print("✅ CDP imports successful")
        
        # Test other dependencies
        import httpx
        import asyncio
        import json
        print("✅ Dependency imports successful")
        
        return True
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def list_tools_info():
    """List detailed information about all tools"""
    print("\n📋 Tool Information:")
    print("=" * 60)
    
    for i, tool in enumerate(TOOLS, 1):
        print(f"\n{i}. {tool.name}")
        print(f"   Description: {tool.description}")
        
        # Show required parameters
        required = tool.inputSchema.get("required", [])
        if required:
            print(f"   Required: {', '.join(required)}")
        
        # Show all properties
        properties = tool.inputSchema.get("properties", {})
        if properties:
            print("   Parameters:")
            for param, info in properties.items():
                param_type = info.get("type", "unknown")
                param_desc = info.get("description", "No description")
                print(f"     - {param} ({param_type}): {param_desc}")

async def main():
    """Run all tests"""
    print("🔬 CDP Browser Control MCP Server Tests")
    print("=" * 50)
    
    # Test imports first
    if not test_imports():
        print("\n❌ Import tests failed - cannot continue")
        sys.exit(1)
    
    # Run async tests
    tests = [
        test_server_creation(),
        test_tool_definitions(), 
        test_tool_schemas()
    ]
    
    results = await asyncio.gather(*tests, return_exceptions=True)
    
    passed = sum(1 for result in results if result is True)
    total = len(results)
    
    print(f"\n📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        await list_tools_info()
        print(f"\n✨ The MCP server is ready to use!")
        print("🚀 Run: python examples/mcp_browser_control.py")
    else:
        print("❌ Some tests failed")
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Test {i+1} exception: {result}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())