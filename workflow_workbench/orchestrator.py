#!/usr/bin/env python3
"""
Main Orchestrator - Entry point for the Workflow-Enhanced Conversational MCP Orchestrator
"""

import asyncio
import json
import logging
import sys
import time
import traceback
from contextlib import AsyncExitStack
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# MCP imports
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

# Google Generative AI imports
from google import genai
from google.genai import types

# Import all refactored components
from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    MCP_TRANSPORT,
    MCP_SERVER_URL,
    MCP_SERVER_COMMAND,
    WORKFLOWS_DIR,
    MAX_ITERATIONS,
    ENABLE_STREAMING,
    ENABLE_TOOL_VALIDATION,
    ENABLE_ERROR_RECOVERY,
    ENABLE_WORKFLOW_LEARNING,
    ENABLE_VISUAL_CONTEXT,
    ENABLE_INTERACTIVE_CONTEXT,
    WORKFLOW_PATTERN_MIN_LENGTH,
    DEBUG,
)
from models import (
    SystemState,
    ToolExecutionStatus,
)
from workflow_engine import (
    WorkflowRecordingMode,
)
from workflow_cli import WorkflowCLI
from tool_execution import (
    ToolChainOrchestrator,
    ContextManager,
    StreamingResponseManager,
)

# Configure logging
logger = logging.getLogger(__name__)


class SystemMessageBuilder:
    """Builds comprehensive system messages for the orchestrator"""
    
    def __init__(self, available_tools: List, system_state: SystemState):
        self.available_tools = available_tools
        self.system_state = system_state
    
    def build_comprehensive_system_message(self) -> str:
        """Build comprehensive system message with workflow awareness"""
        
        tool_descriptions = "\n".join([
            f"- {tool.name}: {tool.description or 'No description'}"
            for tool in self.available_tools
        ])
        
        system_message = f"""You are an advanced AI assistant with browser automation and workflow management capabilities.

# Core Capabilities:
1. **Browser Automation**: You can interact with web pages, click elements, fill forms, and extract data
2. **Workflow Learning**: You can detect patterns in user actions and suggest creating reusable workflows
3. **Sequential Execution**: You can execute multi-step processes deterministically
4. **Error Recovery**: You can handle errors gracefully and suggest alternatives

# Available Tools:
{tool_descriptions}

# Tool Execution Guidelines:
- Always validate tool parameters before execution
- Use sequential tool chains for multi-step processes
- Wait for tool results before proceeding
- Handle errors gracefully with fallback strategies
- Track execution history for workflow learning

# Workflow Awareness:
- Detect repeatable patterns (3+ similar tool sequences)
- Suggest workflow creation when patterns emerge
- Support workflow recording, replay, and management
- Enable deterministic execution without LLM intervention

# Response Style:
- Be concise and action-oriented
- Explain what you're doing and why
- Provide progress updates for long operations
- Suggest optimizations when appropriate

# Current Context:
- Tools available: {len(self.available_tools)}
- Execution history: {len(self.system_state.tool_execution_history)} tool calls
- Browser state: {self.system_state.browser_state.get('current_url', 'Not navigated')}

Execute tasks efficiently and learn from successful interactions to improve future automation.
"""
        return system_message


