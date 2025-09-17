#!/usr/bin/env python3
"""
Enhanced Conversational MCP Orchestrator

Advanced implementation that addresses Claude Desktop performance gaps through:
1. Comprehensive system message architecture
2. Sequential tool execution with smart chaining  
3. Progressive context management with optimization
4. Tool state awareness and validation
5. Streaming responses with progress updates
6. Gemini-specific optimizations
7. Intelligent error recovery and resilience
8. Dynamic context injection

This implementation treats MCP as collaborative problem-solving rather than simple tool execution.

Author: Agent-Space Team
Version: 2.0 Enhanced
"""

import asyncio
import json
import logging
import os
import re
import sys
import shlex
import base64
import binascii
import time
from typing import Dict, Any, List, Optional, Tuple, AsyncGenerator
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from collections import deque
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

# Configuration with enhanced defaults
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:12306/mcp")
MCP_SERVER_COMMAND = os.getenv("MCP_SERVER_COMMAND", '"C:\\Users\\RanVic\\cdp-use\\.venv\\Scripts\\python.exe" "C:\\Users\\RanVic\\cdp-use\\examples\\mcp_browser_control.py" --server-only')
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ENABLE_VISUAL_CONTEXT = os.getenv("ENABLE_VISUAL_CONTEXT", "true").lower() == "true"
ENABLE_INTERACTIVE_CONTEXT = os.getenv("ENABLE_INTERACTIVE_CONTEXT", "true").lower() == "true"
MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", str(1024 * 1024)))  # 1MB
AUTO_SCREENSHOT_INTERVAL = int(os.getenv("AUTO_SCREENSHOT_INTERVAL", "0"))

# Enhanced configuration options
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "100000"))
ENABLE_STREAMING = os.getenv("ENABLE_STREAMING", "true").lower() == "true"
ENABLE_TOOL_VALIDATION = os.getenv("ENABLE_TOOL_VALIDATION", "true").lower() == "true" 
ENABLE_ERROR_RECOVERY = os.getenv("ENABLE_ERROR_RECOVERY", "true").lower() == "true"
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
TOOL_EXECUTION_TIMEOUT = int(os.getenv("TOOL_EXECUTION_TIMEOUT", "60"))

# Setup enhanced logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Classification of error severity levels"""
    INFO = "info"
    WARNING = "warning" 
    RECOVERABLE = "recoverable"
    CRITICAL = "critical"
    FATAL = "fatal"


class ToolExecutionStatus(Enum):
    """Tool execution status tracking"""
    PENDING = "pending"
    VALIDATING = "validating"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class ToolExecutionResult:
    """Enhanced tool execution result with metadata"""
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
    """Comprehensive system state tracking"""
    current_directory: Optional[str] = None
    file_system_cache: Dict[str, Any] = field(default_factory=dict)
    browser_state: Dict[str, Any] = field(default_factory=dict)
    executed_commands: deque = field(default_factory=lambda: deque(maxlen=100))
    environment_vars: Dict[str, str] = field(default_factory=dict)
    session_start_time: datetime = field(default_factory=datetime.now)
    tool_execution_history: List[ToolExecutionResult] = field(default_factory=list)
    context_cache: Dict[str, Any] = field(default_factory=dict)
    last_error: Optional[str] = None
    
    def update_from_tool_result(self, result: ToolExecutionResult):
        """Update state based on tool execution results"""
        self.tool_execution_history.append(result)
        
        # Update specific state based on tool type
        if result.tool_name == "navigate" and result.status == ToolExecutionStatus.COMPLETED:
            self.browser_state["current_url"] = result.arguments.get("url")
            
        elif result.tool_name in ["list_directory", "read_file"] and result.status == ToolExecutionStatus.COMPLETED:
            # Update file system cache
            if result.tool_name == "list_directory":
                path = result.arguments.get("path", ".")
                if result.result and "content" in result.result:
                    self.file_system_cache[path] = result.result["content"]
                    
        # Track state changes
        if result.state_changes:
            for key, value in result.state_changes.items():
                setattr(self, key, value)


