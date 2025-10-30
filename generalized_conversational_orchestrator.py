#!/usr/bin/env python3
"""
Generalized Conversational MCP Orchestrator

A robust, domain-agnostic implementation for orchestrating tool-based workflows via MCP.

Features:
1. Comprehensive, context-aware system message architecture
2. Sequential and intelligent tool execution with chaining
3. Progressive, optimized context management
4. Tool state awareness and validation
5. Streaming responses with progress updates
6. Intelligent error recovery and resilience
7. Dynamic context injection

This orchestrator is suitable for any MCP toolset, not just web or browser agents.

Author: Agent-Space Team (Generalized)
Version: 1.0 Generalized
"""
import os
import sys
import shlex
import time
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, AsyncGenerator
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from collections import deque
from dotenv import load_dotenv

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

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
MCP_SERVER_COMMAND = os.getenv("MCP_SERVER_COMMAND", 'python examples/mcp_browser_control.py --server-only')
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "100000"))
ENABLE_STREAMING = os.getenv("ENABLE_STREAMING", "true").lower() == "true"
ENABLE_TOOL_VALIDATION = os.getenv("ENABLE_TOOL_VALIDATION", "true").lower() == "true"
ENABLE_ERROR_RECOVERY = os.getenv("ENABLE_ERROR_RECOVERY", "true").lower() == "true"
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
TOOL_EXECUTION_TIMEOUT = int(os.getenv("TOOL_EXECUTION_TIMEOUT", "60"))
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "20"))

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- ENUMS & DATA CLASSES ---
class ErrorSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    RECOVERABLE = "recoverable"
    CRITICAL = "critical"
    FATAL = "fatal"

