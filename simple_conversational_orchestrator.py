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
import base64
import binascii
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
ENABLE_VISUAL_CONTEXT = os.getenv("ENABLE_VISUAL_CONTEXT", "false").lower() == "true"
ENABLE_INTERACTIVE_CONTEXT = os.getenv("ENABLE_INTERACTIVE_CONTEXT", "true").lower() == "true"
MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", str(1024 * 1024)))  # 1MB default
AUTO_SCREENSHOT_INTERVAL = int(os.getenv("AUTO_SCREENSHOT_INTERVAL", "0"))  # 0 = disabled

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
        # System prompt defining the assistant's role and permissions
        system_prompt = """You are a personal browser assistant with direct access to the user's computer and browser. You have been granted full permission by the user to:

- Browse websites and interact with web pages
- Access and modify browser tabs, windows, and bookmarks  
- Navigate the user's computer and file system
- Execute commands and scripts as needed
- Take screenshots and capture page information
- Fill out forms and interact with web applications
- Access user's browsing history and saved data

You do not need to ask for permission or worry about privacy concerns since you are operating as the user's authorized personal assistant. The user has explicitly granted you access to their system for automation and assistance purposes.

Be helpful, efficient, and proactive in assisting the user with their browser and computer tasks. Use the available tools confidently to accomplish the user's requests."""

        self.messages = [
            {"role": "system", "content": system_prompt}
        ]  # Core conversation state with system prompt
        self.mcp_session = None
        self.exit_stack = AsyncExitStack()
        self.genai_client = None
        self.available_tools = []
        # transient buffer for images to include in next LLM call
        self._pending_images = []
        # count executed tool calls to support auto-screenshot sampling
        self._tool_call_count = 0

    def _decode_base64_image(self, b64str: str) -> Optional[bytes]:
        """Decode a base64 image string. Handles optional data URL prefixes.

        Returns raw bytes or None on failure.
        """
        if not b64str:
            return None

        # Strip data URL prefix if present
        if b64str.startswith("data:"):
            try:
                _, rest = b64str.split(',', 1)
                b64str = rest
            except ValueError:
                # malformed data URL
                return None

        try:
            img_bytes = base64.b64decode(b64str)
        except (binascii.Error, TypeError):
            return None

        return img_bytes
    
    async def _get_visual_context_description(self) -> Optional[str]:
        """Capture screenshot and get text description of current page state"""
        if not ENABLE_VISUAL_CONTEXT:
            return None
            
        try:
            logger.debug("📸 Capturing screenshot for visual context...")
            
            # Execute screenshot tool directly
            result = await self.mcp_session.call_tool("take_screenshot", {
                "format": "png", 
                "fullPage": False
            })
            
            # Extract base64 image data
            image_data = None
            if hasattr(result, 'content') and result.content:
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        try:
                            parsed = json.loads(content_item.text)
                            if isinstance(parsed, dict) and parsed.get("type") == "image":
                                image_data = parsed.get("data")
                                break
                        except json.JSONDecodeError:
                            pass
                            
            if not image_data:
                logger.warning("No image data found in screenshot result")
                return None
                
            # Convert to bytes for Gemini
            img_bytes = self._decode_base64_image(image_data)
            if not img_bytes or len(img_bytes) > MAX_IMAGE_BYTES:
                logger.warning(f"Image too large or invalid: {len(img_bytes) if img_bytes else 0} bytes")
                return None
                
            logger.debug(f"Screenshot captured: {len(img_bytes)} bytes")
            
            # Send to Gemini for description
            contents = [
                types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                types.Part(text="Describe what you see in this browser screenshot. Focus on the main content, UI elements, and current state. Keep it concise but informative such that a blind person knows what is being shown and can make decisions.")
            ]
            
            response = await self.genai_client.aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=300
                )
            )
            
            if response.candidates and response.candidates[0].content:
                description = response.candidates[0].content.parts[0].text
                logger.debug(f"Visual context: {description[:100]}...")
                return f"[CURRENT SCREEN: {description}]"
            else:
                logger.warning("No description generated from screenshot")
                return None
                
        except Exception as e:
            logger.warning(f"Failed to get visual context: {e}")
            return None

    async def _get_interactive_elements_context(self) -> Optional[str]:
        """Capture interactive elements and get text description of available interactions"""
        if not ENABLE_INTERACTIVE_CONTEXT:
            return None
            
        try:
            logger.debug("🔍 Capturing interactive elements for context...")
            
            # First hide any existing visual indicators to clean the page
            try:
                await self.mcp_session.call_tool("hide_visual_indicators", {})
            except Exception:
                pass  # Ignore if no indicators to hide
            
            # Get interactive elements (this will show visual indicators)
            result = await self.mcp_session.call_tool("get_interactive_elements", {
                "show_visual": True,
                "color": "rgba(0,255,0,0.2)"  # Use green for context capture
            })
            
            # Extract elements data
            elements_data = None
            if hasattr(result, 'content') and result.content:
                for content_item in result.content:
                    if hasattr(content_item, 'text'):
                        try:
                            parsed = json.loads(content_item.text)
                            if isinstance(parsed, dict) and "elements" in parsed:
                                elements_data = parsed
                                break
                        except json.JSONDecodeError:
                            pass
            
            # Hide visual indicators after capturing
            try:
                await self.mcp_session.call_tool("hide_visual_indicators", {})
            except Exception:
                pass  # Ignore if hiding fails
                            
            if not elements_data or not elements_data.get("elements"):
                logger.debug("No interactive elements found")
                return None
                
            # Format elements for context
            elements = elements_data["elements"][:15]  # Limit to first 15 elements to avoid token overflow
            
            context_parts = []
            context_parts.append(f"[INTERACTIVE ELEMENTS AVAILABLE ({elements_data.get('total_elements', 0)} total):")
            
            for elem in elements:
                elem_desc = f"  #{elem['index']}: {elem['tag'].upper()}"
                if elem.get('text') and elem['text'].strip():
                    elem_desc += f" - '{elem['text'][:50]}'"
                if elem.get('attributes'):
                    # Show important attributes
                    attrs = elem['attributes']
                    if attrs.get('type'):
                        elem_desc += f" (type: {attrs['type']})"
                    if attrs.get('placeholder'):
                        elem_desc += f" (placeholder: {attrs['placeholder'][:30]})"
                    if attrs.get('value'):
                        elem_desc += f" (value: {attrs['value'][:30]})"
                
                context_parts.append(elem_desc)
            
            if len(elements_data["elements"]) > 15:
                context_parts.append(f"  ... and {len(elements_data['elements']) - 15} more elements")
                
            context_parts.append("]")
            
            context_text = "\n".join(context_parts)
            logger.debug(f"Interactive elements context: {len(elements)} elements")
            return context_text
                
        except Exception as e:
            logger.warning(f"Failed to get interactive elements context: {e}")
            return None
        
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

            # Normalize and preserve structured result for caller
            # MCP tool implementations often return a list of dicts; preserve that
            try:
                # If result has attribute 'content' (ClientSession wrapper), convert
                if hasattr(result, 'content') and result.content:
                    # content is usually a list-like of parts; attempt to extract python objects
                    raw = []
                    for c in result.content:
                        # try to use text field if present
                        if hasattr(c, 'text') and c.text is not None:
                            raw.append({"type": "text", "text": c.text})
                        else:
                            raw.append(c)
                    tool_out = raw
                else:
                    tool_out = result
            except Exception:
                tool_out = result

            # If the tool returned a list/dict that includes image data (from take_screenshot),
            # detect and store in pending images for the next LLM call but still return text result.
            try:
                # normalize to list
                items = tool_out if isinstance(tool_out, list) else [tool_out]
                for item in items:
                    if isinstance(item, dict) and item.get("type") == "image" and item.get("data"):
                        img_base64 = item.get("data")
                        mime = item.get("mimeType") or item.get("mime_type") or "image/png"
                        self._pending_images.append({"data": img_base64, "mime": mime, "source_tool": tool_name})
            except Exception:
                # don't let image extraction break the tool result
                pass

            # Return a stable JSON-serializable representation
            return {"result": tool_out, "success": True}
                
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
        # Get interactive elements context
        interactive_context = await self._get_interactive_elements_context()
        # Then, get visual context if enabled
        visual_context = await self._get_visual_context_description()
        
        
        # Enhance user input with context
        enhanced_input = user_input
        if visual_context:
            enhanced_input = f"{visual_context}\n\nUser: {user_input}"
        if interactive_context:
            if visual_context:
                enhanced_input = f"{visual_context}\n\n{interactive_context}\n\nUser: {user_input}"
            else:
                enhanced_input = f"{interactive_context}\n\nUser: {user_input}"
            
        self.messages.append({
            "role": "user", 
            "content": enhanced_input
        })
        
        logger.info(f"💬 User input added to messages (total: {len(self.messages)})")
        if visual_context:
            logger.info("👁️ Visual context included automatically")
        if interactive_context:
            logger.info("🔍 Interactive elements context included automatically")
        
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
                    temperature=0.8,
                    max_output_tokens=2048,
                )
                
                # Create content from messages, incorporating system prompt into first user message
                contents = []
                system_instruction = None
                first_user_msg = True

                # Clear any leftover pending images (now using text descriptions instead)
                self._pending_images = []
                
                for msg in self.messages:
                    if msg["role"] == "system":
                        # Store system instruction to prepend to first user message
                        system_instruction = msg["content"]
                    elif msg["role"] == "user":
                        user_content = msg["content"]
                        # Prepend system instruction to first user message
                        if first_user_msg and system_instruction:
                            user_content = f"{system_instruction}\n\nUser: {user_content}"
                            first_user_msg = False
                        contents.append(types.Content(
                            role="user",
                            parts=[types.Part(text=user_content)]
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
                        # Add tool response. Try to preserve structured JSON if available
                        try:
                            parsed = json.loads(msg.get("content") or "null")
                        except Exception:
                            parsed = msg.get("content")

                        contents.append(types.Content(
                            role="function",
                            parts=[types.Part(
                                function_response=types.FunctionResponse(
                                    name=msg["name"],
                                    response={"result": parsed}
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
                        
                        # Increment tool call count 
                        self._tool_call_count += 1
                        
                    # Get updated visual context after tool execution
                    post_tool_visual_context = await self._get_visual_context_description()
                    
                    # Get updated interactive elements context after tool execution
                    post_tool_interactive_context = await self._get_interactive_elements_context()
                    
                    if post_tool_visual_context or post_tool_interactive_context:
                        # Combine contexts for the next iteration
                        context_message = ""
                        if post_tool_visual_context:
                            context_message += post_tool_visual_context
                        if post_tool_interactive_context:
                            if post_tool_visual_context:
                                context_message += f"\n\n{post_tool_interactive_context}"
                            else:
                                context_message += post_tool_interactive_context
                        
                        context_message += "\n\n[Tools executed successfully. Please continue based on the current screen state and available interactive elements.]"
                        
                        # Add context as a system message for the next iteration
                        self.messages.append({
                            "role": "user",
                            "content": context_message
                        })
                        
                        if post_tool_visual_context:
                            logger.info("👁️ Post-tool visual context captured")
                        if post_tool_interactive_context:
                            logger.info("🔍 Post-tool interactive elements context captured")
                    
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
        print("🚀 Personal Browser Assistant")
        print("🤖 I'm your authorized personal assistant with full browser and computer access")
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
                    # Reset conversation but keep system prompt
                    system_msg = next((msg for msg in self.messages if msg["role"] == "system"), None)
                    self.messages = [system_msg] if system_msg else []
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