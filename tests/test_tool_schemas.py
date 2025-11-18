#!/usr/bin/env python3
"""
Quick test to check if the tool schemas are valid for Gemini
"""
import sys
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from cdp_use.mcp_server_fastmcp import BrowserFastMCPServer

async def test_tool_schemas():
    """Test that tool schemas don't have problematic fields"""
    print("=" * 60)
    print("Testing Tool Schemas for Gemini Compatibility")
    print("=" * 60)
    
    server = BrowserFastMCPServer()
    
    # Get all registered tools
    tools = await server.server.list_tools()
    
    print(f"\n✅ Total tools registered: {len(tools)}")
    
    problematic_fields = ['additional_properties', 'additionalProperties']
    issues_found = []
    
    for tool in tools:
        tool_name = tool.name
        schema = tool.inputSchema
        
        # Convert to JSON and check for problematic fields
        schema_json = json.dumps(schema, indent=2)
        
        for field in problematic_fields:
            if field in schema_json:
                issues_found.append({
                    'tool': tool_name,
                    'field': field,
                    'schema': schema
                })
    
    if issues_found:
        print(f"\n❌ Found {len(issues_found)} tool(s) with problematic fields:")
        for issue in issues_found:
            print(f"\n  Tool: {issue['tool']}")
            print(f"  Problematic field: {issue['field']}")
            print(f"  Schema snippet:")
            print(json.dumps(issue['schema'], indent=4)[:500])
        return False
    else:
        print("\n✅ All tool schemas are clean - no problematic fields found!")
        print("\nSample tools:")
        for i, tool in enumerate(tools[:5]):
            print(f"  {i+1}. {tool.name}")
        if len(tools) > 5:
            print(f"  ... and {len(tools) - 5} more")
        return True

if __name__ == "__main__":
    success = asyncio.run(test_tool_schemas())
    sys.exit(0 if success else 1)
