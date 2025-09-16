#!/usr/bin/env python3
"""
Simple Conversational MCP Orchestrator

Implements the core conversational tool execution loop from ConversationalOrchestrator_Strategy.md:
1. Wait for User Input → add to messages array
2. Send Messages to LLM → get response (may include tool calls)  
3. Execute Tool Calls → add results to messages array
4. Repeat until LLM provides final response
5. Show response to user

This is a simplified version focused on the core conversation loop pattern.

Author: Agent-Space Team
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, Any, List, Optional
from contextlib import AsyncExitStack
from dotenv import load_dotenv

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'BrowserAgent', 'clients', 'gemini'))

from google import genai
from google.genai import types

# Import MCP components
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import Tool

# Load environment variables
load_dotenv()

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:12306/mcp")
MCP_SERVER_COMMAND = os.getenv("MCP_SERVER_COMMAND", '"C:\\Users\\RanVic\\cdp-use\\.venv\\Scripts\\python.exe" "C:\\Users\\RanVic\\cdp-use\\examples\\mcp_browser_control.py" --server-only')
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")  # "http", "stdio", or "auto"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Setup logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleConversationalOrchestrator:
    """
    Simple conversational orchestrator implementing the core message loop pattern:
    
    Core Loop:
    1. User input → messages array
    2. Send messages to LLM 
    3. If tool calls → execute tools and add results to messages
    4. Send updated messages back to LLM
    5. Repeat until final response
    """
    
    def __init__(self):
        self.messages = []  # Core conversation state
        self.mcp_session = None
        self.exit_stack = AsyncExitStack()
        self.genai_client = None
        self.available_tools = []
        
    async def initialize(self):
        """Initialize Gemini client and MCP connection"""
        logger.info("🚀 Initializing Simple Conversational Orchestrator...")
        
        # Initialize Gemini client
        if GEMINI_API_KEY:
            try:
                self.genai_client = genai.Client(api_key=GEMINI_API_KEY)
                logger.info(f"✅ Gemini client initialized with model: {GEMINI_MODEL}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Gemini client: {e}")
                raise
        else:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        # Connect to MCP server
        await self._connect_to_mcp_server()
        
        # Load available tools
        await self._load_mcp_tools()
        
        logger.info(f"✅ Orchestrator initialized with {len(self.available_tools)} tools")
        
    async def _connect_to_mcp_server(self):
        """Connect to MCP server using configured transport"""
        transport_type = MCP_TRANSPORT.lower()
        
        # Auto-detect transport type
        if transport_type == "auto":
            if MCP_SERVER_COMMAND:
                transport_type = "stdio"
            elif MCP_SERVER_URL:
                transport_type = "http"
            else:
                logger.warning("No MCP server configuration found")
                return
        
        # Connect using stdio transport
        if transport_type == "stdio" and MCP_SERVER_COMMAND:
            await self._connect_stdio_transport()
        # Connect using HTTP transport  
        elif transport_type == "http" and MCP_SERVER_URL:
            await self._connect_http_transport()
        else:
            logger.warning("No valid MCP server connection configuration")
            
    async def _connect_stdio_transport(self):
        """Connect using stdio transport"""
        logger.info(f"Connecting to MCP stdio server: {MCP_SERVER_COMMAND}")
        
        # Parse command string
        if isinstance(MCP_SERVER_COMMAND, str):
            import shlex
            cmd_parts = shlex.split(MCP_SERVER_COMMAND)
        else:
            cmd_parts = MCP_SERVER_COMMAND
            
        command = cmd_parts[0] if cmd_parts else "python"
        args = cmd_parts[1:] if len(cmd_parts) > 1 else []
        
        # Create server parameters
        server_params = StdioServerParameters(command=command, args=args)
        
        # Start MCP server
        server_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        
        read, write = server_transport
        self.mcp_session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        await self.mcp_session.initialize()
        logger.info("✅ Connected to MCP stdio server")
        
    async def _connect_http_transport(self):
        """Connect using HTTP transport"""
        logger.info(f"Connecting to MCP HTTP server: {MCP_SERVER_URL}")
        
        transport = await self.exit_stack.enter_async_context(
            streamablehttp_client(url=MCP_SERVER_URL)
        )
        
        read, write, _ = transport
        self.mcp_session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        await self.mcp_session.initialize()
        logger.info("✅ Connected to MCP HTTP server")
        
    async def _load_mcp_tools(self):
        """Load available tools from MCP server"""
        try:
            if self.mcp_session:
                tools_response = await self.mcp_session.list_tools()
                self.available_tools = tools_response.tools
                logger.info(f"📡 Loaded {len(self.available_tools)} MCP tools")
                
                if DEBUG:
                    for tool in self.available_tools:
                        logger.debug(f"  - {tool.name}: {tool.description}")
            else:
                logger.warning("No MCP session available for loading tools")
                
        except Exception as e:
            logger.error(f"Failed to load MCP tools: {e}")
            self.available_tools = []
            
    def _convert_tools_to_gemini_format(self) -> List[types.Tool]:
        """Convert MCP tools to Gemini function calling format"""
        function_declarations = []
        
        for tool in self.available_tools:
            try:
                # Convert MCP tool schema to Gemini function declaration
                function_decl = types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description or f"Execute {tool.name}",
                    parameters=tool.inputSchema or {}
                )
                function_declarations.append(function_decl)
            except Exception as e:
                logger.warning(f"Failed to convert tool {tool.name}: {e}")
                
        if function_declarations:
            return [types.Tool(function_declarations=function_declarations)]
        return []
        
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool through MCP session"""
        try:
            if not self.mcp_session:
                return {"error": "No MCP session available"}
                
            logger.info(f"🔧 Executing tool: {tool_name}")
            logger.debug(f"Arguments: {arguments}")
            
            # Execute tool via MCP
            result = await self.mcp_session.call_tool(tool_name, arguments)
            
            # Extract content from result
            if hasattr(result, 'content') and result.content:
                content = result.content[0]
                if hasattr(content, 'text'):
                    return {"result": content.text, "success": True}
                else:
                    return {"result": str(content), "success": True}
            else:
                return {"result": str(result), "success": True}
                
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            return {"error": str(e), "success": False}
            
    async def process_user_input(self, user_input: str) -> str:
        """
        Core conversational loop implementation:
        
        1. Add user input to messages array
        2. Send messages to LLM 
        3. Execute any tool calls and add results to messages
        4. Repeat until LLM provides final response
        5. Return final response
        """
        
        # Step 1: Add user input to messages array
        self.messages.append({
            "role": "user", 
            "content": user_input
        })
        
        logger.info(f"💬 User input added to messages (total: {len(self.messages)})")
        
        # Core loop: send messages → get response → execute tools → repeat
        max_iterations = 10  # Safety limit
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            logger.debug(f"🔄 Conversation loop iteration {iteration}")
            
            # Step 2: Send messages to LLM
            try:
                tools = self._convert_tools_to_gemini_format()
                
                config = types.GenerateContentConfig(
                    tools=tools if tools else None,
                    temperature=0.7,
                    max_output_tokens=2048,
                )
                
                # Create content from messages
                contents = []
                for msg in self.messages:
                    if msg["role"] == "user":
                        contents.append(types.Content(
                            role="user",
                            parts=[types.Part(text=msg["content"])]
                        ))
                    elif msg["role"] == "assistant":
                        parts = []
                        if "content" in msg and msg["content"]:
                            parts.append(types.Part(text=msg["content"]))
                        if "tool_calls" in msg:
                            for tool_call in msg["tool_calls"]:
                                parts.append(types.Part(
                                    function_call=types.FunctionCall(
                                        name=tool_call["function"]["name"],
                                        args=tool_call["function"]["arguments"]
                                    )
                                ))
                        if parts:
                            contents.append(types.Content(role="model", parts=parts))
                    elif msg["role"] == "tool":
                        # Add tool response
                        contents.append(types.Content(
                            role="function", 
                            parts=[types.Part(
                                function_response=types.FunctionResponse(
                                    name=msg["name"],
                                    response={"result": msg["content"]}
                                )
                            )]
                        ))
                
                # Generate response
                response = await self.genai_client.aio.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=contents,
                    config=config
                )
                
                # Step 3: Process response
                if not response.candidates or not response.candidates[0].content:
                    logger.error("No response generated from Gemini")
                    return "Error: No response generated"
                
                candidate = response.candidates[0]
                content = candidate.content
                
                # Check for function calls (tool calls)
                tool_calls = []
                assistant_content = ""
                
                for part in content.parts:
                    if hasattr(part, 'text') and part.text:
                        assistant_content += part.text
                    elif hasattr(part, 'function_call') and part.function_call:
                        # Convert to tool call format
                        func_call = part.function_call
                        tool_calls.append({
                            "id": f"call_{iteration}_{func_call.name}",
                            "type": "function",
                            "function": {
                                "name": func_call.name,
                                "arguments": dict(func_call.args) if func_call.args else {}
                            }
                        })
                
                # Add assistant response to messages
                assistant_msg = {"role": "assistant"}
                if assistant_content:
                    assistant_msg["content"] = assistant_content
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                    
                self.messages.append(assistant_msg)
                
                # Step 4: Execute tool calls if present
                if tool_calls:
                    logger.info(f"🔧 Executing {len(tool_calls)} tool call(s)")
                    
                    for tool_call in tool_calls:
                        func_name = tool_call["function"]["name"] 
                        func_args = tool_call["function"]["arguments"]
                        
                        # Execute tool via MCP
                        tool_result = await self._execute_tool(func_name, func_args)
                        
                        # Add tool result to messages
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "name": func_name,
                            "content": json.dumps(tool_result)
                        })
                        
                    # Continue loop to send updated messages back to LLM
                    continue
                else:
                    # No tool calls - this is the final response
                    logger.info(f"✅ Final response generated (iteration {iteration})")
                    return assistant_content or "Response completed (no text content)"
                    
            except Exception as e:
                logger.error(f"Error in conversation loop iteration {iteration}: {e}")
                return f"Error: {str(e)}"
                
        # Safety limit reached
        logger.warning(f"Reached maximum iterations ({max_iterations})")
        return "Response completed (reached iteration limit)"
        
    async def run_interactive_session(self):
        """Run interactive conversation session"""
        print("🚀 Simple Conversational Orchestrator")
        print("💬 Implements core conversational tool execution loop")
        print(f"📡 MCP Server: {'Connected' if self.mcp_session else 'Not connected'}")
        print(f"🔧 Available tools: {len(self.available_tools)}")
        
        if self.available_tools:
            print("\nAvailable tools:")
            for tool in self.available_tools:
                print(f"  • {tool.name}: {tool.description}")
        
        print("\nType 'quit' to exit, 'clear' to reset conversation")
        print("-" * 60)
        
        while True:
            try:
                # Step 1: Wait for User Input 
                user_input = input("\n👤 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit']:
                    break
                elif user_input.lower() == 'clear':
                    self.messages = []
                    print("🧹 Conversation cleared")
                    continue
                elif not user_input:
                    continue
                    
                # Process input through conversational loop
                print("🤖 Assistant: ", end="", flush=True)
                response = await self.process_user_input(user_input)
                print(response)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Session error: {e}")
                print(f"❌ Error: {e}")
                
        print("\n👋 Goodbye!")
        
    async def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'exit_stack'):
            await self.exit_stack.aclose()


async def main():
    """Main entry point"""
    orchestrator = SimpleConversationalOrchestrator()
    
    try:
        await orchestrator.initialize()
        await orchestrator.run_interactive_session()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"❌ Failed to start orchestrator: {e}")
        sys.exit(1)
    finally:
        await orchestrator.cleanup()


if __name__ == "__main__":
    # Check for API key
    if not GEMINI_API_KEY:
        print("❌ Error: GEMINI_API_KEY environment variable is required")
        print("Please set your Gemini API key in the environment variables")
        sys.exit(1)
    
    asyncio.run(main())