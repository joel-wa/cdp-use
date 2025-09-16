#!/usr/bin/env python3
"""
Gemini MCP Orchestrator Integration

Integrates the AsyncAdvancedOrchestrator with Gemini MCP Client for goal-oriented
task execution with planning, execution, and review cycles.

Author: Agent-Space Team
"""

import asyncio
import json
import logging
import shlex
import subprocess
from typing import Dict, Any, List, Optional
from contextlib import AsyncExitStack
import os
import sys

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'BrowserAgent', 'clients', 'gemini'))

from async_orchestrator import AsyncAdvancedOrchestrator
from google import genai
from google.genai import types
from dotenv import load_dotenv

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
MCP_SERVER_COMMAND = os.getenv("MCP_SERVER_COMMAND", "")  # Command to run stdio MCP server
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "auto")  # "http", "stdio", or "auto"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Setup logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LLM:
    """
    LLM wrapper class for Gemini API interactions with real MCP integration
    """
    def __init__(self, genai_client=None, tools: List = None, mcp_session=None):
        self.genai_client = genai_client
        self.tools = tools or []
        self.mcp_session = mcp_session
        self.model = GEMINI_MODEL

    async def generate_execution(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the specific action planned by the planner using MCP tools
        """
        try:
            # Get planner's decision
            planner = context.get("planner", {})
            tool_to_use = planner.get("tool_to_use", "")
            tool_parameters = planner.get("tool_parameters", "{}")
            next_action = planner.get("next_action", "No action specified")
            goal = context.get("input", "No goal specified")
            
            # Parse tool parameters
            try:
                if isinstance(tool_parameters, str):
                    tool_params = json.loads(tool_parameters) if tool_parameters.strip() else {}
                else:
                    tool_params = tool_parameters or {}
            except json.JSONDecodeError:
                tool_params = {}
                logger.warning(f"Failed to parse tool parameters: {tool_parameters}")
            
            # Validate tool exists in available tools
            available_tool_names = [tool.name for tool in self.tools] if self.tools else []
            if tool_to_use and tool_to_use != "none" and tool_to_use not in available_tool_names:
                logger.warning(f"Tool '{tool_to_use}' not in available tools: {available_tool_names}")
                tool_to_use = "none"  # Prevent execution of non-existent tool
            
            prompt = f"""
            You are an executor AI for a web browsing agent. Your job is to execute the specific action planned by the planner.
            
            GOAL: {goal}
            PLANNED ACTION: {next_action}
            TOOL TO USE: {tool_to_use}
            TOOL PARAMETERS: {json.dumps(tool_params, indent=2)}
            AVAILABLE TOOLS: {available_tool_names}
            
            Your task:
            1. If a valid tool is specified and exists, execute it with the given parameters
            2. If no tool or invalid tool, provide guidance on what should be done
            3. Report the results of the tool execution
            
            Execute the planned action and return a JSON object with:
            {{
                "action_executed": "Description of what was executed",
                "tool_used": "Name of the tool that was called",
                "execution_status": "success/failed/skipped",
                "tool_results": "Results from the tool execution",
                "next_steps": "What should happen next based on results"
            }}
            """
            
            # Execute the tool if specified and valid
            tool_results = "No tool executed"
            execution_status = "skipped"
            tool_used = "none"
            
            if tool_to_use and tool_to_use != "none" and tool_to_use in available_tool_names and self.mcp_session:
                try:
                    # Execute the tool through MCP
                    tool_result = await self._execute_tool(tool_to_use, tool_params)
                    
                    if tool_result["success"]:
                        execution_status = "success"
                        tool_used = tool_to_use
                        
                        # Extract text content from results
                        result_texts = []
                        for content_item in tool_result["content"]:
                            if content_item["type"] == "text":
                                result_texts.append(content_item["text"])
                        
                        tool_results = "\n".join(result_texts) if result_texts else "Tool executed successfully but no text output"
                    else:
                        execution_status = "failed"
                        tool_used = tool_to_use
                        tool_results = f"Tool execution failed: {tool_result.get('content', [{}])[0].get('text', 'Unknown error')}"
                        
                except Exception as e:
                    execution_status = "failed"
                    tool_used = tool_to_use
                    tool_results = f"Tool execution error: {str(e)}"
                    logger.error(f"Error executing tool {tool_to_use}: {e}")
            elif tool_to_use and tool_to_use != "none":
                execution_status = "failed"
                tool_used = tool_to_use
                tool_results = f"Tool '{tool_to_use}' not available. Available tools: {available_tool_names}"
            
            # Generate response using Gemini for analysis
            enhanced_prompt = f"{prompt}\n\nACTUAL EXECUTION RESULTS:\n- Tool: {tool_used}\n- Status: {execution_status}\n- Results: {tool_results}"
            response = await self._generate_content(enhanced_prompt, use_tools=False)
            
            return {
                "action_executed": response.get("action_executed", next_action),
                "tool_used": tool_used,
                "execution_status": execution_status,
                "tool_results": tool_results,
                "next_steps": response.get("next_steps", "Continue to next role")
            }
            
        except Exception as e:
            logger.error(f"Error in generate_execution: {e}")
            return {
                "action_executed": f"Execution error: {str(e)}",
                "tool_used": "none",
                "execution_status": "failed",
                "tool_results": "Execution failed due to error",
                "next_steps": "Review error and retry"
            }

    async def generate_review(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate review and analysis of execution results
        """
        try:
            goal = context.get("input", "No goal specified")
            plan = context.get("planner", {}).get("plan", "No plan available")
            execution = context.get("executor", {})
            critique = context.get("critic", {}).get("critique", "No critique available")
            
            prompt = f"""
            You are a reviewer AI. Analyze the execution results and determine if the goal has been achieved.
            
            GOAL: {goal}
            PLAN: {plan}
            EXECUTION RESULTS: {json.dumps(execution, indent=2)}
            CRITIQUE: {critique}
            
            Full context: {json.dumps(context, indent=2)}
            
            Provide a comprehensive review. Return a JSON object with:
            {{
                "summary": "Summary of what was accomplished",
                "goal_status": "achieved/in_progress/failed",
                "recommendations": "What should be done next",
                "completion_assessment": "Detailed assessment of goal completion"
            }}
            
            IMPORTANT: If you determine the goal has been fully achieved, include the exact text "goal_achieved" 
            somewhere in your response (in summary, recommendations, or completion_assessment).
            """
            
            response = await self._generate_content(prompt, use_tools=False)
            
            return {
                "summary": response.get("summary", f"Unable to generate review summary. Response: {response}"),
                "goal_status": response.get("goal_status", "unknown"),
                "recommendations": response.get("recommendations", f"No recommendations available. Raw response: {response}"),
                "completion_assessment": response.get("completion_assessment", f"Assessment failed. Response: {response}")
            }
            
        except Exception as e:
            logger.error(f"Error in generate_review: {e}")
            return {
                "summary": f"Review error: {str(e)}",
                "goal_status": "failed",
                "recommendations": "Fix review error and retry",
                "completion_assessment": "Review failed"
            }

    async def generate_plan(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate execution plan with Gemini API - Web Browsing Agent
        """
        try:
            goal = context.get("input", "")
            previous_results = context.get("reviewer", {})
            execution_context = context.get("executor", {})
            
            # Get available tools for context - show ALL tools dynamically
            available_tools_desc = []
            if self.tools:
                for tool in self.tools:
                    # Include tool parameters/schema info if available
                    tool_info = f"- {tool.name}: {tool.description}"
                    if hasattr(tool, 'inputSchema') and tool.inputSchema:
                        # Add parameter info if available
                        if isinstance(tool.inputSchema, dict) and 'properties' in tool.inputSchema:
                            params = list(tool.inputSchema['properties'].keys())
                            if params:
                                tool_info += f" (Parameters: {', '.join(params)})"
                    available_tools_desc.append(tool_info)
            
            tools_context = "\n".join(available_tools_desc) if available_tools_desc else "No tools available"
            
            prompt = f"""
            You are a Web Browsing Planner AI. Your role is to decide the SINGLE NEXT ACTION to take toward achieving the goal.
            
            GOAL: {goal}
            
            Available MCP Tools (use EXACT tool names from this list):
            {tools_context}
            
            Previous iteration results: {json.dumps(previous_results, indent=2)}
            Last execution results: {json.dumps(execution_context, indent=2)}
            
            You are part of a web browsing agent system. Your job is to:
            1. Analyze the current state and what has been accomplished
            2. Decide the SINGLE NEXT ACTION to take (not a multi-step plan)
            3. Specify which tool from the available tools list should be used for this action
            4. If the goal is already achieved, set completion_status to "goal_achieved"
            
            CRITICAL REQUIREMENTS:
            - Use ONLY tool names from the "Available MCP Tools" list above
            - Do NOT make up tool names or use hardcoded tool names
            - Focus on ONE action at a time, not multiple steps
            - If no suitable tool is available, suggest the closest available tool or set tool_to_use to "none"
            
            Return a JSON object with:
            {{
                "next_action": "Single specific action to take next",
                "tool_to_use": "EXACT name from available tools list (or 'none' if no suitable tool)",
                "tool_parameters": "JSON object with parameters needed for the tool",
                "reasoning": "Why this is the logical next step and why this tool was chosen",
                "completion_status": "goal_achieved if done, otherwise in_progress"
            }}
            """
            
            response = await self._generate_content(prompt, use_tools=False)
            
            # Validate that the selected tool exists in available tools
            selected_tool = response.get("tool_to_use", "none")
            available_tool_names = [tool.name for tool in self.tools] if self.tools else []
            
            if selected_tool != "none" and selected_tool not in available_tool_names:
                logger.warning(f"Planner selected non-existent tool: {selected_tool}. Available tools: {available_tool_names}")
                # Fall back to first available tool or none
                fallback_tool = available_tool_names[0] if available_tool_names else "none"
                response["tool_to_use"] = fallback_tool
                response["reasoning"] = f"Original tool '{selected_tool}' not available. Using '{fallback_tool}' instead. {response.get('reasoning', '')}"
            
            return {
                "next_action": response.get("next_action", f"Work toward goal: {goal}"),
                "tool_to_use": response.get("tool_to_use", "none"),
                "tool_parameters": response.get("tool_parameters", "{}"),
                "reasoning": response.get("reasoning", "Planning step toward goal"),
                "completion_status": response.get("completion_status", "in_progress")
            }
            
        except Exception as e:
            logger.error(f"Error in generate_plan: {e}")
            return {
                "next_action": f"Planning error: {str(e)}",
                "tool_to_use": "none",
                "tool_parameters": "{}",
                "reasoning": "Error occurred during planning",
                "completion_status": "error"
            }

    async def generate_critique(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate critique and analysis with Gemini API
        """
        try:
            plan = context.get("planner", {}).get("plan", "No plan")
            execution = context.get("executor", {})
            goal = context.get("input", "No goal specified")
            
            prompt = f"""
            You are a critic AI. Analyze the plan and execution results for potential issues and improvements.
            
            GOAL: {goal}
            PLAN: {plan}
            EXECUTION RESULTS: {json.dumps(execution, indent=2)}
            
            Full context: {json.dumps(context, indent=2)}
            
            Provide critical analysis. Return a JSON object with:
            {{
                "critique": "Detailed critique of the plan and execution",
                "suggestions": "Specific suggestions for improvement",
                "risk_assessment": "Assessment of potential risks and issues", 
                "quality_score": "Overall quality assessment (poor/fair/good/excellent)"
            }}
            
            Focus on identifying potential problems, edge cases, and areas for improvement.
            """
            
            response = await self._generate_content(prompt, use_tools=False)
            
            return {
                "critique": response.get("critique", f"Unable to generate critique. Response: {response}"),
                "suggestions": response.get("suggestions", f"No suggestions available. Raw response: {response}"),
                "risk_assessment": response.get("risk_assessment", f"Cannot assess risk. Response: {response}"),
                "quality_score": response.get("quality_score", f"Quality assessment failed. Response: {response}")
            }
            
        except Exception as e:
            logger.error(f"Error in generate_critique: {e}")
            return {
                "critique": f"Critique error: {str(e)}",
                "suggestions": "Fix error and retry",
                "risk_assessment": "High risk due to error",
                "quality_score": "Failed"
            }

    async def _generate_content(self, prompt: str, use_tools: bool = False, web_snapShot_path: str = None) -> Dict[str, Any]:
        """
        Generate content using Gemini API with proper integration (like gemini_mcp_client.py)
        """
        try:
            logger.info(f"🚀 Generating content with Gemini API. Use tools: {use_tools}")
            logger.debug(f"Prompt preview: {prompt[:200]}...")

            if web_snapShot_path:
                logger.info("Proceeding with VISUAL MODE Planning")
                prompt+= """
                Current Webpage screenshot(Use this to understand what is currently being shown on the website):
                """

                with open(web_snapShot_path, 'rb') as f:
                    image_bytes = f.read()

                image = types.Part.from_bytes(
                    data=image_bytes, mime_type="image/jpeg"
                )
                contents = [
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type='image/jpeg',
                    ),
                    prompt
                ]
            else:
                logger.warning("Proceeding with TEXT-ONLY Planning")
                # Build content structure for Gemini API
                contents = [
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=prompt)],
                    ),
                ]
            
            # Convert tools to Gemini format
            tools = self._convert_tools_to_gemini_format() if use_tools and self.tools else []
            
            # Create generate content config with JSON schema for consistency
            response_schema = self._get_response_schema(prompt)
            config = types.GenerateContentConfig(
                tools=tools if tools else None,
                temperature=0.7,
                max_output_tokens=2048,
                response_mime_type="application/json",
                response_schema=response_schema,
            )
            
            logger.info(f"Using {len(tools)} tools for this request" if tools else "No tools being used")
            
            # Check if genai_client is available
            if not self.genai_client:
                logger.error("❌ No Gemini client available")
                return self._create_error_response("No Gemini client configured", prompt)
            
            # Generate response using direct genai_client (like in gemini_mcp_client.py)
            logger.info("📡 Calling Gemini API...")
            response = self.genai_client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config
            )
            logger.info("✅ Received response from Gemini API")
            
            response_text = ""
            tool_calls_made = []
            
            # Process the response (copied from gemini_mcp_client.py)
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                logger.info(f"📥 Processing candidate response")
                
                if hasattr(candidate, 'content') and candidate.content:
                    logger.info(f"📄 Found content with {len(candidate.content.parts)} parts")
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_text += part.text
                            logger.debug(f"📝 Added text part: {part.text[:100]}...")
                        
                        elif hasattr(part, 'function_call') and part.function_call:
                            # Handle function/tool calls (copied from gemini_mcp_client.py)
                            function_call = part.function_call
                            tool_name = function_call.name
                            tool_args = dict(function_call.args) if function_call.args else {}
                            
                            logger.info(f"🔧 Function call detected: {tool_name}")
                            # Execute the tool
                            tool_result = await self._execute_tool(tool_name, tool_args)
                            tool_calls_made.append({
                                "tool": tool_name,
                                "args": tool_args,
                                "result": tool_result
                            })
                            
                            # Add tool result to response
                            if tool_result["success"]:
                                for content_item in tool_result["content"]:
                                    if content_item["type"] == "text":
                                        response_text += f"\n\n**Tool Result ({tool_name}):**\n{content_item['text']}"
                            else:
                                response_text += f"\n\n**Tool Error ({tool_name}):** Tool execution failed"
                else:
                    logger.warning("⚠️ No content found in candidate")
            else:
                logger.warning("⚠️ No candidates found in response")
                logger.debug(f"Response object: {response}")
            
            logger.info(f"📊 Response text length: {len(response_text)}")
            logger.debug(f"Raw response text: {response_text[:500]}...")
            
            # Parse JSON response or create structured response
            try:
                if response_text.strip():
                    logger.info("🔍 Attempting to parse JSON response")
                    # Clean up the response text - remove markdown code blocks if present
                    cleaned_text = response_text.strip()
                    if cleaned_text.startswith('```json'):
                        cleaned_text = cleaned_text[7:]  # Remove ```json
                    if cleaned_text.startswith('```'):
                        cleaned_text = cleaned_text[3:]   # Remove ```
                    if cleaned_text.endswith('```'):
                        cleaned_text = cleaned_text[:-3]  # Remove closing ```
                    cleaned_text = cleaned_text.strip()
                    
                    logger.debug(f"Cleaned text for parsing: {cleaned_text[:300]}...")
                    
                    # Try to parse as JSON first
                    parsed_response = json.loads(cleaned_text)
                    logger.info(f"✅ Successfully parsed JSON response with keys: {list(parsed_response.keys())}")
                else:
                    # Create fallback response if no text
                    logger.warning("⚠️ No response text received from Gemini API")
                    parsed_response = self._create_fallback_response("No response text from API", prompt)
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse JSON response: {e}")
                logger.error(f"Raw response text: {response_text}")
                # Fallback to structured response with actual error details
                parsed_response = self._create_fallback_response(f"JSON Parse Error: {e}. Raw text: {response_text[:500]}", prompt)
            
            # Handle tool calls if any
            if tool_calls_made:
                parsed_response["tool_calls_made"] = tool_calls_made
                parsed_response["tools_executed"] = len(tool_calls_made)
                
                # Enhance the response with tool execution details
                tool_results_summary = []
                for call in tool_calls_made:
                    if call["result"]["success"]:
                        for content_item in call["result"]["content"]:
                            if content_item["type"] == "text":
                                tool_results_summary.append(f"{call['tool']}: {content_item['text'][:200]}...")
                
                if tool_results_summary and "tool_results" in parsed_response:
                    parsed_response["tool_results"] = "\n".join(tool_results_summary)
            
            return parsed_response
            
        except Exception as e:
            logger.error(f"Error generating content with Gemini API: {e}")
            # Return structured error response
            return self._create_error_response(str(e), prompt)
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool through the MCP server (copied from gemini_mcp_client.py)"""
        try:
            if self.mcp_session is None:
                return {
                    "success": False,
                    "content": [{
                        "type": "text",
                        "text": f"No MCP session available to execute tool {tool_name}"
                    }]
                }
                
            logger.info(f"Executing tool: {tool_name} with args: {arguments}")
            
            response = await self.mcp_session.call_tool(tool_name, arguments)
            
            # Convert response to a serializable format
            result = {
                "success": not getattr(response, 'isError', False),
                "content": []
            }
            print(response)


            logger.info(f"Tool {tool_name} response received. Success:\n {result['success']}")
            
            if hasattr(response, 'content') and response.content:
                for content_item in response.content:
                    if hasattr(content_item, 'type'):
                        if content_item.type == 'text':
                            result["content"].append({
                                "type": "text",
                                "text": getattr(content_item, 'text', '')
                            })
                        elif content_item.type == 'image':
                            result["content"].append({
                                "type": "image", 
                                "data": getattr(content_item, 'data', ''),
                                "mimeType": getattr(content_item, 'mimeType', 'image/png')
                            })
            
            logger.info(f"Tool {tool_name} executed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {
                "success": False,
                "content": [{
                    "type": "text",
                    "text": f"Error executing tool {tool_name}: {str(e)}"
                }]
            }
    
    def _get_response_schema(self, prompt: str) -> types.Schema:
        """
        Get appropriate JSON schema based on prompt type
        """
        if "planner" in prompt.lower() or "plan" in prompt.lower():
            return types.Schema(
                type=types.Type.OBJECT,
                required=["next_action", "tool_to_use", "tool_parameters", "reasoning", "completion_status"],
                properties={
                    "next_action": types.Schema(type=types.Type.STRING),
                    "tool_to_use": types.Schema(type=types.Type.STRING),
                    "tool_parameters": types.Schema(type=types.Type.STRING),
                    "reasoning": types.Schema(type=types.Type.STRING),
                    "completion_status": types.Schema(type=types.Type.STRING),
                },
            )
        elif "executor" in prompt.lower() or "execute" in prompt.lower():
            return types.Schema(
                type=types.Type.OBJECT,
                required=["action_executed", "tool_used", "execution_status", "tool_results", "next_steps"],
                properties={
                    "action_executed": types.Schema(type=types.Type.STRING),
                    "tool_used": types.Schema(type=types.Type.STRING),
                    "execution_status": types.Schema(type=types.Type.STRING),
                    "tool_results": types.Schema(type=types.Type.STRING),
                    "next_steps": types.Schema(type=types.Type.STRING),
                },
            )
        elif "reviewer" in prompt.lower() or "review" in prompt.lower():
            return types.Schema(
                type=types.Type.OBJECT,
                required=["summary", "goal_status", "recommendations", "completion_assessment"],
                properties={
                    "summary": types.Schema(type=types.Type.STRING),
                    "goal_status": types.Schema(type=types.Type.STRING),
                    "recommendations": types.Schema(type=types.Type.STRING),
                    "completion_assessment": types.Schema(type=types.Type.STRING),
                },
            )
        else:
            # Generic schema for critic or other roles
            return types.Schema(
                type=types.Type.OBJECT,
                required=["critique", "suggestions", "risk_assessment", "quality_score"],
                properties={
                    "critique": types.Schema(type=types.Type.STRING),
                    "suggestions": types.Schema(type=types.Type.STRING),
                    "risk_assessment": types.Schema(type=types.Type.STRING),
                    "quality_score": types.Schema(type=types.Type.STRING),
                },
            )
    
    def _convert_tools_to_gemini_format(self) -> List[types.Tool]:
        """
        Convert MCP tools to Gemini function calling format
        """
        function_declarations = []
        
        logger.debug(f"Converting {len(self.tools)} tools to Gemini format")
        
        for tool in self.tools:
            try:
                logger.debug(f"Converting tool: {tool.name}")
                function_declaration = types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.inputSchema if hasattr(tool, 'inputSchema') else {}
                )
                function_declarations.append(function_declaration)
            except Exception as e:
                logger.error(f"Failed to convert tool {tool.name}: {e}")
                continue
        
        if function_declarations:
            gemini_tool = types.Tool(function_declarations=function_declarations)
            logger.info(f"Created Gemini tool with {len(function_declarations)} function declarations")
            return [gemini_tool]
        
        logger.warning("No tools available for Gemini")
        return []
    
    
    def _create_fallback_response(self, response_text: str, prompt: str) -> Dict[str, Any]:
        """
        Create a fallback structured response when JSON parsing fails
        """
        logger.warning(f"🔄 Creating fallback response for: {response_text[:100]}...")
        
        if "planner" in prompt.lower():
            # Check for goal achievement in the raw text
            completion_status = "goal_achieved" if "goal_achieved" in response_text.lower() else "error"
            # Use first available tool or none instead of hardcoded tool
            fallback_tool = self.tools[0].name if self.tools else "none"
            return {
                "next_action": f"FALLBACK: Failed to parse planner response. Raw: {response_text[:200]}",
                "tool_to_use": fallback_tool,
                "tool_parameters": "{}",
                "reasoning": f"Gemini API response parsing failed. Raw response: {response_text[:300]}",
                "completion_status": completion_status
            }
        elif "executor" in prompt.lower():
            return {
                "action_executed": f"FALLBACK: Failed to parse executor response. Raw: {response_text[:200]}",
                "tool_used": "none",
                "execution_status": "failed",
                "tool_results": f"Response parsing failed. Raw: {response_text[:300]}",
                "next_steps": "Check API response format"
            }
        elif "reviewer" in prompt.lower():
            # Check for goal achievement in the raw text
            goal_achieved = "goal_achieved" if "goal_achieved" in response_text.lower() else "error"
            return {
                "summary": f"FALLBACK: Failed to parse reviewer response. Raw: {response_text[:200]}",
                "goal_status": goal_achieved,
                "recommendations": f"Fix API response parsing issue. Raw: {response_text[:300]}",
                "completion_assessment": "Response parsing failed"
            }
        else:
            return {
                "critique": f"FALLBACK: Failed to parse critic response. Raw: {response_text[:200]}",
                "suggestions": f"Fix API response parsing. Raw: {response_text[:300]}",
                "risk_assessment": "High risk - API response format issue",
                "quality_score": "Failed - parsing error"
            }
    
    def _create_error_response(self, error_message: str, prompt: str) -> Dict[str, Any]:
        """
        Create a structured error response
        """
        base_error = {
            "error": error_message,
            "status": "failed",
            "timestamp": asyncio.get_event_loop().time()
        }
        
        if "planner" in prompt.lower():
            return {
                **base_error,
                "next_action": f"Planning failed: {error_message}",
                "tool_to_use": "none",
                "tool_parameters": "{}",
                "reasoning": "Error occurred during planning",
                "completion_status": "error"
            }
        elif "executor" in prompt.lower():
            return {
                **base_error,
                "action_executed": f"Execution failed: {error_message}",
                "tool_used": "none",
                "execution_status": "failed",
                "tool_results": "No results due to error",
                "next_steps": "Fix error and retry"
            }
        elif "reviewer" in prompt.lower():
            return {
                **base_error,
                "summary": f"Review failed: {error_message}",
                "goal_status": "failed",
                "recommendations": "Fix error and retry",
                "completion_assessment": "Review could not be completed"
            }
        else:
            return {
                **base_error,
                "critique": f"Critique failed: {error_message}",
                "suggestions": "Fix error and retry",
                "risk_assessment": "High risk due to error",
                "quality_score": "Failed"
            }

class GeminiMCPOrchestrator:
    """
    Main orchestrator that integrates Gemini MCP Client with the orchestration system
    """
    
    def __init__(self):
        self.mcp_session = None
        self.exit_stack = AsyncExitStack()
        self.genai_client = None
        self.available_tools = []
        self.llm = None
        self.orchestrator = None
        
    async def initialize(self):
        """Initialize the orchestrator system with real MCP connection"""
        logger.info("Initializing Gemini MCP Orchestrator...")
        
        # Initialize Gemini client
        if GEMINI_API_KEY:
            try:
                self.genai_client = genai.Client(api_key=GEMINI_API_KEY)
                logger.info(f"✅ Successfully initialized Gemini client with model: {GEMINI_MODEL}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Gemini client: {e}")
                raise
        else:
            logger.error("❌ No GEMINI_API_KEY provided")
            raise ValueError("GEMINI_API_KEY is required")
        
        # Connect to MCP server
        await self._connect_to_mcp_server()
        
        # Load available tools
        await self._load_mcp_tools()
        
        # Initialize LLM with real MCP session and tools
        self.llm = LLM(
            genai_client=self.genai_client,
            tools=self.available_tools,
            mcp_session=self.mcp_session
        )
        
        # Define async roles
        roles = {
            "planner": self._planner_role,
            "executor": self._executor_role,
            "critic": self._critic_role,
            "reviewer": self._reviewer_role,
        }
        
        # Define execution order with critic role included
        order = ["planner", "executor", "reviewer"]
        
        # Create orchestrator with stop sequence
        self.orchestrator = AsyncAdvancedOrchestrator(
            roles=roles,
            order=order,
            stop_sequence="goal_achieved"
        )
        
        logger.info("✅ Gemini MCP Orchestrator initialized")
        logger.info(f"📡 MCP Server: {'Connected' if self.mcp_session else 'Not connected'}")
        logger.info(f"� Transport: {MCP_TRANSPORT}")
        if MCP_SERVER_COMMAND:
            logger.info(f"📋 Stdio Command: {MCP_SERVER_COMMAND}")
        if MCP_SERVER_URL:
            logger.info(f"🌐 HTTP URL: {MCP_SERVER_URL}")
        logger.info(f"�🔧 Available tools: {len(self.available_tools)}")

    async def _connect_to_mcp_server(self):
        """Connect to the MCP server using either HTTP or stdio transport"""
        transport_type = MCP_TRANSPORT.lower()
        
        # Auto-detect transport type if set to "auto"
        if transport_type == "auto":
            if MCP_SERVER_COMMAND:
                transport_type = "stdio"
                logger.info("Auto-detected stdio transport (MCP_SERVER_COMMAND provided)")
            elif MCP_SERVER_URL:
                transport_type = "http"
                logger.info("Auto-detected HTTP transport (MCP_SERVER_URL provided)")
            else:
                logger.error("No MCP server configuration found. Set MCP_SERVER_URL or MCP_SERVER_COMMAND")
                self.mcp_session = None
                return
        
        # Try stdio transport first
        if transport_type == "stdio" and MCP_SERVER_COMMAND:
            try:
                await self._connect_stdio_transport()
                return
            except Exception as e:
                logger.error(f"Failed to connect via stdio transport: {e}")
                if MCP_TRANSPORT != "auto":
                    self.mcp_session = None
                    return
        
        # Try HTTP transport
        if transport_type == "http" and MCP_SERVER_URL:
            try:
                await self._connect_http_transport()
                return
            except Exception as e:
                logger.error(f"Failed to connect via HTTP transport: {e}")
                
        # If we get here, all connection attempts failed
        logger.warning("No MCP server connection established")
        self.mcp_session = None
        
    async def _connect_stdio_transport(self):
        """Connect using stdio transport by launching a subprocess"""
        logger.info(f"Connecting to MCP stdio server with command: {MCP_SERVER_COMMAND}")
        
        # Parse the command (handle both string and list formats)
        if isinstance(MCP_SERVER_COMMAND, str):
            # Split command string into list
            cmd_parts = shlex.split(MCP_SERVER_COMMAND)
        else:
            cmd_parts = MCP_SERVER_COMMAND
            
        # Extract command and arguments
        if cmd_parts:
            command = cmd_parts[0]
            args = cmd_parts[1:] if len(cmd_parts) > 1 else []
        else:
            raise ValueError("Empty MCP_SERVER_COMMAND")
            
        # Create StdioServerParameters
        server_params = StdioServerParameters(
            command=command,
            args=args
        )
        
        # Start the MCP server process
        logger.debug(f"Starting MCP server with params: command={command}, args={args}")
        server_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        
        # stdio_client returns (read, write)
        read, write = server_transport
        logger.debug("Got stdio transport streams, creating ClientSession")
        self.mcp_session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        
        logger.debug("Initializing MCP session...")
        await self.mcp_session.initialize()
        logger.info(f"Successfully connected to MCP stdio server")
        
    async def _connect_http_transport(self):
        """Connect using HTTP transport"""
        logger.info(f"Connecting to MCP HTTP server at: {MCP_SERVER_URL}")
        transport = await self.exit_stack.enter_async_context(
            streamablehttp_client(url=MCP_SERVER_URL)
        )

        # streamablehttp_client returns (read, write, httpx_client)
        read, write, _ = transport
        self.mcp_session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        await self.mcp_session.initialize()
        logger.info(f"Successfully connected to MCP HTTP server at: {MCP_SERVER_URL}")
        
    async def _load_mcp_tools(self):
        """Load available tools from MCP server"""
        try:
            if self.mcp_session is None:
                logger.info("No MCP session available, skipping tool loading")
                self.available_tools = []
                return
                
            # Get tools from the session
            response = await self.mcp_session.list_tools()
            self.available_tools = response.tools if response.tools else []
            
            logger.info(f"Loaded {len(self.available_tools)} tools from MCP server")
            
            # Log available tools
            for tool in self.available_tools:
                logger.info(f"Tool: {tool.name} - {tool.description}")
                logger.debug(f"Tool schema: {tool.inputSchema}")
                
        except Exception as e:
            logger.error(f"Failed to load tools: {e}")
            # Don't raise here, continue with empty tools list
            self.available_tools = []

    async def _planner_role(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Planner role - creates execution plans using Gemini API"""
        return await self.llm.generate_plan(context)

    async def _executor_role(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Executor role - performs actions using tools"""
        return await self.llm.generate_execution(context)

    async def _critic_role(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Critic role - analyzes and critiques the execution using Gemini API"""
        return await self.llm.generate_critique(context)

    async def _reviewer_role(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Reviewer role - synthesizes results and determines completion using Gemini API"""
        return await self.llm.generate_review(context)

    async def run_goal(self, goal: str) -> Dict[str, Any]:
        """
        Run the orchestrator to achieve a goal using run_until_stop
        """
        try:
            logger.info(f"🎯 Starting goal execution: {goal}")
            
            # Run orchestrator until stop sequence is found
            result = await self.orchestrator.run_until_stop(goal)
            
            logger.info(f"🏁 Goal execution completed after {result.get('iterations', 'unknown')} iterations")
            
            return result
            
        except Exception as e:
            logger.error(f"Error running goal: {e}")
            return {
                "error": str(e),
                "status": "failed",
                "final": {"summary": f"Goal execution failed: {str(e)}"}
            }

    async def run_interactive_session(self):
        """Run an interactive session for goal-based execution"""
        print("🚀 Web Browsing Agent with Gemini MCP Orchestrator initialized!")
        print("🎯 Enter goals to execute using the enhanced web browsing orchestration system.")
        print("🔄 Workflow: Planner (Single Action) → Executor (Tool Call) → Critic → Reviewer")
        print(f"📡 MCP Server: {'Connected' if self.mcp_session else 'Not connected'}")
        print(f"� Transport: {MCP_TRANSPORT}")
        if self.mcp_session and MCP_SERVER_COMMAND:
            print(f"📋 Using stdio command: {MCP_SERVER_COMMAND}")
        elif self.mcp_session and MCP_SERVER_URL:
            print(f"🌐 Using HTTP URL: {MCP_SERVER_URL}")
        print(f"�🔧 Available tools: {len(self.available_tools)}")
        
        if self.available_tools:
            print("\nAvailable MCP tools for web browsing:")
            for i, tool in enumerate(self.available_tools):
                print(f"  {i+1}. {tool.name}: {tool.description}")
                if i >= 30:  # Show first 10 tools
                    remaining = len(self.available_tools) - 10
                    if remaining > 0:
                        print(f"  ... and {remaining} more tools")
                    break
        else:
            print("⚠️  No MCP tools available - running in planning-only mode")
            
        print("\nType 'quit' to exit.\n")
        print("Examples for Web Browsing Agent:")
        print("- Navigate to Google and search for 'AI developments'")
        print("- Go to Python.org and find the latest version")
        print("- Visit GitHub and browse trending repositories")
        print("- Take a screenshot of a specific webpage")
        print("- Extract text content from a news article")
        print("-" * 60)
        
        while True:
            try:
                user_input = input("\n🎯 Enter your goal: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                print(f"\n🔄 Executing goal: {user_input}")
                result = await self.run_goal(user_input)
                
                print("\n" + "="*60)
                print("📊 FINAL RESULT:")
                print("="*60)
                final_result = result.get("final", {})
                print(f"Summary: {final_result.get('summary', 'No summary available')}")
                print(f"Status: {final_result.get('goal_status', 'Unknown')}")
                print(f"Iterations: {result.get('iterations', 'Unknown')}")
                
                # Show workflow details
                context = result.get("context", {})
                if context:
                    print(f"\n📋 Workflow Details:")
                    
                    # Planner details
                    planner = context.get("planner", {})
                    if planner:
                        print(f"  Next Action: {planner.get('next_action', 'N/A')}")
                        print(f"  Tool to Use: {planner.get('tool_to_use', 'N/A')}")
                        print(f"  Reasoning: {planner.get('reasoning', 'N/A')}")
                    
                    # Executor details
                    executor = context.get("executor", {})
                    if executor:
                        print(f"  Execution Status: {executor.get('execution_status', 'N/A')}")
                        print(f"  Tool Used: {executor.get('tool_used', 'N/A')}")
                        if executor.get('tool_results'):
                            tool_results = executor['tool_results']
                            if len(tool_results) > 150:
                                tool_results = tool_results[:150] + "..."
                            print(f"  Tool Results: {tool_results}")
                    
                    # Critic details
                    critic = context.get("critic", {})
                    if critic:
                        print(f"  Quality Score: {critic.get('quality_score', 'N/A')}")
                        print(f"  Risk Assessment: {critic.get('risk_assessment', 'N/A')}")
                        if critic.get('suggestions'):
                            suggestions = critic['suggestions']
                            if len(suggestions) > 100:
                                suggestions = suggestions[:100] + "..."
                            print(f"  Suggestions: {suggestions}")
                
                print("="*60)
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

    async def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'exit_stack'):
            try:
                await self.exit_stack.aclose()
                logger.info("Disconnected from MCP server")
            except Exception as e:
                logger.error(f"Error disconnecting from MCP server: {e}")


async def main():
    """Main entry point"""
    orchestrator = GeminiMCPOrchestrator()
    
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
