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
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from LLMOrchestration.gemini_mcp_orchestrator import GeminiMCPOrchestrator

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
        self.orchestrator = GeminiMCPOrchestrator()
        await self.orchestrator.initialize()
        logger.info("✅ Orchestrator Web UI initialized")
    
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
            
            # Create a custom orchestrator that sends updates
            result = await self.run_goal_with_updates(goal, websocket)
            
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
    
    async def run_goal_with_updates(self, goal: str, websocket: WebSocket):
        """Run orchestrator with real-time updates"""
        try:
            logger.info(f"🔄 Starting run_goal_with_updates for: {goal}")
            
            # Initialize context
            context = {"input": goal}
            iteration = 0
            max_iterations = 10
            
            while iteration < max_iterations:
                iteration += 1
                logger.info(f"🔄 Starting iteration {iteration}")
                
                await self.send_message(websocket, {
                    "type": "cycle_start",
                    "data": {
                        "cycle": iteration,
                        "message": f"🔄 Orchestrator iteration {iteration}",
                        "timestamp": datetime.now().isoformat()
                    }
                })
                
                # Execute each role with updates
                for role in ["planner", "executor",
                            #   "critic", 
                              "reviewer"]:
                    logger.info(f"▶️ Executing role: {role}")
                    
                    await self.send_message(websocket, {
                        "type": "role_start",
                        "data": {
                            "role": role,
                            "cycle": iteration,
                            "message": f"▶️ Executing role: {role}",
                            "timestamp": datetime.now().isoformat()
                        }
                    })
                    
                    # Execute the role
                    try:
                        if role == "planner":
                            output = await self.orchestrator._planner_role(context)
                        elif role == "executor":
                            output = await self.orchestrator._executor_role(context)
                        elif role == "critic":
                            output = await self.orchestrator._critic_role(context)
                        elif role == "reviewer":
                            output = await self.orchestrator._reviewer_role(context)
                        
                        logger.info(f"✅ {role} output: {output}")
                        context[role] = output
                        
                        await self.send_message(websocket, {
                            "type": "role_complete",
                            "data": {
                                "role": role,
                                "cycle": iteration,
                                "output": output,
                                "message": f"✅ {role.title()} completed",
                                "timestamp": datetime.now().isoformat()
                            }
                        })
                        
                        # Check for stop sequence immediately after each role
                        if self.orchestrator.orchestrator._contains_stop_sequence(output):
                            logger.info(f"🎯 GOAL ACHIEVED! Stop sequence found in {role}")
                            await self.send_message(websocket, {
                                "type": "goal_achieved",
                                "data": {
                                    "role": role,
                                    "cycle": iteration,
                                    "message": f"🎯 GOAL ACHIEVED! Stop sequence found in {role} output",
                                    "timestamp": datetime.now().isoformat()
                                }
                            })
                            context["final"] = context["reviewer"] if "reviewer" in context else output
                            context["iterations"] = iteration
                            return context
                            
                    except Exception as role_error:
                        logger.error(f"❌ Error in {role}: {role_error}")
                        await self.send_message(websocket, {
                            "type": "role_error",
                            "data": {
                                "role": role,
                                "cycle": iteration,
                                "error": str(role_error),
                                "message": f"❌ Error in {role}: {str(role_error)}",
                                "timestamp": datetime.now().isoformat()
                            }
                        })
                
                await self.send_message(websocket, {
                    "type": "cycle_complete",
                    "data": {
                        "cycle": iteration,
                        "message": f"🔄 Iteration {iteration} complete, continuing...",
                        "timestamp": datetime.now().isoformat()
                    }
                })
            
            # Max iterations reached
            logger.info(f"⚠️ Maximum iterations ({max_iterations}) reached")
            await self.send_message(websocket, {
                "type": "max_iterations",
                "data": {
                    "iterations": max_iterations,
                    "message": f"⚠️ Maximum iterations ({max_iterations}) reached",
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            context["final"] = context.get("reviewer", {})
            context["iterations"] = iteration
            return context
            
        except Exception as e:
            logger.error(f"Error in goal execution: {e}")
            raise
    
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
                        🚀 Welcome to the Live LLM Orchestrator! 
                        
Enter a goal below to watch the AI system plan, execute, and review its way to achieving your objective in real-time.

Each role has a specific purpose:
• Planner: Creates strategic plans and breaks down goals
• Executor: Performs actions and tool calls
• Critic: Analyzes and provides feedback on execution
• Reviewer: Synthesizes results and determines completion
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
                        case 'error':
                            this.handleError(data);
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