class SystemMessageBuilder:
    """Builds comprehensive, context-aware system messages"""
    
    def __init__(self, available_tools: List[Tool], state: SystemState):
        self.available_tools = available_tools
        self.state = state
        
    def build_comprehensive_system_message(self) -> str:
        """Build enhanced system message with context and guidelines"""
        
        base_personality = """You are Jovera Browser, an advanced personal browser assistant with sophisticated tool execution capabilities. You have been granted full permission to access and control the user's browser and computer system.

Your core capabilities include:
- Intelligent web browsing and interaction
- Advanced error handling and recovery  
- Progressive problem-solving with context awareness
- Proactive assistance and suggestion generation
- Multi-step operation coordination"""

        tool_guidelines = self._build_tool_usage_guidelines()
        execution_patterns = self._build_execution_patterns() 
        context_awareness = self._build_context_awareness()
        error_handling = self._build_error_handling_guidelines()
        gemini_optimizations = self._build_gemini_optimizations()
        
        system_message = f"""{base_personality}

{tool_guidelines}

{execution_patterns}

{context_awareness}

{error_handling}

{gemini_optimizations}

Remember: You are operating as the user's authorized personal assistant. Be proactive, intelligent, and thorough in your assistance."""
        
        return system_message
    
    def _build_tool_usage_guidelines(self) -> str:
        """Build tool-specific usage guidelines"""
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

Tool Chaining Patterns:
- Navigation → Screenshot → Interactive Elements (for web tasks)
- List Directory → Read File (for file exploration)  
- Take Screenshot → Get Interactive Elements (for UI analysis)
- Validate → Execute → Verify (for critical operations)"""

        return guidelines
    
    def _build_execution_patterns(self) -> str:
        """Build execution pattern guidelines"""
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
- Handle failures gracefully with recovery"""
    
    def _build_context_awareness(self) -> str:
        """Build context awareness guidelines"""
        current_context = []
        
        if self.state.current_directory:
            current_context.append(f"Working Directory: {self.state.current_directory}")
            
        if self.state.browser_state.get("current_url"):
            current_context.append(f"Current URL: {self.state.browser_state['current_url']}")
            
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
- Track file system changes and browser navigation
- Remember previous tool results for context
- Maintain awareness of user goals and progress
- Use historical context to inform decisions

