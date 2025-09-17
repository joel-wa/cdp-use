#!/usr/bin/env python3
"""
Web UI for Gemini MCP Orchestrator

Provides a real-time web interface to visualize orchestrator execution stages.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import sys
from datetime import datetime

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from enhanced_conversational_orchestrator import EnhancedConversationalOrchestrator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="LLM Orchestrator Web UI")

# Store active WebSocket connections
connections: List[WebSocket] = []

class OrchestratorWebUI:
    def __init__(self):
        self.orchestrator = None
        self.current_execution = None
        
    async def initialize(self):
        """Initialize the orchestrator"""
        self.orchestrator = EnhancedConversationalOrchestrator()
        await self.orchestrator.initialize()
        logger.info("✅ Enhanced Orchestrator Web UI initialized")
    
    async def execute_goal_with_ui(self, goal: str, websocket: WebSocket):
        """Execute goal with real-time UI updates"""
        try:
            logger.info(f"🎯 Starting goal execution in UI: {goal}")
            
            await self.send_message(websocket, {
                "type": "status",
                "data": {
                    "status": "starting",
                    "message": f"🎯 Starting goal execution: {goal}",
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            # Create enhanced orchestrator execution with UI updates
            result = await self.run_enhanced_goal_with_updates(goal, websocket)
            
            # Take final screenshot at goal completion
            await self.take_final_screenshot(websocket)
            
            await self.send_message(websocket, {
                "type": "status",
                "data": {
                    "status": "completed",
                    "message": f"🏁 Goal execution completed",
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing goal: {e}")
            await self.send_message(websocket, {
                "type": "error",
                "data": {
                    "message": f"❌ Error: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }
            })
    
    async def run_enhanced_goal_with_updates(self, goal: str, websocket: WebSocket):
        """Run enhanced orchestrator with real-time updates"""
        try:
            logger.info(f"🔄 Starting enhanced goal execution for: {goal}")
            
            # Send initial processing message
            await self.send_message(websocket, {
                "type": "assistant_thinking",
                "data": {
                    "message": "🤖 Processing your request...",
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            # Hook into the orchestrator to monitor tool calls
            original_tool_orchestrator = self.orchestrator.tool_orchestrator
            if original_tool_orchestrator:
                original_execute = original_tool_orchestrator._execute_single_tool_with_recovery
                
                async def monitored_execute(tool_call):
                    # Send tool start message
                    tool_name = tool_call["function"]["name"]
                    await self.send_message(websocket, {
                        "type": "tool_start",
                        "data": {
                            "tool_name": tool_name,
                            "arguments": tool_call["function"]["arguments"],
                            "message": f"🔧 Executing {tool_name}...",
                            "timestamp": datetime.now().isoformat()
                        }
                    })
                    
                    # Execute the tool
                    result = await original_execute(tool_call)
                    
                    # Send tool completion message
                    await self.send_message(websocket, {
                        "type": "tool_complete",
                        "data": {
                            "tool_name": tool_name,
                            "result": result.result,
                            "success": result.status.value == "completed",
                            "error": result.error,
                            "execution_time": result.execution_time,
                            "message": f"✅ {tool_name} {'completed' if result.error is None else 'failed'}",
                            "timestamp": datetime.now().isoformat()
                        }
                    })
                    
                    # Handle screenshot results specially
                    await self.handle_screenshot_result(tool_name, result, websocket)
                    
                    return result
                
                # Temporarily replace the execute method
                original_tool_orchestrator._execute_single_tool_with_recovery = monitored_execute
            
            # Process the user input with the enhanced orchestrator
            result = await self.orchestrator.process_user_input(goal)
            
            # Send assistant response
            await self.send_message(websocket, {
                "type": "assistant_response",
                "data": {
                    "content": result,
                    "message": "🎯 Assistant response generated",
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            # Restore original execute method
            if original_tool_orchestrator:
                original_tool_orchestrator._execute_single_tool_with_recovery = original_execute
            
            return {"result": result, "status": "completed"}
            
        except Exception as e:
            logger.error(f"Error in enhanced goal execution: {e}")
            await self.send_message(websocket, {
                "type": "error",
                "data": {
                    "message": f"❌ Error during execution: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }
            })
            raise
    
    async def handle_screenshot_result(self, tool_name: str, result, websocket: WebSocket):
        """Handle screenshot tool results specially to display images in UI"""
        try:
            if tool_name == "take_screenshot" and result.result and result.error is None:
                # Extract base64 image data from the result
                screenshot_data = None
                if isinstance(result.result, dict):
                    screenshot_data = result.result.get("image_data") or result.result.get("base64_image")
                elif isinstance(result.result, str):
                    # Sometimes the result might be just the base64 string
                    screenshot_data = result.result
                
                if screenshot_data:
                    await self.send_message(websocket, {
                        "type": "screenshot",
                        "data": {
                            "image_data": screenshot_data,
                            "tool_name": tool_name,
                            "message": "📸 Screenshot captured",
                            "timestamp": datetime.now().isoformat()
                        }
                    })
                    logger.info(f"📸 Screenshot data sent to UI")
                else:
                    logger.warning(f"⚠️ Screenshot tool completed but no image data found")
            
        except Exception as e:
            logger.error(f"Error handling screenshot result: {e}")
    
    async def take_final_screenshot(self, websocket: WebSocket):
        """Take a final screenshot at the end of goal execution"""
        try:
            if self.orchestrator and self.orchestrator.mcp_session:
                logger.info("📸 Taking final screenshot...")
                
                await self.send_message(websocket, {
                    "type": "final_screenshot_start",
                    "data": {
                        "message": "📸 Taking final screenshot...",
                        "timestamp": datetime.now().isoformat()
                    }
                })
                
                # Create a tool call for taking screenshot
                screenshot_tool_call = {
                    "function": {
                        "name": "take_screenshot",
                        "arguments": {}
                    }
                }
                
                # Execute screenshot using the tool orchestrator
                if self.orchestrator.tool_orchestrator:
                    result = await self.orchestrator.tool_orchestrator._execute_single_tool_with_recovery(screenshot_tool_call)
                    await self.handle_screenshot_result("take_screenshot", result, websocket)
                    
                    await self.send_message(websocket, {
                        "type": "final_screenshot_complete",
                        "data": {
                            "message": "📸 Final screenshot completed",
                            "timestamp": datetime.now().isoformat()
                        }
                    })
                    
        except Exception as e:
            logger.error(f"Error taking final screenshot: {e}")
            await self.send_message(websocket, {
                "type": "error",
                "data": {
                    "message": f"❌ Error taking final screenshot: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }
            })
    
    async def send_message(self, websocket: WebSocket, message: Dict[str, Any]):
        """Send message to WebSocket with proper error handling"""
        try:
            message_json = json.dumps(message)
            logger.info(f"📤 Sending WebSocket message: {message['type']} - {message.get('data', {}).get('message', '')}")
            await websocket.send_text(message_json)
            # Add small delay to ensure message is processed
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"❌ Error sending WebSocket message: {e}")
            raise

# Global orchestrator instance
orchestrator_ui = OrchestratorWebUI()

@app.on_event("startup")
async def startup_event():
    """Initialize the orchestrator on startup"""
    await orchestrator_ui.initialize()

@app.get("/", response_class=HTMLResponse)
async def get_ui():
    """Serve the main UI"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>LLM Orchestrator - Live</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                background: white;
                color: black;
                height: 100vh;
                overflow: hidden;
            }

            .container {
                display: flex;
                flex-direction: column;
                height: 100vh;
            }

            .header {
                padding: 20px 30px;
                border-bottom: 1px solid #e0e0e0;
                background: white;
            }

            .header h1 {
                font-size: 24px;
                font-weight: 300;
                margin-bottom: 8px;
            }

            .status {
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 14px;
                color: #666;
            }

            .status-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: #ccc;
            }

            .status-dot.active {
                background: black;
                animation: pulse 2s infinite;
            }

            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }

            .chat-container {
                flex: 1;
                overflow-y: auto;
                padding: 20px 30px;
                scroll-behavior: smooth;
            }

            .message {
                margin-bottom: 20px;
                opacity: 0;
                transform: translateY(20px);
                animation: slideIn 0.5s ease forwards;
            }

            @keyframes slideIn {
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            .message-header {
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 12px;
            }

            .role-badge {
                padding: 6px 12px;
                border: 1px solid black;
                font-size: 12px;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            .role-badge.planner {
                background: black;
                color: white;
            }

            .role-badge.executor {
                background: white;
                color: black;
            }

            .role-badge.critic {
                background: white;
                color: black;
                border-style: dotted;
            }

            .role-badge.reviewer {
                background: white;
                color: black;
                border-style: dashed;
            }

            .role-badge.system {
                background: #f5f5f5;
                color: #666;
                border-color: #ccc;
            }

            .cycle-count {
                font-size: 11px;
                color: #666;
                background: #f5f5f5;
                padding: 4px 8px;
                border-radius: 12px;
            }

            .message-content {
                padding: 20px;
                border: 1px solid #e0e0e0;
                font-size: 15px;
                line-height: 1.6;
                margin-left: 0;
                white-space: pre-wrap;
            }

            .message.planner .message-content {
                border-left: 3px solid black;
            }

            .message.executor .message-content {
                border-left: 3px solid #666;
            }

            .message.critic .message-content {
                border-left: 3px solid #999;
            }

            .message.reviewer .message-content {
                border-left: 3px solid #333;
            }

            .message.system .message-content {
                border-left: 3px solid #ccc;
                background: #f9f9f9;
            }

            .controls {
                padding: 20px 30px;
                border-top: 1px solid #e0e0e0;
                background: white;
            }

            .input-container {
                display: flex;
                gap: 15px;
                align-items: center;
            }

            .task-input {
                flex: 1;
                padding: 12px 16px;
                border: 1px solid #e0e0e0;
                font-size: 15px;
                outline: none;
                transition: border-color 0.2s;
            }

            .task-input:focus {
                border-color: black;
            }

            .btn {
                padding: 12px 24px;
                background: black;
                color: white;
                border: none;
                font-size: 14px;
                cursor: pointer;
                transition: all 0.2s;
                font-weight: 500;
            }

            .btn:hover {
                background: #333;
            }

            .btn:disabled {
                background: #ccc;
                cursor: not-allowed;
            }

            .btn.secondary {
                background: white;
                color: black;
                border: 1px solid black;
            }

            .btn.secondary:hover {
                background: #f5f5f5;
            }

            .goal-achieved {
                text-align: center;
                padding: 30px;
                margin: 20px 0;
                border: 2px solid black;
                font-size: 18px;
                font-weight: 500;
                background: black;
                color: white;
            }

            .timestamp {
                font-size: 11px;
                color: #999;
                margin-left: auto;
            }

            .json-content {
                background: #f5f5f5;
                padding: 10px;
                border-radius: 4px;
                font-family: monospace;
                font-size: 13px;
                margin-top: 10px;
                max-height: 200px;
                overflow-y: auto;
            }

            /* Screenshot-specific styles */
            .message.screenshot .message-content {
                border-left: 3px solid #ff6b35;
                padding: 15px;
            }

            .message.assistant .message-content {
                border-left: 3px solid #007acc;
            }

            .message.tool .message-content {
                border-left: 3px solid #28a745;
                background: #f8f9fa;
            }

            .role-badge.screenshot {
                background: #ff6b35;
                color: white;
            }

            .role-badge.assistant {
                background: #007acc;
                color: white;
            }

            .role-badge.tool {
                background: #28a745;
                color: white;
            }

            .screenshot-image {
                max-width: 100%;
                height: auto;
                border: 1px solid #ddd;
                border-radius: 4px;
                margin-top: 10px;
                cursor: pointer;
                transition: transform 0.2s ease;
            }

            .screenshot-image:hover {
                transform: scale(1.02);
            }

            .screenshot-message {
                margin-bottom: 10px;
                font-weight: 500;
            }

            /* Modal for full-size image view */
            .screenshot-modal {
                display: none;
                position: fixed;
                z-index: 1000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0,0,0,0.8);
                cursor: pointer;
            }

            .screenshot-modal img {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                max-width: 90%;
                max-height: 90%;
                border-radius: 4px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>LLM Orchestrator - Live</h1>
                <div class="status">
                    <div class="status-dot" id="statusDot"></div>
                    <span id="statusText">Ready</span>
                    <span>•</span>
                    <span id="cycleCount">Cycle 0</span>
                </div>
            </div>

            <div class="chat-container" id="chatContainer">
                <div class="message system">
                    <div class="message-content">
                        🚀 Welcome to the Enhanced LLM Orchestrator! 
                        
Enter a goal below to watch the AI assistant intelligently plan and execute tools to achieve your objective in real-time.

Features:
• 🤖 Enhanced conversational AI with tool execution
• 🔧 Real-time tool execution monitoring
• 📸 Automatic screenshot capture and display
• ⚡ Smart error recovery and retry logic
• 🎯 Goal completion with final screenshot
                    </div>
                </div>
            </div>

            <div class="controls">
                <div class="input-container">
                    <input 
                        type="text" 
                        class="task-input" 
                        id="taskInput" 
                        placeholder="Enter your goal (e.g., 'Navigate to LinkedIn and extract job listings')"
                        value=""
                    >
                    <button class="btn" id="startBtn">Start</button>
                    <button class="btn secondary" id="stopBtn" disabled>Stop</button>
                    <button class="btn secondary" id="resetBtn">Reset</button>
                </div>
            </div>
        </div>

        <script>
            class LiveOrchestratorUI {
                constructor() {
                    this.chatContainer = document.getElementById('chatContainer');
                    this.taskInput = document.getElementById('taskInput');
                    this.startBtn = document.getElementById('startBtn');
                    this.stopBtn = document.getElementById('stopBtn');
                    this.resetBtn = document.getElementById('resetBtn');
                    this.statusDot = document.getElementById('statusDot');
                    this.statusText = document.getElementById('statusText');
                    this.cycleCount = document.getElementById('cycleCount');
                    
                    this.websocket = null;
                    this.isRunning = false;
                    this.currentCycle = 0;
                    
                    this.initializeEventListeners();
                    this.connectWebSocket();
                }

                initializeEventListeners() {
                    this.startBtn.addEventListener('click', () => this.startOrchestration());
                    this.stopBtn.addEventListener('click', () => this.stopOrchestration());
                    this.resetBtn.addEventListener('click', () => this.resetOrchestration());
                    this.taskInput.addEventListener('keypress', (e) => {
                        if (e.key === 'Enter' && !this.isRunning) {
                            this.startOrchestration();
                        }
                    });
                }

                connectWebSocket() {
                    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                    const wsUrl = `${protocol}//${window.location.host}/ws`;
                    
                    this.websocket = new WebSocket(wsUrl);
                    
                    this.websocket.onopen = () => {
                        console.log('WebSocket connected');
                        this.statusText.textContent = 'Connected';
                    };
                    
                    this.websocket.onmessage = (event) => {
                        const message = JSON.parse(event.data);
                        this.handleWebSocketMessage(message);
                    };
                    
                    this.websocket.onclose = () => {
                        console.log('WebSocket disconnected');
                        this.statusText.textContent = 'Disconnected';
                        // Attempt to reconnect after 3 seconds
                        setTimeout(() => this.connectWebSocket(), 3000);
                    };
                    
                    this.websocket.onerror = (error) => {
                        console.error('WebSocket error:', error);
                        this.statusText.textContent = 'Error';
                    };
                }

                handleWebSocketMessage(message) {
                    const { type, data } = message;
                    
                    switch (type) {
                        case 'status':
                            this.handleStatusMessage(data);
                            break;
                        case 'assistant_thinking':
                            this.handleAssistantThinking(data);
                            break;
                        case 'tool_start':
                            this.handleToolStart(data);
                            break;
                        case 'tool_complete':
                            this.handleToolComplete(data);
                            break;
                        case 'assistant_response':
                            this.handleAssistantResponse(data);
                            break;
                        case 'screenshot':
                            this.handleScreenshot(data);
                            break;
                        case 'final_screenshot_start':
                        case 'final_screenshot_complete':
                            this.handleFinalScreenshot(data);
                            break;
                        case 'error':
                            this.handleError(data);
                            break;
                        // Legacy handlers for backward compatibility
                        case 'cycle_start':
                            this.handleCycleStart(data);
                            break;
                        case 'role_start':
                            this.handleRoleStart(data);
                            break;
                        case 'role_complete':
                            this.handleRoleComplete(data);
                            break;
                        case 'role_error':
                            this.handleRoleError(data);
                            break;
                        case 'cycle_complete':
                            this.handleCycleComplete(data);
                            break;
                        case 'goal_achieved':
                            this.handleGoalAchieved(data);
                            break;
                        case 'max_iterations':
                            this.handleMaxIterations(data);
                            break;
                    }
                }

                handleStatusMessage(data) {
                    if (data.status === 'starting') {
                        this.statusDot.classList.add('active');
                        this.statusText.textContent = 'Running';
                    } else if (data.status === 'completed') {
                        this.statusDot.classList.remove('active');
                        this.statusText.textContent = 'Completed';
                        this.stopOrchestration();
                    }
                    
                    this.addSystemMessage(data.message, data.timestamp);
                }

                handleCycleStart(data) {
                    this.currentCycle = data.cycle;
                    this.cycleCount.textContent = `Cycle ${data.cycle}`;
                    this.addSystemMessage(data.message, data.timestamp);
                }

                handleRoleStart(data) {
                    this.addSystemMessage(`  ${data.message}`, data.timestamp);
                }

                handleRoleComplete(data) {
                    this.addRoleMessage(data.role, data.output, data.cycle, data.timestamp);
                }

                // New Enhanced Orchestrator Handlers
                handleAssistantThinking(data) {
                    this.addSystemMessage(data.message, data.timestamp);
                }

                handleToolStart(data) {
                    this.addMessage('tool', `🔧 ${data.message}`, null, data.timestamp);
                }

                handleToolComplete(data) {
                    const status = data.success ? '✅' : '❌';
                    let message = `${status} ${data.tool_name} ${data.success ? 'completed' : 'failed'}`;
                    if (data.execution_time) {
                        message += ` (${data.execution_time.toFixed(2)}s)`;
                    }
                    if (data.error) {
                        message += `: ${data.error}`;
                    }
                    this.addMessage('tool', message, null, data.timestamp);
                }

                handleAssistantResponse(data) {
                    this.addMessage('assistant', data.content, null, data.timestamp);
                }

                handleScreenshot(data) {
                    if (data.image_data) {
                        this.addScreenshotMessage(data.image_data, data.message, data.timestamp);
                    } else {
                        this.addSystemMessage(`📸 Screenshot tool executed but no image data received`, data.timestamp);
                    }
                }

                handleFinalScreenshot(data) {
                    this.addSystemMessage(data.message, data.timestamp);
                }

                // Legacy handlers for backward compatibility
                handleRoleError(data) {
                    this.addSystemMessage(`❌ ${data.message}`, data.timestamp);
                }

                handleCycleComplete(data) {
                    this.addSystemMessage(`  ${data.message}`, data.timestamp);
                }

                handleGoalAchieved(data) {
                    this.addGoalAchievedMessage();
                    this.stopOrchestration();
                }

                handleError(data) {
                    this.addSystemMessage(data.message, data.timestamp);
                    this.stopOrchestration();
                }

                handleMaxIterations(data) {
                    this.addSystemMessage(data.message, data.timestamp);
                    this.stopOrchestration();
                }

                startOrchestration() {
                    if (this.isRunning || !this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
                        return;
                    }
                    
                    const task = this.taskInput.value.trim();
                    if (!task) return;

                    this.isRunning = true;
                    this.startBtn.disabled = true;
                    this.stopBtn.disabled = false;
                    this.taskInput.disabled = true;
                    
                    // Send goal to backend
                    this.websocket.send(JSON.stringify({
                        type: 'execute_goal',
                        goal: task
                    }));
                }

                stopOrchestration() {
                    this.isRunning = false;
                    this.startBtn.disabled = false;
                    this.stopBtn.disabled = true;
                    this.taskInput.disabled = false;
                    
                    this.statusDot.classList.remove('active');
                    this.statusText.textContent = 'Ready';
                }

                resetOrchestration() {
                    this.stopOrchestration();
                    this.currentCycle = 0;
                    this.cycleCount.textContent = 'Cycle 0';
                    
                    // Clear chat except welcome message
                    const messages = this.chatContainer.querySelectorAll('.message');
                    for (let i = 1; i < messages.length; i++) {
                        messages[i].remove();
                    }
                }

                addSystemMessage(content, timestamp) {
                    this.addMessage('system', content, null, timestamp);
                }

                addRoleMessage(role, output, cycle, timestamp) {
                    let content = '';
                    
                    if (typeof output === 'object') {
                        // Format object output nicely
                        content = this.formatObjectOutput(output);
                    } else {
                        content = output;
                    }
                    
                    this.addMessage(role, content, cycle, timestamp);
                }

                formatObjectOutput(output) {
                    let formatted = '';
                    
                    // Extract key fields based on role
                    if (output.plan) {
                        formatted += `📋 Plan: ${output.plan}`;
                        if (output.priority) formatted += `\n🔥 Priority: ${output.priority}`;
                        if (output.estimated_steps) formatted += `\n📊 Steps: ${output.estimated_steps}`;
                    } else if (output.actions_taken) {
                        formatted += `⚡ Actions: ${output.actions_taken}`;
                        if (output.status) formatted += `\n📈 Status: ${output.status}`;
                        if (output.tool_results) formatted += `\n🔧 Results: ${output.tool_results}`;
                    } else if (output.critique) {
                        formatted += `🔍 Critique: ${output.critique}`;
                        if (output.suggestions) formatted += `\n💡 Suggestions: ${output.suggestions}`;
                        if (output.quality_score) formatted += `\n⭐ Quality: ${output.quality_score}`;
                    } else if (output.summary) {
                        formatted += `📝 Summary: ${output.summary}`;
                        if (output.goal_status) formatted += `\n🎯 Status: ${output.goal_status}`;
                        if (output.recommendations) formatted += `\n📋 Next: ${output.recommendations}`;
                    }
                    
                    return formatted || JSON.stringify(output, null, 2);
                }

                addMessage(role, content, cycle, timestamp) {
                    const messageDiv = document.createElement('div');
                    messageDiv.className = `message ${role}`;
                    
                    const timestampStr = timestamp ? new Date(timestamp).toLocaleTimeString() : '';
                    
                    let cycleInfo = '';
                    if (cycle) {
                        cycleInfo = `<div class="cycle-count">Cycle ${cycle}</div>`;
                    }
                    
                    messageDiv.innerHTML = `
                        <div class="message-header">
                            <div class="role-badge ${role}">${role}</div>
                            ${cycleInfo}
                            <div class="timestamp">${timestampStr}</div>
                        </div>
                        <div class="message-content">${content}</div>
                    `;

                    this.chatContainer.appendChild(messageDiv);
                    this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
                }

                addScreenshotMessage(imageData, message, timestamp) {
                    const messageDiv = document.createElement('div');
                    messageDiv.className = 'message screenshot';
                    
                    const timestampStr = timestamp ? new Date(timestamp).toLocaleTimeString() : '';
                    
                    // Create image element
                    const imageUrl = `data:image/png;base64,${imageData}`;
                    const imageId = `screenshot-${Date.now()}`;
                    
                    messageDiv.innerHTML = `
                        <div class="message-header">
                            <div class="role-badge screenshot">📸 screenshot</div>
                            <div class="timestamp">${timestampStr}</div>
                        </div>
                        <div class="message-content">
                            <div class="screenshot-message">${message}</div>
                            <img src="${imageUrl}" alt="Screenshot" class="screenshot-image" id="${imageId}" />
                        </div>
                    `;

                    this.chatContainer.appendChild(messageDiv);
                    
                    // Add click handler for full-size view
                    const img = document.getElementById(imageId);
                    img.addEventListener('click', () => this.showFullSizeImage(imageUrl));
                    
                    this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
                }

                showFullSizeImage(imageUrl) {
                    // Create modal if it doesn't exist
                    let modal = document.getElementById('screenshot-modal');
                    if (!modal) {
                        modal = document.createElement('div');
                        modal.id = 'screenshot-modal';
                        modal.className = 'screenshot-modal';
                        modal.innerHTML = '<img src="" alt="Full-size screenshot" />';
                        document.body.appendChild(modal);
                        
                        modal.addEventListener('click', () => {
                            modal.style.display = 'none';
                        });
                    }
                    
                    // Show the modal with the image
                    modal.querySelector('img').src = imageUrl;
                    modal.style.display = 'block';
                }

                addGoalAchievedMessage() {
                    const goalDiv = document.createElement('div');
                    goalDiv.className = 'goal-achieved';
                    goalDiv.textContent = '🎯 GOAL ACHIEVED';
                    this.chatContainer.appendChild(goalDiv);
                    this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
                }
            }

            // Initialize the UI when the page loads
            document.addEventListener('DOMContentLoaded', () => {
                new LiveOrchestratorUI();
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication"""
    await websocket.accept()
    connections.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "execute_goal":
                goal = message["goal"]
                await orchestrator_ui.execute_goal_with_ui(goal, websocket)
                
    except WebSocketDisconnect:
        connections.remove(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in connections:
            connections.remove(websocket)

if __name__ == "__main__":
    # Run the web server
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8000,
        log_level="info"
    )