class ToolExecutionStatus(Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

@dataclass
class ToolExecutionResult:
    tool_name: str
    arguments: Dict[str, Any]
    status: ToolExecutionStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    retry_count: int = 0
    context_updates: List[str] = field(default_factory=list)
    state_changes: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SystemState:
    current_directory: Optional[str] = None
    file_system_cache: Dict[str, Any] = field(default_factory=dict)
    executed_commands: deque = field(default_factory=lambda: deque(maxlen=100))
    environment_vars: Dict[str, str] = field(default_factory=dict)
    session_start_time: datetime = field(default_factory=datetime.now)
    tool_execution_history: List[ToolExecutionResult] = field(default_factory=list)
    context_cache: Dict[str, Any] = field(default_factory=dict)
    last_error: Optional[str] = None
    def update_from_tool_result(self, result: ToolExecutionResult):
        self.tool_execution_history.append(result)
        if result.state_changes:
            for key, value in result.state_changes.items():
                setattr(self, key, value)

# --- SYSTEM MESSAGE BUILDER ---
class SystemMessageBuilder:
    def __init__(self, available_tools: List[Tool], state: SystemState):
        self.available_tools = available_tools
        self.state = state
    def build_comprehensive_system_message(self) -> str:
        base_personality = """
You are a Generalized MCP Agent, an advanced assistant capable of orchestrating complex tool-based workflows across any domain. You have full permission to access and control the user's available tools and system resources as authorized.

Core Capabilities:
- Intelligent tool selection and execution
- Advanced error handling and recovery
- Progressive, context-aware problem-solving
- Proactive assistance and suggestion generation
- Multi-step operation coordination
"""
        tool_guidelines = self._build_tool_usage_guidelines()
        execution_patterns = self._build_execution_patterns()
        context_awareness = self._build_context_awareness()
        error_handling = self._build_error_handling_guidelines()
        gemini_optimizations = self._build_gemini_optimizations()
        system_message = f"""{base_personality}\n\n{tool_guidelines}\n\n{execution_patterns}\n\n{context_awareness}\n\n{error_handling}\n\n{gemini_optimizations}\n\nRemember: You are operating as the user's authorized assistant. Be proactive, intelligent, and thorough in your assistance."""
        return system_message
    def _build_tool_usage_guidelines(self) -> str:
        tool_names = [tool.name for tool in self.available_tools]
        guidelines = f"""
TOOL USAGE GUIDELINES:

Available Tools: {', '.join(tool_names)}

Core Principles:
1. SEQUENTIAL EXECUTION: Execute tools one at a time unless explicitly parallel
2. EXPLAIN FIRST: Always explain your reasoning before calling tools
3. VALIDATE INPUTS: Verify parameters make sense before execution
4. HANDLE ERRORS: If a tool fails, explain why and try alternatives
5. SHOW PROGRESS: Keep the user informed of your progress
6. CHAIN LOGICALLY: When tools have dependencies, execute in proper order
"""
        return guidelines
    def _build_execution_patterns(self) -> str:
        return """
EXECUTION PATTERNS:

Before Tool Execution:
- State your intention and plan
- Validate prerequisites are met
- Check current state for context

During Tool Execution:
- Monitor for errors or unexpected results
- Adapt strategy based on intermediate results
- Maintain awareness of state changes

After Tool Execution:
- Verify results meet expectations
- Update understanding of current state
- Plan next steps based on new information

Multi-Step Operations:
- Break complex tasks into logical steps
- Execute steps sequentially with validation
- Provide progress updates between steps
- Handle failures gracefully with recovery
"""
    def _build_context_awareness(self) -> str:
        current_context = []
        if self.state.current_directory:
            current_context.append(f"Working Directory: {self.state.current_directory}")
        if self.state.last_error:
            current_context.append(f"Last Error: {self.state.last_error}")
        recent_tools = [r.tool_name for r in self.state.tool_execution_history[-5:]]
        if recent_tools:
            current_context.append(f"Recent Tools: {' → '.join(recent_tools)}")
        context_info = '\n'.join(f"- {ctx}" for ctx in current_context) if current_context else "- No specific context available"
        return f"""
CONTEXT AWARENESS:

Current Session Context:
{context_info}

State Management:
- Track system and tool state changes
- Remember previous tool results for context
- Maintain awareness of user goals and progress
- Use historical context to inform decisions

Context Usage:
- Reference previous results when relevant
- Avoid repeating unnecessary operations
- Build upon established context
- Provide continuity across interactions
"""
    def _build_error_handling_guidelines(self) -> str:
        return """
ERROR HANDLING & RECOVERY:

Error Response Protocol:
1. ACKNOWLEDGE: Clearly state what went wrong
2. ANALYZE: Explain the likely cause of the error
3. ADAPT: Propose alternative approaches
4. EXECUTE: Try recovery strategies
5. ESCALATE: If all else fails, ask for user guidance

Recovery Strategies:
- Retry with modified parameters
- Use alternative tools for same goal
- Break down complex operations into simpler steps
- Verify prerequisites before retry attempts
- Provide fallback options to user

Error Classifications:
- Transient (network, timeout) → Retry automatically
- Parameter (invalid input) → Fix and retry
- State (prerequisite not met) → Address prerequisite
- Critical (system failure) → Escalate to user
"""
    def _build_gemini_optimizations(self) -> str:
        return """
GEMINI OPTIMIZATION PATTERNS:

Thinking Process:
- Use step-by-step reasoning for complex tasks
- Explain your decision-making process clearly
- Consider multiple approaches before choosing
- Validate assumptions before proceeding

Tool Call Structure:
- One primary tool per response when possible
- Group related tools logically when parallel execution makes sense
- Provide clear rationale for tool selection
- Include error handling in your planning

Response Quality:
- Be specific and actionable in your explanations
- Provide context for why you're taking certain actions
- Offer alternatives when appropriate
- Synthesize results into coherent narrative
"""

# --- TOOL VALIDATOR ---
class ToolValidator:
    def __init__(self, state: SystemState):
        self.state = state
    def validate_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        if not ENABLE_TOOL_VALIDATION:
            return True, None
        try:
            if not isinstance(arguments, dict):
                return False, "Tool arguments must be a dictionary"
            # Optionally, add tool-specific validation here
            return True, None
        except Exception as e:
            return False, f"Validation error: {str(e)}"

# --- ERROR RECOVERY ENGINE ---
class ErrorRecoveryEngine:
    def __init__(self, state: SystemState):
        self.state = state
    def analyze_error(self, tool_name: str, error: str, context: Dict[str, Any]) -> Tuple[ErrorSeverity, List[str]]:
        error_lower = error.lower()
        if any(keyword in error_lower for keyword in ["timeout", "network", "connection"]):
            severity = ErrorSeverity.RECOVERABLE
            suggestions = ["Retry the operation after a brief delay", "Check network connectivity"]
        elif any(keyword in error_lower for keyword in ["not found", "404"]):
            severity = ErrorSeverity.WARNING
            suggestions = ["Verify resource exists", "Check input parameters"]
        elif any(keyword in error_lower for keyword in ["permission", "access denied"]):
            severity = ErrorSeverity.CRITICAL
            suggestions = ["Check permissions", "Run with appropriate privileges"]
        elif any(keyword in error_lower for keyword in ["syntax", "invalid", "malformed"]):
            severity = ErrorSeverity.RECOVERABLE
            suggestions = ["Validate input parameters", "Check parameter format and types"]
        else:
            severity = ErrorSeverity.WARNING
            suggestions = ["Review error message for details", "Try alternative approach"]
        return severity, suggestions

# --- CONTEXT MANAGER ---
class ContextManager:
    def __init__(self, max_tokens: int = MAX_CONTEXT_TOKENS):
        self.max_tokens = max_tokens
        self.token_estimate_ratio = 4
    def optimize_context(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        estimated_tokens = self._estimate_tokens(messages)
        if estimated_tokens <= self.max_tokens:
            return messages
        logger.info(f"Context optimization needed: {estimated_tokens} > {self.max_tokens} tokens")
        optimized = []
        system_msg = next((msg for msg in messages if msg.get("role") == "system"), None)
        if system_msg:
            optimized.append(system_msg)
        recent_messages = messages[-6:]
        older_messages = messages[1:-6] if len(messages) > 7 else []
        if older_messages:
            summarized_chains = self._summarize_tool_chains(older_messages)
            optimized.extend(summarized_chains)
        optimized.extend(recent_messages)
        final_tokens = self._estimate_tokens(optimized)
        logger.info(f"Context optimized: {estimated_tokens} → {final_tokens} tokens")
        return optimized
    def _estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        total_chars = 0
        for msg in messages:
            if "content" in msg:
                total_chars += len(str(msg["content"]))
        return total_chars // self.token_estimate_ratio
    def _summarize_tool_chains(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        chains = []
        current_chain = []
        for msg in messages:
            if msg.get("role") == "assistant":
                if current_chain:
                    chains.append(current_chain)
                current_chain = [msg]
            elif msg.get("role") == "tool":
                current_chain.append(msg)
        if current_chain:
            chains.append(current_chain)
        summarized = []
        for chain in chains:
            summary = self._create_chain_summary(chain)
            summarized.append(summary)
        return summarized
    def _create_chain_summary(self, chain: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not chain:
            return {"role": "assistant", "content": "[Tool chain summary: No operations]"}
        assistant_msg = chain[0] if chain[0].get("role") == "assistant" else None
        tool_results = [msg for msg in chain if msg.get("role") == "tool"]
        tools_used = []
        successful_tools = []
        failed_tools = []
        for tool_msg in tool_results:
            tool_name = tool_msg.get("name", "unknown")
            tools_used.append(tool_name)
            try:
                result = json.loads(tool_msg.get("content", "{}"))
                if result.get("success", True):
                    successful_tools.append(tool_name)
                else:
                    failed_tools.append(tool_name)
            except json.JSONDecodeError:
                successful_tools.append(tool_name)
        summary_parts = []
        if tools_used:
            summary_parts.append(f"Tools used: {', '.join(tools_used)}")
        if successful_tools:
            summary_parts.append(f"Successful: {', '.join(successful_tools)}")
        if failed_tools:
            summary_parts.append(f"Failed: {', '.join(failed_tools)}")
        summary_content = f"[Tool chain summary: {'; '.join(summary_parts)}]"
        return {"role": "assistant", "content": summary_content}

# --- TOOL CHAIN ORCHESTRATOR ---
class ToolChainOrchestrator:
    def __init__(self, mcp_session: ClientSession, state: SystemState):
        self.mcp_session = mcp_session
        self.state = state
        self.validator = ToolValidator(state)
        self.recovery_engine = ErrorRecoveryEngine(state)
    async def execute_tool_chain_sequentially(self, tool_calls: List[Dict[str, Any]]) -> List[ToolExecutionResult]:
        results = []
        for i, tool_call in enumerate(tool_calls):
            logger.info(f"🔧 Executing tool {i+1}/{len(tool_calls)}: {tool_call['function']['name']}")
            result = await self._execute_single_tool_with_recovery(tool_call)
            results.append(result)
            self.state.update_from_tool_result(result)
            if result.status == ToolExecutionStatus.FAILED:
                severity, suggestions = self.recovery_engine.analyze_error(
                    result.tool_name, result.error or "Unknown error", {}
                )
                if severity == ErrorSeverity.FATAL:
                    logger.error(f"Fatal error in tool chain, stopping execution: {result.error}")
                    break
                elif severity == ErrorSeverity.CRITICAL:
                    logger.warning(f"Critical error, but continuing: {result.error}")
        return results
    async def _execute_single_tool_with_recovery(self, tool_call: Dict[str, Any]) -> ToolExecutionResult:
        tool_name = tool_call["function"]["name"]
        arguments = tool_call["function"]["arguments"]
        result = ToolExecutionResult(
            tool_name=tool_name,
            arguments=arguments,
            status=ToolExecutionStatus.PENDING
        )
        result.status = ToolExecutionStatus.VALIDATING
        is_valid, validation_error = self.validator.validate_tool_call(tool_name, arguments)
        if not is_valid:
            result.status = ToolExecutionStatus.FAILED
            result.error = f"Validation failed: {validation_error}"
            return result
        for attempt in range(MAX_RETRY_ATTEMPTS):
            if attempt > 0:
                result.status = ToolExecutionStatus.RETRYING
                result.retry_count = attempt
                await asyncio.sleep(min(2 ** attempt, 10))
            try:
                result.status = ToolExecutionStatus.EXECUTING
                start_time = time.time()
                mcp_result = await asyncio.wait_for(
                    self.mcp_session.call_tool(tool_name, arguments),
                    timeout=TOOL_EXECUTION_TIMEOUT
                )
                result.execution_time = time.time() - start_time
                processed_result = self._process_mcp_result(mcp_result)
                result.result = processed_result
                result.status = ToolExecutionStatus.COMPLETED
                logger.info(f"✅ Tool {tool_name} executed successfully in {result.execution_time:.2f}s")
                return result
            except asyncio.TimeoutError:
                error_msg = f"Tool execution timeout after {TOOL_EXECUTION_TIMEOUT}s"
                logger.warning(f"⏰ {error_msg}")
                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    continue
                else:
                    result.status = ToolExecutionStatus.FAILED
                    result.error = error_msg
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"❌ Tool execution error (attempt {attempt + 1}): {error_msg}")
                if attempt < MAX_RETRY_ATTEMPTS - 1 and ENABLE_ERROR_RECOVERY:
                    severity, suggestions = self.recovery_engine.analyze_error(tool_name, error_msg, {})
                    if severity in [ErrorSeverity.RECOVERABLE, ErrorSeverity.WARNING]:
                        continue
                result.status = ToolExecutionStatus.FAILED
                result.error = error_msg
        return result
    def _process_mcp_result(self, mcp_result) -> Dict[str, Any]:
        try:
            if hasattr(mcp_result, 'content') and mcp_result.content:
                processed = []
                for content_item in mcp_result.content:
                    if hasattr(content_item, 'text'):
                        processed.append(content_item.text)
                    else:
                        processed.append(str(content_item))
                return {"success": True, "content": processed}
            else:
                return {"success": True, "content": mcp_result}
        except Exception as e:
            logger.warning(f"Error processing MCP result: {e}")
            return {"success": False, "error": str(e), "raw_result": str(mcp_result)}

# --- STREAMING RESPONSE MANAGER ---
class StreamingResponseManager:
    def __init__(self):
        self.enable_streaming = ENABLE_STREAMING
    async def stream_tool_execution(self, tool_calls: List[Dict[str, Any]], executor_func) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.enable_streaming:
            results = await executor_func(tool_calls)
            yield {"type": "final_result", "content": results}
            return
        yield {"type": "planning", "content": f"Planning to execute {len(tool_calls)} tool(s)..."}
        for i, tool_call in enumerate(tool_calls):
            tool_name = tool_call["function"]["name"]
            yield {
                "type": "tool_start",
                "content": f"Starting {tool_name} ({i+1}/{len(tool_calls)})",
                "tool_name": tool_name,
                "progress": i / len(tool_calls)
            }
            result = await executor_func([tool_call])
            yield {
                "type": "tool_complete",
                "content": f"Completed {tool_name}",
                "tool_name": tool_name,
                "result": result[0] if result else None,
                "progress": (i + 1) / len(tool_calls)
            }
        yield {"type": "synthesis", "content": "Synthesizing results..."}

# --- MAIN ORCHESTRATOR ---
class GeneralizedConversationalOrchestrator:
    def __init__(self):
        self.messages = []
        self.mcp_session = None
        self.exit_stack = AsyncExitStack()
        self.genai_client = None
        self.available_tools = []
        self.system_state = SystemState()
        self.context_manager = ContextManager()
        self.streaming_manager = StreamingResponseManager()
        self.tool_orchestrator = None
        self.system_message_builder = None
        self._conversation_id = f"conv_{int(time.time())}"
        self._tool_call_count = 0
    async def initialize(self):
        logger.info("🚀 Initializing Generalized Conversational Orchestrator...")
        if GEMINI_API_KEY:
            try:
                self.genai_client = genai.Client(api_key=GEMINI_API_KEY)
                logger.info(f"✅ Gemini client initialized with model: {GEMINI_MODEL}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Gemini client: {e}")
                raise
        else:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        await self._connect_to_mcp_server()
        await self._load_mcp_tools()
        self.tool_orchestrator = ToolChainOrchestrator(self.mcp_session, self.system_state)
        self.system_message_builder = SystemMessageBuilder(self.available_tools, self.system_state)
        system_content = self.system_message_builder.build_comprehensive_system_message()
        self.messages = [{"role": "system", "content": system_content}]
        logger.info(f"✅ Orchestrator initialized with {len(self.available_tools)} tools")
    async def _connect_to_mcp_server(self):
        transport_type = MCP_TRANSPORT.lower()
        if transport_type == "auto":
            if MCP_SERVER_COMMAND:
                transport_type = "stdio"
            elif MCP_SERVER_URL:
                transport_type = "http"
            else:
                logger.warning("No MCP server configuration found")
                return
        if transport_type == "stdio" and MCP_SERVER_COMMAND:
            await self._connect_stdio_transport()
        elif transport_type == "http" and MCP_SERVER_URL:
            await self._connect_http_transport()
        else:
            logger.warning("No valid MCP server connection configuration")
    async def _connect_stdio_transport(self):
        logger.info(f"Connecting to MCP stdio server: {MCP_SERVER_COMMAND}")
        if isinstance(MCP_SERVER_COMMAND, str):
            cmd_parts = shlex.split(MCP_SERVER_COMMAND)
        else:
            cmd_parts = MCP_SERVER_COMMAND
        command = cmd_parts[0] if cmd_parts else "python"
        args = cmd_parts[1:] if len(cmd_parts) > 1 else []
        server_params = StdioServerParameters(command=command, args=args)
        server_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read, write = server_transport
        self.mcp_session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        await self.mcp_session.initialize()
        logger.info("✅ Connected to MCP stdio server")
    async def _connect_http_transport(self):
        logger.info(f"Connecting to MCP HTTP server: {MCP_SERVER_URL}")
        transport = await self.exit_stack.enter_async_context(
            streamablehttp_client(url=MCP_SERVER_URL)
        )
        read, write, _ = transport
        self.mcp_session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        await self.mcp_session.initialize()
        logger.info("✅ Connected to MCP HTTP server")
    async def _load_mcp_tools(self):
        try:
            if self.mcp_session:
                tools_response = await self.mcp_session.list_tools()
                self.available_tools = tools_response.tools
                logger.info(f"📡 Loaded {len(self.available_tools)} MCP tools")
            else:
                logger.warning("No MCP session available for loading tools")
        except Exception as e:
            logger.error(f"Failed to load MCP tools: {e}")
            self.available_tools = []
    def _convert_tools_to_gemini_format(self) -> List[types.Tool]:
        function_declarations = []
        for tool in self.available_tools:
            try:
                # Convert MCP tool schema to Gemini function declaration format
                schema = tool.inputSchema or {}
                # Ensure the schema has the correct structure
                parameters = {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", [])
                }
                
                function_decl = types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description or f"Execute {tool.name}",
                    parameters=parameters
                )
                function_declarations.append(function_decl)
            except Exception as e:
                logger.warning(f"Failed to convert tool {tool.name}: {e}")
        if function_declarations:
            return [types.Tool(function_declarations=function_declarations)]
        return []
    def _create_gemini_contents(self) -> List[types.Content]:
        contents = []
        system_instruction = None
        first_user_msg = True
        for msg in self.messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                user_content = msg["content"]
                if first_user_msg and system_instruction:
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
                    for call in msg["tool_calls"]:
                        function_call = types.FunctionCall(
                            name=call["function"]["name"],
                            args=json.dumps(call["function"]["arguments"])
                        )
                        parts.append(types.Part(function_call=function_call))
                if parts:
                    contents.append(types.Content(role="model", parts=parts))
            elif msg["role"] == "tool":
                try:
                    parsed = json.loads(msg["content"])
                except Exception:
                    parsed = msg["content"]
                contents.append(types.Content(
                    role="function",
                    parts=[types.Part(
                        function_response=types.FunctionResponse(
                            name=msg["name"],
                            response={"result": parsed}
                        )
                    )]
                ))
        return contents
    async def process_user_input(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": user_input})
        self.messages = self.context_manager.optimize_context(self.messages)
        logger.info(f"📝 User input processed (messages: {len(self.messages)})")
        max_iterations = MAX_ITERATIONS
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            logger.debug(f"🔄 Conversation loop iteration {iteration}")
            try:
                tools = self._convert_tools_to_gemini_format()
                config = types.GenerateContentConfig(
                    tools=tools if tools else None,
                    temperature=0.7,
                    max_output_tokens=2048,
                )
                contents = self._create_gemini_contents()
                response = await self.genai_client.aio.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=contents,
                    config=config
                )
                if not response.candidates or not response.candidates[0].content:
                    logger.error("No response generated from Gemini")
                    return "Error: No response generated"
                candidate = response.candidates[0]
                content = candidate.content
                tool_calls = []
                assistant_content = ""
                for part in content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        try:
                            # Convert Gemini function call to the expected format
                            tool_call = {
                                "function": {
                                    "name": part.function_call.name,
                                    "arguments": json.loads(part.function_call.args) if isinstance(part.function_call.args, str) else part.function_call.args
                                }
                            }
                            tool_calls.append(tool_call)
                        except Exception as e:
                            logger.warning(f"Error processing function call: {e}")
                            continue
                    elif hasattr(part, 'text') and part.text:
                        assistant_content += part.text
                assistant_msg = {"role": "assistant"}
                if assistant_content:
                    assistant_msg["content"] = assistant_content
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                self.messages.append(assistant_msg)
                if tool_calls:
                    results = await self.tool_orchestrator.execute_tool_chain_sequentially(tool_calls)
                    for i, tool_call in enumerate(tool_calls):
                        tool_result = results[i] if i < len(results) else None
                        tool_msg = {
                            "role": "tool",
                            "name": tool_call["function"]["name"],
                            "content": json.dumps(tool_result.result if tool_result else {"error": "No result"})
                        }
                        self.messages.append(tool_msg)
                    continue
                else:
                    return assistant_content or "[No response]"
            except Exception as e:
                logger.error(f"Error in conversation loop iteration {iteration}: {e}")
                if ENABLE_ERROR_RECOVERY and iteration < max_iterations - 1:
                    continue
                else:
                    return f"Error: {e}"
        logger.warning(f"Reached maximum iterations ({max_iterations})")
        return "Response completed (reached iteration limit)"
    async def run_interactive_session(self):
        print("\n🚀 Generalized MCP Agent")
        print("🎯 Advanced MCP orchestration for any domain")
        print("🤖 Sophisticated error handling, context management, and tool chaining")
        print(f"📡 MCP Server: {'Connected' if self.mcp_session else 'Not connected'}")
        print(f"🔧 Available tools: {len(self.available_tools)}")
        print(f"✨ Features: Validation, Recovery, Streaming, Context Optimization")
        if self.available_tools:
            print("\nAvailable tools:")
            for tool in self.available_tools:
                print(f"  • {tool.name}: {tool.description}")
        print("\nCommands:")
        print("  'quit' or 'exit' - Exit the session")
        print("  'clear' - Reset conversation history")
        print("  'status' - Show system status")
        print("  'debug' - Toggle debug logging")
        print("-" * 60)
        while True:
            try:
                user_input = input("\n👤 You: ").strip()
                if user_input.lower() in ['quit', 'exit']:
                    break
                elif user_input.lower() == 'clear':
                    self.messages = [self.messages[0]] if self.messages else []
                    print("[Conversation history cleared]")
                elif user_input.lower() == 'status':
                    self._print_system_status()
                elif user_input.lower() == 'debug':
                    if logger.level == logging.DEBUG:
                        logger.setLevel(logging.INFO)
                        print("[Debug logging disabled]")
                    else:
                        logger.setLevel(logging.DEBUG)
                        print("[Debug logging enabled]")
                elif not user_input:
                    continue
                print("🤖 Assistant: ", end="", flush=True)
                response = await self.process_user_input(user_input)
                print(response)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Session error: {e}")
                print(f"❌ Error: {e}")
        print("\n👋 Goodbye!")
    def _print_system_status(self):
        print("\n" + "=" * 60)
        print("📊 ORCHESTRATOR STATUS")
        print("=" * 60)
        print(f"Session ID: {self._conversation_id}")
        print(f"Messages in conversation: {len(self.messages)}")
        print(f"Tools executed this session: {self._tool_call_count}")
        print(f"Session duration: {datetime.now() - self.system_state.session_start_time}")
        print(f"\nSystem State:")
        print(f"  Current directory: {self.system_state.current_directory or 'Unknown'}")
        print(f"  Last error: {self.system_state.last_error or 'None'}")
        print(f"  Commands executed: {len(self.system_state.executed_commands)}")
        print(f"\nConfiguration:")
        print(f"  Model: {GEMINI_MODEL}")
        print(f"  Max context tokens: {MAX_CONTEXT_TOKENS}")
        print(f"  Tool validation: {ENABLE_TOOL_VALIDATION}")
        print(f"  Error recovery: {ENABLE_ERROR_RECOVERY}")
        print(f"  Streaming: {ENABLE_STREAMING}")
        print(f"  Max retries: {MAX_RETRY_ATTEMPTS}")
        if self.system_state.tool_execution_history:
            recent_tools = self.system_state.tool_execution_history[-5:]
            print(f"\nRecent tool executions:")
            for tool_result in recent_tools:
                status_emoji = "✅" if tool_result.status == ToolExecutionStatus.COMPLETED else "❌"
                print(f"  {status_emoji} {tool_result.tool_name} ({tool_result.execution_time:.2f}s)")
        print("=" * 60)
    async def cleanup(self):
        logger.info("🧹 Cleaning up orchestrator...")
        if hasattr(self, 'exit_stack'):
            await self.exit_stack.aclose()
        logger.info("✅ Cleanup completed")

async def main():
    orchestrator = GeneralizedConversationalOrchestrator()
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
    if not GEMINI_API_KEY:
        print("❌ Error: GEMINI_API_KEY environment variable is required")
        print("Please set your Gemini API key in the environment variables")
        sys.exit(1)
    asyncio.run(main())
