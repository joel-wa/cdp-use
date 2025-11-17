#!/usr/bin/env python3
"""
Tool Execution Infrastructure

Tool validation, orchestration, error recovery, context management, and streaming.
"""

import os
import time
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, AsyncGenerator
from collections import deque

from mcp import ClientSession
from models import (
    SystemState, ToolExecutionResult, ToolExecutionStatus, ErrorSeverity
)
from config import (
    ENABLE_TOOL_VALIDATION, ENABLE_ERROR_RECOVERY, MAX_RETRY_ATTEMPTS,
    TOOL_EXECUTION_TIMEOUT, MAX_CONTEXT_TOKENS, ENABLE_STREAMING,
    logger
)


class ToolValidator:
    """Validates tool calls before execution"""
    
    def __init__(self, state: SystemState):
        self.state = state
        
    def validate_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate a tool call before execution"""
        if not ENABLE_TOOL_VALIDATION:
            return True, None
            
        try:
            if tool_name == "read_file":
                return self._validate_read_file(arguments)
            elif tool_name == "navigate":
                return self._validate_navigate(arguments)
            elif tool_name == "click_element_by_index":
                return self._validate_click_element_by_index(arguments)
            
            return True, None
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    def _validate_read_file(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate read_file tool call"""
        file_path = args.get("path") or args.get("filePath")
        if not file_path:
            return False, "File path is required"
        if not os.path.exists(file_path) and file_path not in self.state.file_system_cache:
            return False, f"File not found: {file_path}"
        return True, None
        
    def _validate_navigate(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate navigate tool call"""
        url = args.get("url")
        if not url:
            return False, "URL is required"
        if not (url.startswith("http://") or url.startswith("https://") or url.startswith("file://")):
            if url.startswith("www."):
                args["url"] = f"https://{url}"
            else:
                return False, "URL must start with http://, https://, or file://"
        return True, None
        
    def _validate_click_element_by_index(self, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate click element by index"""
        element_index = args.get("element_index")
        if element_index is None:
            return False, "Element index is required"
        if not isinstance(element_index, int) or element_index < 0:
            return False, "Element index must be a non-negative integer"
        return True, None


class ErrorRecoveryEngine:
    """Handles error analysis and recovery strategies"""
    
    def __init__(self, state: SystemState):
        self.state = state
        
    def analyze_error(self, tool_name: str, error: str, context: Dict[str, Any]) -> Tuple[ErrorSeverity, List[str]]:
        """Analyze error and generate recovery suggestions"""
        error_lower = error.lower()
        suggestions = []
        
        if any(keyword in error_lower for keyword in ["timeout", "network", "connection"]):
            severity = ErrorSeverity.RECOVERABLE
            suggestions.extend(["Retry after brief delay", "Check network connectivity"])
        elif any(keyword in error_lower for keyword in ["not found", "404"]):
            severity = ErrorSeverity.WARNING
            suggestions.extend(["Verify path/URL is correct", "Check if resource exists"])
        elif any(keyword in error_lower for keyword in ["permission", "access denied"]):
            severity = ErrorSeverity.CRITICAL
            suggestions.extend(["Check permissions", "Try elevated privileges"])
        else:
            severity = ErrorSeverity.RECOVERABLE
            suggestions.extend(["Retry the operation", "Check system resources"])
            
        return severity, suggestions


class ContextManager:
    """Manages conversation context with intelligent optimization"""
    
    def __init__(self, max_tokens: int = MAX_CONTEXT_TOKENS):
        self.max_tokens = max_tokens
        self.token_estimate_ratio = 4
        
    def optimize_context(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Optimize context to fit within token limits"""
        estimated_tokens = self._estimate_tokens(messages)
        
        if estimated_tokens <= self.max_tokens:
            return messages
            
        logger.info(f"Context optimization: {estimated_tokens} → {self.max_tokens} tokens")
        
        optimized = []
        system_msg = next((msg for msg in messages if msg.get("role") == "system"), None)
        if system_msg:
            optimized.append(system_msg)
            
        recent_messages = messages[-6:]
        older_messages = messages[1:-6] if len(messages) > 7 else []
        
        if older_messages:
            summarized = self._summarize_tool_chains(older_messages)
            optimized.extend(summarized)
            
        optimized.extend(recent_messages)
        return optimized
        
    def _estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Rough token estimation"""
        total_chars = sum(len(str(msg.get("content", ""))) for msg in messages)
        return total_chars // self.token_estimate_ratio
        
    def _summarize_tool_chains(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Summarize tool execution chains"""
        return [{"role": "assistant", "content": "[Tool chain summary: multiple tools executed]"}]


class ToolChainOrchestrator:
    """Orchestrates sequential tool execution with intelligent chaining"""
    
    def __init__(self, mcp_session: ClientSession, state: SystemState):
        self.mcp_session = mcp_session
        self.state = state
        self.validator = ToolValidator(state)
        self.recovery_engine = ErrorRecoveryEngine(state)
        
    async def execute_tool_chain_sequentially(self, tool_calls: List[Dict[str, Any]]) -> List[ToolExecutionResult]:
        """Execute tool calls sequentially with error handling"""
        results = []
        
        for i, tool_call in enumerate(tool_calls):
            logger.info(f"Executing tool {i+1}/{len(tool_calls)}: {tool_call['function']['name']}")
            result = await self._execute_single_tool_with_recovery(tool_call)
            results.append(result)
            self.state.update_from_tool_result(result)
            
            if result.status == ToolExecutionStatus.FAILED and not ENABLE_ERROR_RECOVERY:
                break
                    
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
        
        is_valid, validation_error = self.validator.validate_tool_call(tool_name, arguments)
        if not is_valid:
            result.status = ToolExecutionStatus.FAILED
            result.error = f"Validation failed: {validation_error}"
            return result
            
        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                result.status = ToolExecutionStatus.EXECUTING
                start_time = time.time()
                
                mcp_result = await asyncio.wait_for(
                    self.mcp_session.call_tool(tool_name, arguments),
                    timeout=TOOL_EXECUTION_TIMEOUT
                )
                
                result.result = self._process_mcp_result(mcp_result)
                result.status = ToolExecutionStatus.COMPLETED
                result.execution_time = time.time() - start_time
                result.retry_count = attempt
                
                logger.info(f"✅ Tool {tool_name} executed successfully")
                return result
                
            except asyncio.TimeoutError:
                result.error = f"Tool {tool_name} timed out"
                logger.warning(f"⏰ {result.error}")
                
            except Exception as e:
                result.error = f"Tool {tool_name} failed: {str(e)}"
                logger.warning(f"❌ {result.error}")
                
                if ENABLE_ERROR_RECOVERY and attempt < MAX_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(min(2 ** attempt, 10))
                    continue
                        
            result.status = ToolExecutionStatus.FAILED
            result.retry_count = attempt + 1
            break
                
        return result
        
    def _process_mcp_result(self, mcp_result) -> Dict[str, Any]:
        """Process raw MCP result into standardized format"""
        try:
            if hasattr(mcp_result, 'content'):
                if isinstance(mcp_result.content, list) and mcp_result.content:
                    content = mcp_result.content[0]
                    if hasattr(content, 'text'):
                        try:
                            return json.loads(content.text)
                        except json.JSONDecodeError:
                            return {"text": content.text}
                    return {"content": str(content)}
                return {"content": str(mcp_result.content)}
            return {"result": str(mcp_result)}
        except Exception as e:
            return {"error": f"Failed to process result: {str(e)}"}


class StreamingResponseManager:
    """Manages streaming responses with progress updates"""
    
    def __init__(self):
        self.enable_streaming = ENABLE_STREAMING
        
    async def stream_tool_execution(self, tool_calls: List[Dict[str, Any]], executor_func) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream tool execution progress"""
        if not self.enable_streaming:
            results = await executor_func(tool_calls)
            yield {"type": "completion", "results": results}
            return
            
        yield {"type": "planning", "content": f"Executing {len(tool_calls)} tool(s)..."}
        
        for i, tool_call in enumerate(tool_calls):
            tool_name = tool_call["function"]["name"]
            yield {
                "type": "tool_start", 
                "content": f"Executing {tool_name} ({i+1}/{len(tool_calls)})...",
                "progress": i / len(tool_calls)
            }
            
            result = await executor_func([tool_call])
            
            yield {
                "type": "tool_complete",
                "result": result[0] if result else None,
                "progress": (i + 1) / len(tool_calls)
            }