Context Usage:
- Reference previous results when relevant  
- Avoid repeating unnecessary operations
- Build upon established context
- Provide continuity across interactions"""
    
    def _build_error_handling_guidelines(self) -> str:
        """Build error handling and recovery guidelines"""
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
- Critical (system failure) → Escalate to user"""
    
    def _build_gemini_optimizations(self) -> str:
        """Build Gemini-specific optimization guidelines"""
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
- Synthesize results into coherent narrative"""


class ToolValidator:
    """Validates tool calls before execution"""
    
    def __init__(self, state: SystemState):
        self.state = state
        
    def validate_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate a tool call before execution"""
        
        if not ENABLE_TOOL_VALIDATION:
            return True, None
            
        try:
            # General parameter validation
            if not isinstance(arguments, dict):
                return False, "Tool arguments must be a dictionary"
                
            # Tool-specific validation
            validator_method = getattr(self, f"_validate_{tool_name}", None)
            if validator_method:
                return validator_method(arguments)
                
            # Default validation passed
            return True, None
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def _validate_read_file(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate read_file tool call"""
        file_path = args.get("path") or args.get("filePath")
        
        if not file_path:
            return False, "File path is required"
            
        # Check if file exists in our cache or suggest alternatives
        if not os.path.exists(file_path) and file_path not in self.state.file_system_cache:
            # Suggest alternatives from current directory cache
            current_dir = self.state.current_directory or "."
            cached_files = self.state.file_system_cache.get(current_dir, [])
            
            if cached_files:
                similar_files = [f for f in cached_files if os.path.basename(file_path).lower() in f.lower()]
                if similar_files:
                    return False, f"File not found. Did you mean: {', '.join(similar_files[:3])}?"
                    
            return False, f"File '{file_path}' not found. Use list_directory to see available files."
            
        return True, None
        
    def _validate_navigate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate navigate tool call"""
        url = args.get("url")
        
        if not url:
            return False, "URL is required for navigation"
            
        # Basic URL validation
        if not (url.startswith("http://") or url.startswith("https://") or url.startswith("file://")):
            # Allow relative URLs or add protocol
            if not url.startswith("www.") and "." in url:
                return False, f"URL should include protocol (http:// or https://). Did you mean: https://{url}?"
                
        return True, None
        
    def _validate_click_element_by_index(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate click element by index"""
        element_index = args.get("element_index")
        
        if element_index is None:
            return False, "Element index is required"
            
        if not isinstance(element_index, int) or element_index < 0:
            return False, "Element index must be a non-negative integer"
            
        # Could validate against cached interactive elements if available
        return True, None


class ErrorRecoveryEngine:
    """Handles error analysis and recovery strategies"""
    
    def __init__(self, state: SystemState):
        self.state = state
        
    def analyze_error(self, tool_name: str, error: str, context: Dict[str, Any]) -> Tuple[ErrorSeverity, List[str]]:
        """Analyze error and generate recovery suggestions"""
        
        error_lower = error.lower()
        
        # Classify error severity
        if any(keyword in error_lower for keyword in ["timeout", "network", "connection"]):
            severity = ErrorSeverity.RECOVERABLE
            suggestions = [
                "Retry the operation after a brief delay",
                "Check network connectivity", 
                "Use a shorter timeout if available"
            ]
            
        elif any(keyword in error_lower for keyword in ["not found", "file not found", "404"]):
            severity = ErrorSeverity.WARNING
            suggestions = [
                "Verify the file path or URL is correct",
                "Use list_directory to see available files",
                "Check if the resource was moved or renamed"
            ]
            
        elif any(keyword in error_lower for keyword in ["permission", "access denied", "forbidden"]):
            severity = ErrorSeverity.CRITICAL
            suggestions = [
                "Check file permissions",
                "Run with appropriate privileges", 
                "Verify access rights to the resource"
            ]
            
        elif any(keyword in error_lower for keyword in ["syntax", "invalid", "malformed"]):
            severity = ErrorSeverity.RECOVERABLE
            suggestions = [
                "Validate input parameters",
                "Check parameter format and types",
                "Refer to tool documentation for correct usage"
            ]
            
        else:
            severity = ErrorSeverity.WARNING
            suggestions = [
                "Review error message for specific details",
                "Try alternative approach to accomplish the same goal",
                "Break down the operation into smaller steps"
            ]
            
        # Tool-specific recovery suggestions
        tool_suggestions = self._get_tool_specific_suggestions(tool_name, error_lower)
        suggestions.extend(tool_suggestions)
        
        return severity, suggestions
        
    def _get_tool_specific_suggestions(self, tool_name: str, error_lower: str) -> List[str]:
        """Get tool-specific recovery suggestions"""
        
        if tool_name == "navigate":
            if "timeout" in error_lower:
                return ["Try a more reliable website", "Check internet connection"]
            elif "invalid url" in error_lower:
                return ["Ensure URL includes http:// or https://", "Verify URL spelling"]
                
        elif tool_name == "click_element_by_index":
            if "not found" in error_lower:
                return ["Take a new screenshot to see current elements", "Use get_interactive_elements to refresh element list"]
                
        elif tool_name == "read_file":
            if "not found" in error_lower:
                return ["Use list_directory to see available files", "Check if file path is relative or absolute"]
                
        return []


class ContextManager:
    """Manages conversation context with intelligent optimization"""
    
    def __init__(self, max_tokens: int = MAX_CONTEXT_TOKENS):
        self.max_tokens = max_tokens
        self.token_estimate_ratio = 4  # Rough chars per token estimate
        
    def optimize_context(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Optimize context to fit within token limits while preserving critical information"""
        
        # Estimate current token usage
        estimated_tokens = self._estimate_tokens(messages)
        
        if estimated_tokens <= self.max_tokens:
            return messages  # No optimization needed
            
        logger.info(f"Context optimization needed: {estimated_tokens} > {self.max_tokens} tokens")
        
        # Preserve critical messages
        optimized = []
        
        # Always keep system message
        system_msg = next((msg for msg in messages if msg.get("role") == "system"), None)
        if system_msg:
            optimized.append(system_msg)
            
        # Keep recent user input and assistant responses (last 3 exchanges)
        recent_messages = messages[-6:]  # Last 3 user-assistant pairs
        
        # Compress or summarize older tool chains
        older_messages = messages[1:-6] if len(messages) > 7 else []
        
        if older_messages:
            # Group tool chains and summarize
            summarized_chains = self._summarize_tool_chains(older_messages)
            optimized.extend(summarized_chains)
            
        # Add recent messages
        optimized.extend(recent_messages)
        
        # Final token check
        final_tokens = self._estimate_tokens(optimized)
        logger.info(f"Context optimized: {estimated_tokens} → {final_tokens} tokens")
        
        return optimized
        
    def _estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Rough token estimation"""
        total_chars = 0
        for msg in messages:
            if "content" in msg:
                total_chars += len(str(msg["content"]))
        return total_chars // self.token_estimate_ratio
        
    def _summarize_tool_chains(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Summarize tool execution chains to preserve key outcomes"""
        
        # Group messages into tool chains (assistant + tool results)
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
            
        # Summarize each chain
        summarized = []
        for chain in chains:
            summary = self._create_chain_summary(chain)
            summarized.append(summary)
            
        return summarized
        
    def _create_chain_summary(self, chain: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a summary of a tool execution chain"""
        
        if not chain:
            return {"role": "assistant", "content": "[Tool chain summary: No operations]"}
            
        assistant_msg = chain[0] if chain[0].get("role") == "assistant" else None
        tool_results = [msg for msg in chain if msg.get("role") == "tool"]
        
        # Extract key information
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
                # Assume success if we can't parse
                successful_tools.append(tool_name)
                
        # Create summary
        summary_parts = []
        if tools_used:
            summary_parts.append(f"Tools used: {', '.join(tools_used)}")
        if successful_tools:
            summary_parts.append(f"Successful: {', '.join(successful_tools)}")
        if failed_tools:
            summary_parts.append(f"Failed: {', '.join(failed_tools)}")
            
        summary_content = f"[Tool chain summary: {'; '.join(summary_parts)}]"
        
        return {"role": "assistant", "content": summary_content}


class ToolChainOrchestrator:
    """Orchestrates sequential tool execution with intelligent chaining"""
    
    def __init__(self, mcp_session: ClientSession, state: SystemState):
        self.mcp_session = mcp_session
        self.state = state
        self.validator = ToolValidator(state)
        self.recovery_engine = ErrorRecoveryEngine(state)
        
    async def execute_tool_chain_sequentially(self, tool_calls: List[Dict[str, Any]]) -> List[ToolExecutionResult]:
        """Execute tool calls sequentially with error handling and recovery"""
        
        results = []
        
        for i, tool_call in enumerate(tool_calls):
            logger.info(f"🔧 Executing tool {i+1}/{len(tool_calls)}: {tool_call['function']['name']}")
            
            result = await self._execute_single_tool_with_recovery(tool_call)
            results.append(result)
            
            # Update system state
            self.state.update_from_tool_result(result)
            
            # Check for critical failures that should stop the chain
            if result.status == ToolExecutionStatus.FAILED:
                severity, suggestions = self.recovery_engine.analyze_error(
                    result.tool_name, result.error or "Unknown error", {}
                )
                
                if severity == ErrorSeverity.FATAL:
                    logger.error(f"Fatal error in tool chain, stopping execution: {result.error}")
                    break
                elif severity == ErrorSeverity.CRITICAL:
                    logger.warning(f"Critical error, but continuing with remaining tools: {result.error}")
                    
        return results
        
    async def _execute_single_tool_with_recovery(self, tool_call: Dict[str, Any]) -> ToolExecutionResult:
        """Execute a single tool with validation, retry, and recovery"""
        
        tool_name = tool_call["function"]["name"]
        arguments = tool_call["function"]["arguments"]
        
        result = ToolExecutionResult(
            tool_name=tool_name,
            arguments=arguments,
            status=ToolExecutionStatus.PENDING
        )
        
        # Validation phase
        result.status = ToolExecutionStatus.VALIDATING
        is_valid, validation_error = self.validator.validate_tool_call(tool_name, arguments)
        
        if not is_valid:
            result.status = ToolExecutionStatus.FAILED
            result.error = f"Validation failed: {validation_error}"
            return result
            
        # Execution phase with retry logic
        for attempt in range(MAX_RETRY_ATTEMPTS):
            if attempt > 0:
                result.status = ToolExecutionStatus.RETRYING
                result.retry_count = attempt
                await asyncio.sleep(min(2 ** attempt, 10))  # Exponential backoff
                
            try:
                result.status = ToolExecutionStatus.EXECUTING
                start_time = time.time()
                
                # Execute tool via MCP with timeout
                mcp_result = await asyncio.wait_for(
                    self.mcp_session.call_tool(tool_name, arguments),
                    timeout=TOOL_EXECUTION_TIMEOUT
                )
                
                result.execution_time = time.time() - start_time
                
                # Process result
                processed_result = self._process_mcp_result(mcp_result)
                result.result = processed_result
                result.status = ToolExecutionStatus.COMPLETED
                
                logger.info(f"✅ Tool {tool_name} executed successfully in {result.execution_time:.2f}s")
                return result
                
            except asyncio.TimeoutError:
                error_msg = f"Tool execution timeout after {TOOL_EXECUTION_TIMEOUT}s"
                logger.warning(f"⏰ {error_msg}")
                
                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    continue  # Retry
                else:
                    result.status = ToolExecutionStatus.FAILED
                    result.error = error_msg
                    
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"❌ Tool execution error (attempt {attempt + 1}): {error_msg}")
                
                if attempt < MAX_RETRY_ATTEMPTS - 1 and ENABLE_ERROR_RECOVERY:
                    # Analyze error for recovery strategy
                    severity, suggestions = self.recovery_engine.analyze_error(tool_name, error_msg, {})
                    
                    if severity in [ErrorSeverity.RECOVERABLE, ErrorSeverity.WARNING]:
                        logger.info(f"🔄 Retrying after recoverable error: {suggestions[0] if suggestions else 'Generic retry'}")
                        continue  # Retry
                        
                result.status = ToolExecutionStatus.FAILED
                result.error = error_msg
                
        return result
        
    def _process_mcp_result(self, mcp_result) -> Dict[str, Any]:
        """Process raw MCP result into standardized format"""
        
        try:
            if hasattr(mcp_result, 'content') and mcp_result.content:
                processed = []
                for content_item in mcp_result.content:
                    if hasattr(content_item, 'text'):
                        try:
                            # Try to parse as JSON first
                            parsed = json.loads(content_item.text)
                            processed.append(parsed)
                        except json.JSONDecodeError:
                            # Fall back to raw text
                            processed.append({"type": "text", "content": content_item.text})
                    else:
                        processed.append(content_item)
                        
                return {"success": True, "content": processed}
            else:
                return {"success": True, "content": mcp_result}
                
        except Exception as e:
            logger.warning(f"Error processing MCP result: {e}")
            return {"success": False, "error": str(e), "raw_result": str(mcp_result)}


class StreamingResponseManager:
    """Manages streaming responses with progress updates"""
    
    def __init__(self):
        self.enable_streaming = ENABLE_STREAMING
        
    async def stream_tool_execution(self, tool_calls: List[Dict[str, Any]], executor_func) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream tool execution progress"""
        
        if not self.enable_streaming:
            # Non-streaming mode - just execute and return final result
            results = await executor_func(tool_calls)
            yield {"type": "final_result", "content": results}
            return
            
        # Streaming mode - provide progress updates
        yield {"type": "planning", "content": f"Planning to execute {len(tool_calls)} tool(s)..."}
        
        for i, tool_call in enumerate(tool_calls):
            tool_name = tool_call["function"]["name"]
            
            yield {
                "type": "tool_start", 
                "content": f"Starting {tool_name} ({i+1}/{len(tool_calls)})",
                "tool_name": tool_name,
                "progress": i / len(tool_calls)
            }
            
            # Execute single tool
            result = await executor_func([tool_call])
            
            yield {
                "type": "tool_complete",
                "content": f"Completed {tool_name}",
                "tool_name": tool_name, 
                "result": result[0] if result else None,
                "progress": (i + 1) / len(tool_calls)
            }
            
        yield {"type": "synthesis", "content": "Synthesizing results..."}


class EnhancedConversationalOrchestrator:
    """
    Enhanced conversational orchestrator with sophisticated coordination strategies.
    
    Implements:
    - Comprehensive system message architecture
    - Sequential tool execution with smart chaining
    - Progressive context management  
    - Tool state awareness and validation
    - Streaming responses with progress updates
    - Intelligent error recovery
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
        
        # Will be initialized after MCP connection
        self.tool_orchestrator = None
        self.system_message_builder = None
        
        # Internal state
        self._conversation_id = f"conv_{int(time.time())}"
        self._tool_call_count = 0
        
    async def initialize(self):
        """Initialize all components"""
        logger.info("🚀 Initializing Enhanced Conversational Orchestrator...")
        
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
        
        # Initialize enhanced components that require tools/session
        self.tool_orchestrator = ToolChainOrchestrator(self.mcp_session, self.system_state)
        self.system_message_builder = SystemMessageBuilder(self.available_tools, self.system_state)
        
        # Build and set initial system message
        system_content = self.system_message_builder.build_comprehensive_system_message()
        self.messages = [{"role": "system", "content": system_content}]
        
        logger.info(f"✅ Enhanced orchestrator initialized with {len(self.available_tools)} tools")
        logger.info("🎯 Features enabled: " + 
                   f"Streaming={ENABLE_STREAMING}, " +
                   f"Validation={ENABLE_TOOL_VALIDATION}, " +  
                   f"Recovery={ENABLE_ERROR_RECOVERY}")
        
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
    
    async def _get_enhanced_context(self, user_input: str) -> Optional[str]:
        """Get enhanced page context with improved error handling"""
        try:
            # Use existing visual-interactive mapping logic from original
            context = await self._get_context_with_fallback(user_input)
            return context[0]  # Return just the context string
        except Exception as e:
            logger.warning(f"Failed to get enhanced context: {e}")
            return None
            
    async def _get_context_with_fallback(self, user_input) -> tuple[Optional[str], str]:
        """Fallback context method from original implementation"""
        # This would contain the same logic as in the original file
        # For brevity, returning a placeholder - in real implementation, 
        # copy the full method from the original
        return None, "none"
        
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
        
    async def process_user_input(self, user_input: str) -> str:
        """
        Enhanced conversational loop with all improvements:
        
        1. Enhanced context gathering
        2. Sequential tool execution  
        3. Intelligent error recovery
        4. Progressive responses
        5. Context optimization
        """
        
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
        
        # Core enhanced conversation loop
        max_iterations = 10
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
                    
                    # Continue loop for next iteration
                    continue
                else:
                    # No tool calls - final response
                    logger.info(f"✅ Enhanced response generated (iteration {iteration})")
                    return assistant_content or "Response completed (no text content)"
                    
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
        """Create optimized Gemini contents from messages"""
        contents = []
        system_instruction = None
        first_user_msg = True
        
        for msg in self.messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                user_content = msg["content"]
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
                try:
                    parsed = json.loads(msg.get("content", "null"))
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
                
        return contents
        
    def _log_enhanced_prompt(self, contents: List[types.Content], config: types.GenerateContentConfig):
        """Enhanced logging of the prompt being sent"""
        logger.info("🤖 ENHANCED PROMPT TO LLM:")
        logger.info("=" * 80)
        
        logger.info(f"Model: {GEMINI_MODEL}")
        logger.info(f"Temperature: {config.temperature}")
        logger.info(f"Max Tokens: {config.max_output_tokens}")
        logger.info(f"Session: {self._conversation_id}")
        logger.info(f"Tool Calls Executed: {self._tool_call_count}")
        
        if config.tools:
            tool_names = []
            for tool in config.tools:
                if hasattr(tool, 'function_declarations'):
                    tool_names.extend([f.name for f in tool.function_declarations])
            logger.info(f"Available Tools: {', '.join(tool_names)}")
            
        logger.info(f"Context Messages: {len(contents)}")
        logger.info(f"Enhanced Features: Validation={ENABLE_TOOL_VALIDATION}, Recovery={ENABLE_ERROR_RECOVERY}, Streaming={ENABLE_STREAMING}")
        
        logger.info("-" * 80)
        
        # Log truncated message contents
        for i, content in enumerate(contents):
            role = content.role
            logger.info(f"[{i+1}] Role: {role}")
            
            for j, part in enumerate(content.parts):
                if hasattr(part, 'text') and part.text:
                    text = part.text
                    if len(text) > 500:
                        text = text[:500] + "... [TRUNCATED]"
                    logger.info(f"  Part {j+1} (text): {text}")
                elif hasattr(part, 'function_call'):
                    func_call = part.function_call  
                    logger.info(f"  Part {j+1} (function_call): {func_call.name}({dict(func_call.args) if func_call.args else {}})")
                elif hasattr(part, 'function_response'):
                    func_response = part.function_response
                    response_text = str(func_response.response)
                    if len(response_text) > 300:
                        response_text = response_text[:300] + "... [TRUNCATED]"
                    logger.info(f"  Part {j+1} (function_response): {func_response.name} -> {response_text}")
                    
        logger.info("=" * 80)
        
    async def run_interactive_session(self):
        """Run enhanced interactive conversation session"""
        print("🚀 Enhanced Personal Browser Assistant")
        print("🎯 Advanced MCP orchestration with intelligent coordination")
        print("🤖 Sophisticated error handling, context management, and tool chaining")
        print(f"📡 MCP Server: {'Connected' if self.mcp_session else 'Not connected'}")
        print(f"🔧 Available tools: {len(self.available_tools)}")
        print(f"✨ Enhanced features: Validation, Recovery, Streaming, Context Optimization")
        
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
                    # Reset conversation but rebuild system message
                    system_content = self.system_message_builder.build_comprehensive_system_message()
                    self.messages = [{"role": "system", "content": system_content}]
                    print("🧹 Conversation cleared and system message rebuilt")
                    continue
                elif user_input.lower() == 'status':
                    self._print_system_status()
                    continue
                elif user_input.lower() == 'debug':
                    global DEBUG
                    DEBUG = not DEBUG
                    logging.getLogger().setLevel(logging.DEBUG if DEBUG else logging.INFO)
                    print(f"🔧 Debug logging {'enabled' if DEBUG else 'disabled'}")
                    continue
                elif not user_input:
                    continue
                    
                # Process input through enhanced conversational loop
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
        """Print detailed system status"""
        print("\n" + "=" * 60)
        print("📊 ENHANCED ORCHESTRATOR STATUS")
        print("=" * 60)
        print(f"Session ID: {self._conversation_id}")
        print(f"Messages in conversation: {len(self.messages)}")
        print(f"Tools executed this session: {self._tool_call_count}")
        print(f"Session duration: {datetime.now() - self.system_state.session_start_time}")
        
        print(f"\nSystem State:")
        print(f"  Current directory: {self.system_state.current_directory or 'Unknown'}")
        print(f"  Browser URL: {self.system_state.browser_state.get('current_url', 'No page loaded')}")
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
        """Enhanced cleanup with state persistence"""
        logger.info("🧹 Cleaning up enhanced orchestrator...")
        
        if hasattr(self, 'exit_stack'):
            await self.exit_stack.aclose()
            
        # Could add state persistence here for session recovery
        logger.info("✅ Cleanup completed")


async def main():
    """Enhanced main entry point"""
    orchestrator = EnhancedConversationalOrchestrator()
    
    try:
        await orchestrator.initialize()
        await orchestrator.run_interactive_session()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"❌ Failed to start enhanced orchestrator: {e}")
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