class WorkflowEnhancedConversationalOrchestrator:
    """
    Workflow-Enhanced Conversational Orchestrator with automation capabilities.
    
    Maintains all Enhanced Conversational Orchestrator features while adding:
    - Workflow capture, parameterization, and replay functionality  
    - Pattern recognition and learning from successful interactions
    - Deterministic workflow execution without LLM intervention
    - Comprehensive workflow management and CLI interface
    """
    
    def __init__(self):
        # Core components
        self.messages = []
        self.mcp_session = None
        self.exit_stack = AsyncExitStack()
        self.genai_client = None
        self.available_tools = []
        
        # Enhanced components
        self.system_state = SystemState()
        self.context_manager = ContextManager()
        self.streaming_manager = StreamingResponseManager()
        
        # Workflow components
        self.workflow_recording = None
        self.workflow_cli = None
        
        # Will be initialized after MCP connection
        self.tool_orchestrator = None
        self.system_message_builder = None
        
        # Internal state
        self._conversation_id = f"conv_{int(time.time())}"
        self._tool_call_count = 0
        
    async def initialize(self):
        """Initialize all components including workflow features"""
        logger.info("🚀 Initializing Workflow-Enhanced Conversational Orchestrator...")
        
        # Initialize Gemini client
        if GEMINI_API_KEY:
            self.genai_client = genai.Client(api_key=GEMINI_API_KEY)
            logger.info("✅ Gemini client initialized")
        else:
            logger.error("❌ GEMINI_API_KEY not found in environment variables")
            raise ValueError("GEMINI_API_KEY is required")
        
        # Connect to MCP server
        await self._connect_to_mcp_server()
        
        # Load available tools
        await self._load_mcp_tools()
        
        # Initialize enhanced components that require tools/session
        self.tool_orchestrator = ToolChainOrchestrator(self.mcp_session, self.system_state)
        self.system_message_builder = SystemMessageBuilder(self.available_tools, self.system_state)
        
        # Initialize workflow components
        self.workflow_recording = WorkflowRecordingMode(self)
        self.workflow_cli = WorkflowCLI(self)
        
        # Build and set initial system message
        system_content = self.system_message_builder.build_comprehensive_system_message()
        self.messages = [{"role": "system", "content": system_content}]
        
        logger.info(f"✅ Workflow-enhanced orchestrator initialized with {len(self.available_tools)} tools")
        logger.info("🎯 Features enabled: " + 
                   f"Streaming={ENABLE_STREAMING}, " +
                   f"Validation={ENABLE_TOOL_VALIDATION}, " +  
                   f"Recovery={ENABLE_ERROR_RECOVERY}, " +
                   f"Workflows={ENABLE_WORKFLOW_LEARNING}")
        
    async def _connect_to_mcp_server(self):
        """Connect to MCP server using configured transport"""
        transport_type = MCP_TRANSPORT.lower()
        
        # Auto-detect transport type  
        if transport_type == "auto":
            if MCP_SERVER_URL and ("http://" in MCP_SERVER_URL or "https://" in MCP_SERVER_URL):
                transport_type = "http"
            elif MCP_SERVER_COMMAND:
                transport_type = "stdio"
            else:
                raise ValueError("Cannot auto-detect transport type. Set MCP_TRANSPORT explicitly.")
        
        # Connect using stdio transport
        if transport_type == "stdio" and MCP_SERVER_COMMAND:
            await self._connect_stdio_transport()
        # Connect using HTTP transport
        elif transport_type == "http" and MCP_SERVER_URL:
            await self._connect_http_transport()
        else:
            raise ValueError(f"Invalid transport configuration. Transport: {transport_type}, URL: {MCP_SERVER_URL}, Command: {MCP_SERVER_COMMAND}")
            
    async def _connect_stdio_transport(self):
        """Connect using stdio transport"""
        import shlex
        
        if isinstance(MCP_SERVER_COMMAND, str):
            cmd_parts = shlex.split(MCP_SERVER_COMMAND)
        else:
            cmd_parts = MCP_SERVER_COMMAND
            
        command = cmd_parts[0] if cmd_parts else "python"
        args = cmd_parts[1:] if len(cmd_parts) > 1 else []
        
        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        
        self.mcp_session = await self.exit_stack.enter_async_context(
            ClientSession(stdio_transport[0], stdio_transport[1])
        )
        
        await self.mcp_session.initialize()
        logger.info(f"✅ Connected to MCP server via stdio: {MCP_SERVER_COMMAND}")
        
    async def _connect_http_transport(self):
        """Connect using HTTP transport"""
        http_transport = await self.exit_stack.enter_async_context(
            streamablehttp_client(MCP_SERVER_URL)
        )
        
        self.mcp_session = await self.exit_stack.enter_async_context(
            ClientSession(http_transport[0], http_transport[1])
        )
        
        await self.mcp_session.initialize()
        logger.info(f"✅ Connected to MCP server via HTTP: {MCP_SERVER_URL}")
        
    async def _load_mcp_tools(self):
        """Load available tools from MCP server"""
        try:
            tools_result = await self.mcp_session.list_tools()
            self.available_tools = tools_result.tools
            
            tool_names = [tool.name for tool in self.available_tools]
            logger.info(f"📊 Loaded {len(self.available_tools)} tools: {', '.join(tool_names)}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load MCP tools: {e}")
            raise
    
    async def _get_enhanced_context(self, user_input: str) -> Optional[str]:
        """Get enhanced context information including visual and interactive context"""
        context_parts = []
        
        try:
            # Check if this is a workflow command
            if user_input.strip().startswith("workflow"):
                return None  # Workflow commands don't need visual context
                
            # Get visual context if enabled and likely needed
            if ENABLE_VISUAL_CONTEXT and any(keyword in user_input.lower() 
                                           for keyword in ["see", "show", "what", "screenshot", "page", "website", "click", "element"]):
                try:
                    # Try to get screenshot first
                    screenshot_result = await self.mcp_session.call_tool("take_screenshot", {})
                    if screenshot_result and hasattr(screenshot_result, 'content'):
                        context_parts.append("📸 Current page screenshot captured")
                        
                        # Also get interactive elements if enabled
                        if ENABLE_INTERACTIVE_CONTEXT:
                            try:
                                elements_result = await self.mcp_session.call_tool("get_interactive_elements", {})
                                if elements_result and hasattr(elements_result, 'content'):
                                    context_parts.append("🎯 Interactive elements mapped")
                            except Exception as e:
                                logger.debug(f"Could not get interactive elements: {e}")
                                
                except Exception as e:
                    logger.debug(f"Could not get screenshot: {e}")
                    context_parts.append("📋 Visual context requested but screenshot unavailable")
                    
            # Add browser state context if available
            if self.system_state.browser_state.get("current_url"):
                context_parts.append(f"🌐 Current page: {self.system_state.browser_state['current_url']}")
                
            # Add file system context if relevant
            if any(keyword in user_input.lower() for keyword in ["file", "directory", "folder", "read", "write"]):
                if self.system_state.current_directory:
                    context_parts.append(f"📁 Working directory: {self.system_state.current_directory}")
                    
        except Exception as e:
            logger.warning(f"Error getting enhanced context: {e}")
            
        return "\n".join(context_parts) if context_parts else None
        
    def _convert_tools_to_gemini_format(self) -> List[types.Tool]:
        """Convert MCP tools to Gemini format"""
        gemini_tools = []
        
        for tool in self.available_tools:
            try:
                # Convert MCP tool schema to Gemini function declaration
                function_declaration = types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description or f"Execute {tool.name}",
                    parameters=tool.inputSchema or {}
                )
                
                gemini_tool = types.Tool(
                    function_declarations=[function_declaration]
                )
                gemini_tools.append(gemini_tool)
                
            except Exception as e:
                logger.warning(f"Failed to convert tool {tool.name}: {e}")
                
        return gemini_tools
        
    async def process_user_input(self, user_input: str) -> str:
        """
        Enhanced conversational loop with workflow support:
        
        1. Enhanced context gathering
        2. Sequential tool execution with iterative conversation loop
        3. Intelligent error recovery
        4. Progressive responses
        5. Context optimization
        6. Workflow learning and suggestion capabilities
        """
        
        # Handle workflow commands first
        if user_input.strip().startswith("workflow"):
            return await self.workflow_cli.process_workflow_command(user_input.strip())
        
        # Step 1: Enhance user input with context
        context = await self._get_enhanced_context(user_input)
        
        if context:
            enhanced_input = f"{context}\n\nUser: {user_input}"
            logger.info("🔗 Enhanced context included")
        else:
            enhanced_input = user_input
            logger.warning("⚠️ No context available")
            
        self.messages.append({
            "role": "user",
            "content": enhanced_input
        })
        
        # Step 2: Optimize context if needed
        self.messages = self.context_manager.optimize_context(self.messages)
        
        logger.info(f"📝 User input processed (messages: {len(self.messages)})")
        
        # Core enhanced conversation loop (critical for multi-step execution)
        max_iterations = MAX_ITERATIONS
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            logger.debug(f"🔄 Enhanced conversation loop iteration {iteration}")
            
            try:
                # Prepare tools and config
                tools = self._convert_tools_to_gemini_format()
                
                config = types.GenerateContentConfig(
                    tools=tools if tools else None,
                    temperature=0.7,  # Slightly lower for more consistent behavior
                    max_output_tokens=2048,
                )
                
                # Create optimized content from messages  
                contents = self._create_gemini_contents()
                
                # Log final prompt for debugging
                if DEBUG:
                    self._log_enhanced_prompt(contents, config)
                
                # Generate response
                response = await self.genai_client.aio.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=contents,
                    config=config
                )
                
                # Process response
                if not response.candidates or not response.candidates[0].content:
                    logger.error("No response generated from Gemini")
                    return "Error: No response generated"
                
                candidate = response.candidates[0]
                content = candidate.content
                
                # Extract tool calls and assistant content
                tool_calls = []
                assistant_content = ""
                
                for part in content.parts:
                    if hasattr(part, 'text') and part.text:
                        assistant_content += part.text
                    elif hasattr(part, 'function_call') and part.function_call:
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
                
                # Execute tool calls if present (enhanced sequential execution)
                if tool_calls:
                    logger.info(f"🔧 Executing {len(tool_calls)} tool call(s) sequentially")
                    
                    # Execute with enhanced orchestrator
                    execution_results = await self.tool_orchestrator.execute_tool_chain_sequentially(tool_calls)
                    
                    # Record executions for workflow learning
                    if self.workflow_recording.is_recording():
                        for result in execution_results:
                            self.workflow_recording.current_session.add_tool_execution(result)
                    
                    # Add tool results to messages
                    for i, result in enumerate(execution_results):
                        tool_call = tool_calls[i]
                        
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "name": result.tool_name,
                            "content": json.dumps({
                                "result": result.result,
                                "success": result.status == ToolExecutionStatus.COMPLETED,
                                "error": result.error,
                                "execution_time": result.execution_time,
                                "retry_count": result.retry_count
                            })
                        })
                        
                    self._tool_call_count += len(tool_calls)
                    
                    # Get updated context after tool execution  
                    post_tool_context = await self._get_enhanced_context("Tools executed, analyzing current state...")
                    
                    if post_tool_context:
                        self.messages.append({
                            "role": "user",
                            "content": f"{post_tool_context}\n\n[Tools executed successfully. Please continue based on the current state.]"
                        })
                        logger.info("🔄 Post-tool context captured")
                    
                    # Continue loop for next iteration (CRITICAL: this keeps the conversation going)
                    continue
                else:
                    # No tool calls - final response
                    logger.info(f"✅ Enhanced response generated (iteration {iteration})")
                    
                    # Check for workflow suggestions before returning
                    suggestion_text = ""
                    if ENABLE_WORKFLOW_LEARNING and len(self.system_state.tool_execution_history) >= WORKFLOW_PATTERN_MIN_LENGTH:
                        if any(r.status == ToolExecutionStatus.COMPLETED for r in self.system_state.tool_execution_history[-3:]):
                            suggestions = await self.workflow_recording.auto_suggest_workflows()
                            if suggestions and len(suggestions) > 0 and suggestions[0].confidence_score > 0.8:
                                suggestion_text = f"\n\n💡 **Workflow Suggestion**: I detected a repeatable pattern in your recent actions. " \
                                                f"Would you like me to save this as a workflow? Type `workflow record start` to begin capturing patterns."
                    
                    return (assistant_content or "Response completed (no text content)") + suggestion_text
                    
            except Exception as e:
                logger.error(f"Error in enhanced conversation loop iteration {iteration}: {e}")
                
                # Enhanced error handling
                if ENABLE_ERROR_RECOVERY and iteration < max_iterations - 1:
                    self.messages.append({
                        "role": "user",
                        "content": f"An error occurred: {str(e)}. Please try a different approach or break down the task into smaller steps."
                    })
                    continue
                else:
                    return f"Error: {str(e)}"
                    
        # Safety limit reached
        logger.warning(f"Reached maximum iterations ({max_iterations})")
        return "Response completed (reached iteration limit)"
        
    def _create_gemini_contents(self) -> List[types.Content]:
        """Create Gemini contents from conversation messages"""
        contents = []
        
        for message in self.messages:
            role = message["role"]
            content_text = message.get("content", "")
            
            # Map roles to Gemini format
            if role == "system":
                # System messages are typically included in the first user message
                continue
            elif role == "user":
                # Include system message content in first user message if present
                if len(contents) == 0 and self.messages[0].get("role") == "system":
                    system_content = self.messages[0].get("content", "")
                    content_text = f"{system_content}\n\nUser: {content_text}"
                
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part(text=content_text)]
                ))
                
            elif role == "assistant":
                contents.append(types.Content(
                    role="model", 
                    parts=[types.Part(text=content_text)]
                ))
                
            elif role == "tool":
                # Tool results are included as model responses
                tool_name = message.get("name", "tool")
                tool_content = message.get("content", {})
                
                if isinstance(tool_content, dict):
                    tool_text = f"Tool {tool_name} result: {json.dumps(tool_content, indent=2)}"
                else:
                    tool_text = f"Tool {tool_name} result: {tool_content}"
                    
                contents.append(types.Content(
                    role="model",
                    parts=[types.Part(text=tool_text)]
                ))
        
        return contents
        
    def _log_enhanced_prompt(self, contents: List[types.Content], config: types.GenerateContentConfig):
        """Log enhanced prompt information for debugging"""
        if not DEBUG:
            return
            
        logger.debug("🔍 Enhanced Prompt Analysis:")
        logger.debug(f"  - Contents: {len(contents)} items")
        logger.debug(f"  - Tools available: {len(config.tools) if config.tools else 0}")
        logger.debug(f"  - Temperature: {config.temperature}")
        logger.debug(f"  - Max tokens: {config.max_output_tokens}")
        
        # Log recent conversation context
        if len(contents) >= 2:
            last_user = next((c for c in reversed(contents) if c.role == "user"), None)
            if last_user and last_user.parts:
                user_text = last_user.parts[0].text[:200] + "..." if len(last_user.parts[0].text) > 200 else last_user.parts[0].text
                logger.debug(f"  - Last user input: {user_text}")
        
        # Log system state
        logger.debug(f"  - Tool execution history: {len(self.system_state.tool_execution_history)} items")
        logger.debug(f"  - Current browser URL: {self.system_state.browser_state.get('current_url', 'None')}")
        logger.debug(f"  - Recording workflow: {self.workflow_recording.is_recording() if self.workflow_recording else False}")
        
    async def run_interactive_session(self):
        """Run interactive session with workflow support"""
        print("🎉 Welcome to the Workflow-Enhanced Conversational Orchestrator!")
        print("🚀 Advanced browser automation with workflow learning capabilities")
        print()
        
        self._print_system_status()
        print()
        print("💬 Type your requests or commands. Special commands:")
        print("   • 'workflow help' - Show workflow commands")
        print("   • 'workflow list' - List available workflows") 
        print("   • 'workflow record start' - Start recording workflow")
        print("   • 'status' - Show system status")
        print("   • 'quit' or 'exit' - Exit the session")
        print("   • 'clear' - Clear conversation history")
        print()
        
        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                    
                # Handle special commands
                if user_input.lower() in ['quit', 'exit']:
                    print("👋 Goodbye!")
                    break
                elif user_input.lower() == 'status':
                    self._print_system_status()
                    continue
                elif user_input.lower() == 'clear':
                    # Rebuild system message and clear conversation
                    system_content = self.system_message_builder.build_comprehensive_system_message()
                    self.messages = [{"role": "system", "content": system_content}]
                    print("🧹 Conversation history cleared")
                    continue
                
                # Process input
                print("🤖 Assistant: ", end="", flush=True)
                response = await self.process_user_input(user_input)
                print(response)
                print()
                
            except KeyboardInterrupt:
                print("\n👋 Session interrupted. Type 'quit' to exit or continue...")
            except Exception as e:
                print(f"\n❌ Error: {e}")
                logger.error(f"Interactive session error: {e}")
                
    def _print_system_status(self):
        """Print current system status"""
        print("📊 System Status:")
        print(f"   🔗 MCP Connection: {'✅ Connected' if self.mcp_session else '❌ Disconnected'}")
        print(f"   🤖 Gemini Client: {'✅ Ready' if self.genai_client else '❌ Not initialized'}")
        print(f"   🛠️  Available Tools: {len(self.available_tools)}")
        print(f"   📝 Conversation Length: {len(self.messages)} messages")
        print(f"   🎯 Tool Executions: {len(self.system_state.tool_execution_history)}")
        
        # Workflow status
        if self.workflow_recording:
            if self.workflow_recording.is_recording():
                session = self.workflow_recording.recording_session
                duration = datetime.now() - session.start_time
                print(f"   🎬 Recording: ✅ Active ({duration.total_seconds():.0f}s)")
            else:
                print(f"   🎬 Recording: ⏹️  Stopped")
                
        # Recent activity
        if self.system_state.tool_execution_history:
            recent_tools = [r.tool_name for r in self.system_state.tool_execution_history[-3:]]
            print(f"   🔄 Recent Tools: {' → '.join(recent_tools)}")
            
        # Browser state
        if self.system_state.browser_state.get("current_url"):
            print(f"   🌐 Current URL: {self.system_state.browser_state['current_url']}")
        
    async def cleanup(self):
        """Clean up resources"""
        logger.info("🧹 Cleaning up resources...")
        
        try:
            # Save any ongoing workflow recording
            if self.workflow_recording and self.workflow_recording.is_recording():
                logger.info("💾 Saving ongoing workflow recording...")
                await self.workflow_recording.stop_recording_and_create_workflow("Session cleanup")
                
            # Close MCP session
            await self.exit_stack.aclose()
            logger.info("✅ Cleanup completed")
            
        except Exception as e:
            logger.error(f"❌ Error during cleanup: {e}")


async def main():
    """Enhanced main entry point with workflow support"""
    orchestrator = WorkflowEnhancedConversationalOrchestrator()
    
    try:
        await orchestrator.initialize()
        await orchestrator.run_interactive_session()
    except KeyboardInterrupt:
        print("\n👋 Session interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.error(traceback.format_exc())
        print(f"\n❌ Fatal error: {e}")
    finally:
        await orchestrator.cleanup()


if __name__ == "__main__":
    # Check for API key
    if not GEMINI_API_KEY:
        print("❌ Error: GEMINI_API_KEY environment variable is required")
        print("Please set your Gemini API key and try again.")
        sys.exit(1)
    
    # Create workflows directory if it doesn't exist
    Path(WORKFLOWS_DIR).mkdir(exist_ok=True)
    
    asyncio.run(main())
