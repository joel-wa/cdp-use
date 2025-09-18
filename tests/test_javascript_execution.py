#!/usr/bin/env python3
"""
Test the execute_javascript function of the FastMCP browser server
"""

import asyncio
import subprocess
import sys
import time
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

async def test_javascript_execution():
    """Test the execute_javascript function with various JavaScript code samples"""
    
    print("🧪 Testing JavaScript execution in FastMCP browser server...")
    
    # First, check if Chrome is running with debugging enabled
    print("🔍 Checking if Chrome is accessible on debugging port...")
    try:
        import urllib.request
        import json
        with urllib.request.urlopen('http://localhost:9222/json', timeout=5) as response:
            data = response.read().decode()
            tabs = json.loads(data)
            print(f"✅ Chrome debugging accessible, found {len(tabs)} tab(s)")
    except Exception as e:
        print(f"❌ Chrome debugging not accessible: {e}")
        print("💡 Please start Chrome with: chrome --remote-debugging-port=9222 --user-data-dir=C:\\temp\\chrome_debug")
        return
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[r"C:\Users\RanVic\cdp-use\cdp_use\mcp_server_fastmcp.py"]
    )
    
    print(f"🚀 Starting MCP server: {server_params.command}")
    
    try:
        print("📡 Starting stdio transport...")
        async with stdio_client(server_params) as (read, write):
            print("✅ Got stdio streams")
            
            print("🔗 Creating MCP session...")
            async with ClientSession(read, write) as session:
                print("✅ Created session")
                
                print("🚀 Initializing session...")
                await session.initialize()
                print("✅ Session initialized!")
                
                print("📋 Listing tools...")
                tools = await session.list_tools()
                print(f"✅ Found {len(tools.tools)} tools:")
                
                # Check if execute_javascript is available
                js_tool_found = False
                for tool in tools.tools:
                    print(f"  - {tool.name}: {tool.description}")
                    if tool.name == "execute_javascript":
                        js_tool_found = True
                
                if not js_tool_found:
                    print("❌ execute_javascript tool not found!")
                    return
                
                # Test cases for JavaScript execution
                test_cases = [
                    {
                        "name": "Simple arithmetic",
                        "code": "2 + 2",
                        "expected_type": int,
                        "expected_value": 4
                    },
                    {
                        "name": "String manipulation",
                        "code": "'Hello' + ' ' + 'World'",
                        "expected_type": str,
                        "expected_value": "Hello World"
                    },
                    {
                        "name": "Get current URL",
                        "code": "window.location.href",
                        "expected_type": str
                    },
                    {
                        "name": "Get page title",
                        "code": "document.title",
                        "expected_type": str
                    },
                    {
                        "name": "Check if document exists",
                        "code": "typeof document !== 'undefined'",
                        "expected_type": bool,
                        "expected_value": True
                    },
                    {
                        "name": "Get user agent",
                        "code": "navigator.userAgent",
                        "expected_type": str
                    },
                    {
                        "name": "Create and return object",
                        "code": "({name: 'test', value: 42})",
                        "expected_type": dict
                    },
                    {
                        "name": "Error handling test",
                        "code": "nonExistentFunction()",
                        "should_error": True
                    }
                ]
                
                print("\n🧪 Running JavaScript execution tests...")
                print("=" * 60)
                
                passed = 0
                total = len(test_cases)
                
                for i, test_case in enumerate(test_cases, 1):
                    print(f"\n🔧 Test {i}/{total}: {test_case['name']}")
                    print(f"   Code: {test_case['code']}")
                    
                    try:
                        result = await session.call_tool("execute_javascript", {
                            "expression": test_case["code"]
                        })
                        
                        print(f"   Raw result: {result}")
                        
                        # Extract the actual result value
                        if hasattr(result, 'content') and result.content:
                            # For TextContent
                            actual_value = result.content[0].text if result.content else None
                        else:
                            actual_value = str(result)
                        
                        print(f"   Actual value: {actual_value} (type: {type(actual_value).__name__})")
                        
                        # Check if this test should produce an error
                        if test_case.get("should_error", False):
                            if "Error" in str(actual_value) or "error" in str(actual_value).lower():
                                print("   ✅ PASS - Expected error occurred")
                                passed += 1
                            else:
                                print("   ❌ FAIL - Expected error but got success")
                        else:
                            # For non-error tests, check the result
                            success = True
                            
                            # Check if there's an error in the result
                            if "Error" in str(actual_value):
                                print(f"   ❌ FAIL - Unexpected error: {actual_value}")
                                success = False
                            else:
                                # Type check if specified
                                if "expected_type" in test_case:
                                    try:
                                        # Try to convert the result to expected type for comparison
                                        if test_case["expected_type"] == int:
                                            converted_value = int(float(str(actual_value)))
                                        elif test_case["expected_type"] == bool:
                                            converted_value = str(actual_value).lower() == 'true'
                                        elif test_case["expected_type"] == dict:
                                            # For objects, just check if it contains object-like content
                                            converted_value = "{" in str(actual_value) and "}" in str(actual_value)
                                        else:
                                            converted_value = actual_value
                                        
                                        print(f"   Converted value: {converted_value}")
                                        
                                        # Value check if specified
                                        if "expected_value" in test_case:
                                            if converted_value == test_case["expected_value"]:
                                                print("   ✅ PASS - Value matches expected")
                                                passed += 1
                                            else:
                                                print(f"   ❌ FAIL - Expected {test_case['expected_value']}, got {converted_value}")
                                                success = False
                                        else:
                                            print("   ✅ PASS - Type check passed")
                                            passed += 1
                                            
                                    except Exception as conv_error:
                                        print(f"   ❌ FAIL - Type conversion error: {conv_error}")
                                        success = False
                                
                                if success and "expected_value" not in test_case and "expected_type" not in test_case:
                                    print("   ✅ PASS - Executed without error")
                                    passed += 1
                    
                    except Exception as e:
                        print(f"   ❌ FAIL - Exception: {e}")
                        import traceback
                        print(f"   Stack trace: {traceback.format_exc()}")
                
                print("\n" + "=" * 60)
                print(f"📊 Test Results: {passed}/{total} tests passed")
                
                if passed == total:
                    print("🎉 All JavaScript execution tests passed!")
                else:
                    print(f"⚠️  {total - passed} test(s) failed")
                
                # Additional debugging information
                print("\n🔍 Additional debugging info:")
                try:
                    result = await session.call_tool("execute_javascript", {
                        "expression": "JSON.stringify({url: window.location.href, title: document.title, readyState: document.readyState})"
                    })
                    print(f"Page info: {result}")
                except Exception as e:
                    print(f"Failed to get page info: {e}")
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        print(f"Stack trace: {traceback.format_exc()}")

def main():
    """Main function to run the test"""
    asyncio.run(test_javascript_execution())

if __name__ == "__main__":
    main()