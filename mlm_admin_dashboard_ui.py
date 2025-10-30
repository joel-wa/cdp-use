#!/usr/bin/env python3
"""
MLM Admin Dashboard UI - Chat-based MCP Interface

Provides a conversational interface to manage MLM system operations.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn
import aiohttp
from datetime import datetime
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="MLM Admin Dashboard UI")

# Store active WebSocket connections
connections: List[WebSocket] = []

class MLMAdminDashboard:
    def __init__(self, api_base_url: str = "http://localhost:8001"):
        self.api_base_url = api_base_url
        self.session = None
        
    async def initialize(self):
        """Initialize the HTTP session"""
        self.session = aiohttp.ClientSession()
        logger.info("✅ MLM Admin Dashboard initialized")
    
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
    
    async def process_command(self, command: str, websocket: WebSocket) -> Dict[str, Any]:
        """Process user commands and interact with MLM API"""
        command = command.strip().lower()
        
        try:
            await self.send_message(websocket, {
                "type": "processing",
                "data": {
                    "message": f"🤖 Processing command: {command}",
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            # Route command to appropriate handler
            if command.startswith(('health', 'status', 'check')):
                result = await self.handle_health_check(websocket)
            elif command.startswith(('stats', 'statistics', 'overview')):
                result = await self.handle_system_stats(websocket)
            elif command.startswith(('users', 'list users', 'show users')):
                result = await self.handle_list_users(websocket)
            elif command.startswith(('create user', 'add user', 'new user')):
                result = await self.handle_create_user_flow(websocket)
            elif command.startswith(('products', 'list products', 'show products')):
                result = await self.handle_list_products(websocket)
            elif command.startswith(('sales', 'sales overview', 'sales stats')):
                result = await self.handle_sales_overview(websocket)
            elif command.startswith(('network', 'network overview', 'mlm network')):
                result = await self.handle_network_overview(websocket)
            elif command.startswith(('commissions', 'commission overview')):
                result = await self.handle_commissions_overview(websocket)
            elif command.startswith(('stock transfers', 'transfers')):
                result = await self.handle_stock_transfers(websocket)
            elif command.startswith(('top performers', 'top users', 'best performers')):
                result = await self.handle_top_performers(websocket)
            else:
                result = await self.handle_help(websocket)
            
            await self.send_message(websocket, {
                "type": "command_complete",
                "data": {
                    "message": "✅ Command completed successfully",
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing command: {e}")
            await self.send_message(websocket, {
                "type": "error",
                "data": {
                    "message": f"❌ Error processing command: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }
            })
            raise
    
    async def handle_health_check(self, websocket: WebSocket) -> Dict[str, Any]:
        """Check system health"""
        await self.send_message(websocket, {
            "type": "api_call",
            "data": {
                "message": "🏥 Checking system health...",
                "endpoint": "/admin/system/health",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        try:
            async with self.session.get(f"{self.api_base_url}/admin/system/health") as response:
                data = await response.json()
                
                await self.send_message(websocket, {
                    "type": "health_status",
                    "data": {
                        "status": "healthy" if response.status == 200 else "unhealthy",
                        "details": data,
                        "message": f"🏥 System Health: {'✅ Healthy' if response.status == 200 else '❌ Unhealthy'}",
                        "timestamp": datetime.now().isoformat()
                    }
                })
                
                return {"status": "success", "data": data}
        except Exception as e:
            await self.send_message(websocket, {
                "type": "health_status",
                "data": {
                    "status": "error",
                    "message": f"🏥 Health Check Failed: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }
            })
            raise
    
    async def handle_system_stats(self, websocket: WebSocket) -> Dict[str, Any]:
        """Get system statistics"""
        await self.send_message(websocket, {
            "type": "api_call",
            "data": {
                "message": "📊 Fetching system statistics...",
                "endpoint": "/admin/system/stats",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        try:
            async with self.session.get(f"{self.api_base_url}/admin/system/stats") as response:
                data = await response.json()
                
                # Format stats for display
                formatted_stats = self.format_system_stats(data)
                
                await self.send_message(websocket, {
                    "type": "system_stats",
                    "data": {
                        "stats": data,
                        "formatted": formatted_stats,
                        "message": "📊 System Statistics Retrieved",
                        "timestamp": datetime.now().isoformat()
                    }
                })
                
                return {"status": "success", "data": data}
        except Exception as e:
            logger.error(f"Error fetching system stats: {e}")
            raise
    
    async def handle_list_users(self, websocket: WebSocket) -> Dict[str, Any]:
        """List all users"""
        await self.send_message(websocket, {
            "type": "api_call",
            "data": {
                "message": "👥 Fetching users list...",
                "endpoint": "/admin/users",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        try:
            params = {"limit": 20, "page": 1}
            async with self.session.get(f"{self.api_base_url}/admin/users", params=params) as response:
                data = await response.json()
                
                await self.send_message(websocket, {
                    "type": "users_list",
                    "data": {
                        "users": data.get('users', []),
                        "total": data.get('total', 0),
                        "page": data.get('page', 1),
                        "message": f"👥 Found {data.get('total', 0)} users",
                        "timestamp": datetime.now().isoformat()
                    }
                })
                
                return {"status": "success", "data": data}
        except Exception as e:
            logger.error(f"Error fetching users: {e}")
            raise
    
    async def handle_create_user_flow(self, websocket: WebSocket) -> Dict[str, Any]:
        """Handle interactive user creation flow"""
        await self.send_message(websocket, {
            "type": "interactive_form",
            "data": {
                "form_type": "create_user",
                "message": "👤 User Creation Form",
                "fields": [
                    {"name": "full_name", "label": "Full Name", "type": "text", "required": True},
                    {"name": "phone_number", "label": "Phone Number", "type": "text", "required": True},
                    {"name": "ghana_card_id", "label": "Ghana Card ID", "type": "text", "required": True},
                    {"name": "user_type", "label": "User Type", "type": "select", "options": ["marketer", "distributor", "admin"], "default": "marketer"},
                    {"name": "recruiter_id", "label": "Recruiter ID (optional)", "type": "text", "required": False}
                ],
                "timestamp": datetime.now().isoformat()
            }
        })
        
        return {"status": "form_displayed", "message": "Please fill out the user creation form"}
    
    async def handle_list_products(self, websocket: WebSocket) -> Dict[str, Any]:
        """List all products"""
        await self.send_message(websocket, {
            "type": "api_call",
            "data": {
                "message": "📦 Fetching products list...",
                "endpoint": "/admin/products",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        try:
            params = {"limit": 20, "page": 1}
            async with self.session.get(f"{self.api_base_url}/admin/products", params=params) as response:
                data = await response.json()
                
                await self.send_message(websocket, {
                    "type": "products_list",
                    "data": {
                        "products": data.get('products', []),
                        "total": data.get('total', 0),
                        "message": f"📦 Found {data.get('total', 0)} products",
                        "timestamp": datetime.now().isoformat()
                    }
                })
                
                return {"status": "success", "data": data}
        except Exception as e:
            logger.error(f"Error fetching products: {e}")
            raise
    
    async def handle_sales_overview(self, websocket: WebSocket) -> Dict[str, Any]:
        """Get sales overview"""
        await self.send_message(websocket, {
            "type": "api_call",
            "data": {
                "message": "💰 Fetching sales overview...",
                "endpoint": "/admin/sales/overview",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        try:
            async with self.session.get(f"{self.api_base_url}/admin/sales/overview") as response:
                data = await response.json()
                
                await self.send_message(websocket, {
                    "type": "sales_overview",
                    "data": {
                        "sales_data": data,
                        "message": "💰 Sales Overview Retrieved",
                        "timestamp": datetime.now().isoformat()
                    }
                })
                
                return {"status": "success", "data": data}
        except Exception as e:
            logger.error(f"Error fetching sales overview: {e}")
            raise
    
    async def handle_network_overview(self, websocket: WebSocket) -> Dict[str, Any]:
        """Get network overview"""
        await self.send_message(websocket, {
            "type": "api_call",
            "data": {
                "message": "🌐 Fetching network overview...",
                "endpoint": "/admin/network/overview",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        try:
            async with self.session.get(f"{self.api_base_url}/admin/network/overview") as response:
                data = await response.json()
                
                await self.send_message(websocket, {
                    "type": "network_overview",
                    "data": {
                        "network_data": data,
                        "message": "🌐 Network Overview Retrieved",
                        "timestamp": datetime.now().isoformat()
                    }
                })
                
                return {"status": "success", "data": data}
        except Exception as e:
            logger.error(f"Error fetching network overview: {e}")
            raise
    
    async def handle_commissions_overview(self, websocket: WebSocket) -> Dict[str, Any]:
        """Get commissions overview"""
        await self.send_message(websocket, {
            "type": "api_call",
            "data": {
                "message": "💵 Fetching commissions overview...",
                "endpoint": "/admin/commissions/overview",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        try:
            async with self.session.get(f"{self.api_base_url}/admin/commissions/overview") as response:
                data = await response.json()
                
                await self.send_message(websocket, {
                    "type": "commissions_overview",
                    "data": {
                        "commissions_data": data,
                        "message": "💵 Commissions Overview Retrieved",
                        "timestamp": datetime.now().isoformat()
                    }
                })
                
                return {"status": "success", "data": data}
        except Exception as e:
            logger.error(f"Error fetching commissions overview: {e}")
            raise
    
    async def handle_stock_transfers(self, websocket: WebSocket) -> Dict[str, Any]:
        """List stock transfers"""
        await self.send_message(websocket, {
            "type": "api_call",
            "data": {
                "message": "📋 Fetching stock transfers...",
                "endpoint": "/admin/stock-transfers",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        try:
            params = {"limit": 20, "page": 1}
            async with self.session.get(f"{self.api_base_url}/admin/stock-transfers", params=params) as response:
                data = await response.json()
                
                await self.send_message(websocket, {
                    "type": "stock_transfers",
                    "data": {
                        "transfers": data.get('transfers', []),
                        "total": data.get('total', 0),
                        "message": f"📋 Found {data.get('total', 0)} stock transfers",
                        "timestamp": datetime.now().isoformat()
                    }
                })
                
                return {"status": "success", "data": data}
        except Exception as e:
            logger.error(f"Error fetching stock transfers: {e}")
            raise
    
    async def handle_top_performers(self, websocket: WebSocket) -> Dict[str, Any]:
        """Get top performing users"""
        await self.send_message(websocket, {
            "type": "api_call",
            "data": {
                "message": "🏆 Fetching top performers...",
                "endpoint": "/admin/sales/top-performers",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        try:
            params = {"limit": 10, "period": "month"}
            async with self.session.get(f"{self.api_base_url}/admin/sales/top-performers", params=params) as response:
                data = await response.json()
                
                await self.send_message(websocket, {
                    "type": "top_performers",
                    "data": {
                        "performers": data.get('top_performers', []),
                        "period": "month",
                        "message": f"🏆 Top 10 Performers This Month",
                        "timestamp": datetime.now().isoformat()
                    }
                })
                
                return {"status": "success", "data": data}
        except Exception as e:
            logger.error(f"Error fetching top performers: {e}")
            raise
    
    async def handle_help(self, websocket: WebSocket) -> Dict[str, Any]:
        """Show available commands"""
        help_text = """
        🤖 **MLM Admin Dashboard Commands:**
        
        **System:**
        • `health` - Check system health
        • `stats` - View system statistics
        
        **Users:**
        • `users` - List all users
        • `create user` - Create a new user
        
        **Products:**
        • `products` - List all products
        
        **Sales & Analytics:**
        • `sales` - View sales overview
        • `top performers` - View top performing users
        
        **Network:**
        • `network` - View MLM network overview
        
        **Financial:**
        • `commissions` - View commissions overview
        
        **Operations:**
        • `stock transfers` - View stock transfers
        
        Type any of these commands to get started!
        """
        
        await self.send_message(websocket, {
            "type": "help",
            "data": {
                "help_text": help_text,
                "message": "📋 Available Commands",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        return {"status": "help_displayed"}
    
    def format_system_stats(self, stats: Dict[str, Any]) -> str:
        """Format system statistics for display"""
        formatted = "📊 **System Statistics:**\n\n"
        
        if isinstance(stats, dict):
            for key, value in stats.items():
                if isinstance(value, (int, float)):
                    formatted += f"• {key.replace('_', ' ').title()}: {value:,}\n"
                elif isinstance(value, str):
                    formatted += f"• {key.replace('_', ' ').title()}: {value}\n"
                elif isinstance(value, dict):
                    formatted += f"• **{key.replace('_', ' ').title()}:**\n"
                    for sub_key, sub_value in value.items():
                        formatted += f"  - {sub_key.replace('_', ' ').title()}: {sub_value}\n"
        
        return formatted
    
    async def create_user(self, user_data: Dict[str, Any], websocket: WebSocket) -> Dict[str, Any]:
        """Create a new user via API"""
        await self.send_message(websocket, {
            "type": "api_call",
            "data": {
                "message": f"👤 Creating user: {user_data.get('full_name')}...",
                "endpoint": "/admin/users",
                "method": "POST",
                "timestamp": datetime.now().isoformat()
            }
        })
        
        try:
            async with self.session.post(f"{self.api_base_url}/admin/users", json=user_data) as response:
                if response.status == 201:
                    result = await response.json()
                    await self.send_message(websocket, {
                        "type": "user_created",
                        "data": {
                            "user": result,
                            "message": f"✅ User '{user_data.get('full_name')}' created successfully!",
                            "timestamp": datetime.now().isoformat()
                        }
                    })
                    return {"status": "success", "user": result}
                else:
                    error_data = await response.json()
                    raise Exception(f"API returned {response.status}: {error_data}")
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            await self.send_message(websocket, {
                "type": "error",
                "data": {
                    "message": f"❌ Failed to create user: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }
            })
            raise
    
    async def send_message(self, websocket: WebSocket, message: Dict[str, Any]):
        """Send message to WebSocket with proper error handling"""
        try:
            message_json = json.dumps(message)
            logger.info(f"📤 Sending message: {message['type']} - {message.get('data', {}).get('message', '')}")
            await websocket.send_text(message_json)
            await asyncio.sleep(0.1)  # Small delay to ensure message is processed
        except Exception as e:
            logger.error(f"❌ Error sending WebSocket message: {e}")
            raise

# Global dashboard instance
mlm_dashboard = MLMAdminDashboard()

@app.on_event("startup")
async def startup_event():
    """Initialize the dashboard on startup"""
    await mlm_dashboard.initialize()

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    await mlm_dashboard.close()

@app.get("/", response_class=HTMLResponse)
async def get_ui():
    """Serve the main UI"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MLM Admin Dashboard - Chat Interface</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                background: #f8f9fa;
                color: #333;
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
                border-bottom: 1px solid #e0e6ed;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }

            .header h1 {
                font-size: 24px;
                font-weight: 600;
                margin-bottom: 8px;
            }

            .header .subtitle {
                font-size: 14px;
                opacity: 0.9;
            }

            .status {
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 14px;
                margin-top: 10px;
            }

            .status-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: rgba(255,255,255,0.6);
            }

            .status-dot.active {
                background: #4ade80;
                animation: pulse 2s infinite;
            }

            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.6; }
            }

            .chat-container {
                flex: 1;
                overflow-y: auto;
                padding: 20px 30px;
                scroll-behavior: smooth;
                background: white;
            }

            .message {
                margin-bottom: 24px;
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
                border-radius: 16px;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            .role-badge.system {
                background: #f1f5f9;
                color: #64748b;
            }

            .role-badge.processing {
                background: #fef3c7;
                color: #d97706;
            }

            .role-badge.api_call {
                background: #ddd6fe;
                color: #7c3aed;
            }

            .role-badge.success {
                background: #dcfce7;
                color: #16a34a;
            }

            .role-badge.error {
                background: #fecaca;
                color: #dc2626;
            }

            .role-badge.help {
                background: #e0f2fe;
                color: #0369a1;
            }

            .timestamp {
                font-size: 11px;
                color: #94a3b8;
                margin-left: auto;
            }

            .message-content {
                padding: 20px;
                border-radius: 12px;
                border: 1px solid #e2e8f0;
                font-size: 14px;
                line-height: 1.6;
                white-space: pre-wrap;
                background: white;
            }

            .message.system .message-content {
                border-left: 4px solid #64748b;
                background: #f8fafc;
            }

            .message.processing .message-content {
                border-left: 4px solid #d97706;
                background: #fffbeb;
            }

            .message.api_call .message-content {
                border-left: 4px solid #7c3aed;
                background: #faf5ff;
            }

            .message.success .message-content {
                border-left: 4px solid #16a34a;
                background: #f0fdf4;
            }

            .message.error .message-content {
                border-left: 4px solid #dc2626;
                background: #fef2f2;
            }

            .message.help .message-content {
                border-left: 4px solid #0369a1;
                background: #f0f9ff;
            }

            .controls {
                padding: 20px 30px;
                border-top: 1px solid #e2e8f0;
                background: white;
            }

            .input-container {
                display: flex;
                gap: 15px;
                align-items: center;
            }

            .command-input {
                flex: 1;
                padding: 12px 16px;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                font-size: 14px;
                outline: none;
                transition: border-color 0.2s;
            }

            .command-input:focus {
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }

            .btn {
                padding: 12px 24px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
            }

            .btn:hover {
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
            }

            .btn:disabled {
                background: #94a3b8;
                cursor: not-allowed;
                transform: none;
                box-shadow: none;
            }

            .btn.secondary {
                background: white;
                color: #667eea;
                border: 2px solid #667eea;
            }

            .btn.secondary:hover {
                background: #f8fafc;
            }

            .data-table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 16px;
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }

            .data-table th,
            .data-table td {
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #e2e8f0;
                font-size: 13px;
            }

            .data-table th {
                background: #f8fafc;
                font-weight: 600;
                color: #374151;
            }

            .data-table tr:last-child td {
                border-bottom: none;
            }

            .data-table tr:hover {
                background: #f9fafb;
            }

            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 16px;
                margin-top: 16px;
            }

            .stat-card {
                background: white;
                padding: 20px;
                border-radius: 8px;
                border: 1px solid #e2e8f0;
                text-align: center;
            }

            .stat-value {
                font-size: 24px;
                font-weight: 700;
                color: #667eea;
                margin-bottom: 4px;
            }

            .stat-label {
                font-size: 12px;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }

            .form-container {
                background: white;
                padding: 24px;
                border-radius: 12px;
                border: 1px solid #e2e8f0;
                margin-top: 16px;
            }

            .form-row {
                margin-bottom: 20px;
            }

            .form-label {
                display: block;
                margin-bottom: 8px;
                font-weight: 600;
                color: #374151;
                font-size: 14px;
            }

            .form-input,
            .form-select {
                width: 100%;
                padding: 12px;
                border: 2px solid #e2e8f0;
                border-radius: 6px;
                font-size: 14px;
                transition: border-color 0.2s;
            }

            .form-input:focus,
            .form-select:focus {
                outline: none;
                border-color: #667eea;
            }

            .form-actions {
                display: flex;
                gap: 12px;
                justify-content: flex-end;
                margin-top: 24px;
                padding-top: 24px;
                border-top: 1px solid #e2e8f0;
            }

            .quick-commands {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin-bottom: 16px;
            }

            .quick-command {
                padding: 6px 12px;
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
                border-radius: 20px;
                font-size: 12px;
                cursor: pointer;
                transition: all 0.2s;
            }

            .quick-command:hover {
                background: #e2e8f0;
                border-color: #94a3b8;
            }

            @media (max-width: 768px) {
                .container {
                    height: 100vh;
                }

                .header {
                    padding: 15px 20px;
                }

                .chat-container {
                    padding: 15px 20px;
                }

                .controls {
                    padding: 15px 20px;
                }

                .input-container {
                    flex-direction: column;
                    gap: 10px;
                }

                .stats-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏢 MLM Admin Dashboard</h1>
                <div class="subtitle">Conversational MLM System Management Interface</div>
                <div class="status">
                    <div class="status-dot" id="statusDot"></div>
                    <span id="statusText">Ready</span>
                </div>
            </div>

            <div class="chat-container" id="chatContainer">
                <div class="message system">
                    <div class="message-content">
                        🚀 **Welcome to MLM Admin Dashboard!**
                        
This is your conversational interface for managing the MLM system. You can type natural language commands to:

• Check system health and statistics
• Manage users and products
• View sales analytics and top performers  
• Monitor MLM network structure
• Handle commissions and stock transfers

**Quick Start:** Try typing "help" to see all available commands, or use the quick commands below.
                    </div>
                </div>
            </div>

            <div class="controls">
                <div class="quick-commands">
                    <span class="quick-command" data-command="health">🏥 Health Check</span>
                    <span class="quick-command" data-command="stats">📊 System Stats</span>
                    <span class="quick-command" data-command="users">👥 List Users</span>
                    <span class="quick-command" data-command="products">📦 Products</span>
                    <span class="quick-command" data-command="sales">💰 Sales Overview</span>
                    <span class="quick-command" data-command="network">🌐 MLM Network</span>
                    <span class="quick-command" data-command="top performers">🏆 Top Performers</span>
                </div>
                <div class="input-container">
                    <input 
                        type="text" 
                        class="command-input" 
                        id="commandInput" 
                        placeholder="Type a command... (e.g., 'show users', 'sales stats', 'health check')"
                    >
                    <button class="btn" id="sendBtn">Send</button>
                    <button class="btn secondary" id="clearBtn">Clear</button>
                </div>
            </div>
        </div>

        <script>
            class MLMAdminUI {
                constructor() {
                    this.chatContainer = document.getElementById('chatContainer');
                    this.commandInput = document.getElementById('commandInput');
                    this.sendBtn = document.getElementById('sendBtn');
                    this.clearBtn = document.getElementById('clearBtn');
                    this.statusDot = document.getElementById('statusDot');
                    this.statusText = document.getElementById('statusText');
                    
                    this.websocket = null;
                    this.isProcessing = false;
                    
                    this.initializeEventListeners();
                    this.connectWebSocket();
                }

                initializeEventListeners() {
                    this.sendBtn.addEventListener('click', () => this.sendCommand());
                    this.clearBtn.addEventListener('click', () => this.clearChat());
                    this.commandInput.addEventListener('keypress', (e) => {
                        if (e.key === 'Enter' && !this.isProcessing) {
                            this.sendCommand();
                        }
                    });

                    // Quick command buttons
                    document.querySelectorAll('.quick-command').forEach(btn => {
                        btn.addEventListener('click', () => {
                            const command = btn.getAttribute('data-command');
                            this.commandInput.value = command;
                            this.sendCommand();
                        });
                    });
                }

                connectWebSocket() {
                    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                    const wsUrl = `${protocol}//${window.location.host}/ws`;
                    
                    this.websocket = new WebSocket(wsUrl);
                    
                    this.websocket.onopen = () => {
                        console.log('WebSocket connected');
                        this.statusText.textContent = 'Connected';
                        this.statusDot.classList.add('active');
                    };
                    
                    this.websocket.onmessage = (event) => {
                        const message = JSON.parse(event.data);
                        this.handleWebSocketMessage(message);
                    };
                    
                    this.websocket.onclose = () => {
                        console.log('WebSocket disconnected');
                        this.statusText.textContent = 'Disconnected';
                        this.statusDot.classList.remove('active');
                        setTimeout(() => this.connectWebSocket(), 3000);
                    };
                    
                    this.websocket.onerror = (error) => {
                        console.error('WebSocket error:', error);
                        this.statusText.textContent = 'Error';
                        this.statusDot.classList.remove('active');
                    };
                }

                handleWebSocketMessage(message) {
                    const { type, data } = message;
                    
                    switch (type) {
                        case 'processing':
                            this.addMessage('processing', data.message, data.timestamp);
                            break;
                        case 'api_call':
                            this.addMessage('api_call', `${data.message}\n📍 Endpoint: ${data.endpoint}`, data.timestamp);
                            break;
                        case 'command_complete':
                            this.addMessage('success', data.message, data.timestamp);
                            this.isProcessing = false;
                            this.updateUIState();
                            break;
                        case 'health_status':
                            this.handleHealthStatus(data);
                            break;
                        case 'system_stats':
                            this.handleSystemStats(data);
                            break;
                        case 'users_list':
                            this.handleUsersList(data);
                            break;
                        case 'products_list':
                            this.handleProductsList(data);
                            break;
                        case 'sales_overview':
                            this.handleSalesOverview(data);
                            break;
                        case 'network_overview':
                            this.handleNetworkOverview(data);
                            break;
                        case 'commissions_overview':
                            this.handleCommissionsOverview(data);
                            break;
                        case 'stock_transfers':
                            this.handleStockTransfers(data);
                            break;
                        case 'top_performers':
                            this.handleTopPerformers(data);
                            break;
                        case 'interactive_form':
                            this.handleInteractiveForm(data);
                            break;
                        case 'user_created':
                            this.addMessage('success', data.message, data.timestamp);
                            break;
                        case 'help':
                            this.addMessage('help', data.help_text, data.timestamp);
                            break;
                        case 'error':
                            this.addMessage('error', data.message, data.timestamp);
                            this.isProcessing = false;
                            this.updateUIState();
                            break;
                    }
                }

                handleHealthStatus(data) {
                    let content = `${data.message}\n\n`;
                    if (data.details) {
                        content += `**Status Details:**\n${JSON.stringify(data.details, null, 2)}`;
                    }
                    this.addMessage(data.status === 'healthy' ? 'success' : 'error', content, data.timestamp);
                }

                handleSystemStats(data) {
                    if (data.formatted) {
                        this.addMessage('success', data.formatted, data.timestamp);
                    } else {
                        this.addMessage('success', `${data.message}\n\n${JSON.stringify(data.stats, null, 2)}`, data.timestamp);
                    }
                    
                    // Add visual stats if available
                    if (data.stats && typeof data.stats === 'object') {
                        this.addStatsCards(data.stats);
                    }
                }

                handleUsersList(data) {
                    this.addMessage('success', data.message, data.timestamp);
                    if (data.users && data.users.length > 0) {
                        this.addDataTable('Users', data.users, ['id', 'full_name', 'phone_number', 'user_type', 'status']);
                    }
                }

                handleProductsList(data) {
                    this.addMessage('success', data.message, data.timestamp);
                    if (data.products && data.products.length > 0) {
                        this.addDataTable('Products', data.products, ['id', 'name', 'price', 'stock', 'category']);
                    }
                }

                handleSalesOverview(data) {
                    this.addMessage('success', data.message, data.timestamp);
                    if (data.sales_data) {
                        this.addMessage('success', `**Sales Data:**\n${JSON.stringify(data.sales_data, null, 2)}`, data.timestamp);
                    }
                }

                handleNetworkOverview(data) {
                    this.addMessage('success', data.message, data.timestamp);
                    if (data.network_data) {
                        this.addMessage('success', `**Network Data:**\n${JSON.stringify(data.network_data, null, 2)}`, data.timestamp);
                    }
                }

                handleCommissionsOverview(data) {
                    this.addMessage('success', data.message, data.timestamp);
                    if (data.commissions_data) {
                        this.addMessage('success', `**Commissions Data:**\n${JSON.stringify(data.commissions_data, null, 2)}`, data.timestamp);
                    }
                }

                handleStockTransfers(data) {
                    this.addMessage('success', data.message, data.timestamp);
                    if (data.transfers && data.transfers.length > 0) {
                        this.addDataTable('Stock Transfers', data.transfers, ['id', 'distributor_id', 'recipient_id', 'status', 'created_at']);
                    }
                }

                handleTopPerformers(data) {
                    this.addMessage('success', data.message, data.timestamp);
                    if (data.performers && data.performers.length > 0) {
                        this.addDataTable('Top Performers', data.performers, ['user_id', 'full_name', 'total_sales', 'commission_earned']);
                    }
                }

                handleInteractiveForm(data) {
                    this.addMessage('system', data.message, data.timestamp);
                    if (data.form_type === 'create_user') {
                        this.addUserCreationForm(data.fields);
                    }
                }

                sendCommand() {
                    if (this.isProcessing || !this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
                        return;
                    }
                    
                    const command = this.commandInput.value.trim();
                    if (!command) return;

                    this.isProcessing = true;
                    this.updateUIState();
                    
                    // Add user message
                    this.addMessage('system', `🤖 **You:** ${command}`, new Date().toISOString());
                    
                    // Send command to backend
                    this.websocket.send(JSON.stringify({
                        type: 'command',
                        command: command
                    }));

                    this.commandInput.value = '';
                }

                clearChat() {
                    // Keep only the welcome message
                    const messages = this.chatContainer.querySelectorAll('.message');
                    for (let i = 1; i < messages.length; i++) {
                        messages[i].remove();
                    }
                }

                updateUIState() {
                    this.sendBtn.disabled = this.isProcessing;
                    this.commandInput.disabled = this.isProcessing;
                    this.statusText.textContent = this.isProcessing ? 'Processing...' : 'Ready';
                }

                addMessage(type, content, timestamp) {
                    const messageDiv = document.createElement('div');
                    messageDiv.className = `message ${type}`;
                    
                    const timestampStr = timestamp ? new Date(timestamp).toLocaleTimeString() : '';
                    
                    messageDiv.innerHTML = `
                        <div class="message-header">
                            <div class="role-badge ${type}">${type.replace('_', ' ')}</div>
                            <div class="timestamp">${timestampStr}</div>
                        </div>
                        <div class="message-content">${content}</div>
                    `;

                    this.chatContainer.appendChild(messageDiv);
                    this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
                }

                addDataTable(title, data, columns) {
                    if (!data || data.length === 0) return;
                    
                    const tableContainer = document.createElement('div');
                    tableContainer.style.marginTop = '16px';
                    
                    const table = document.createElement('table');
                    table.className = 'data-table';
                    
                    // Header
                    const thead = document.createElement('thead');
                    const headerRow = document.createElement('tr');
                    columns.forEach(col => {
                        const th = document.createElement('th');
                        th.textContent = col.replace('_', ' ').toUpperCase();
                        headerRow.appendChild(th);
                    });
                    thead.appendChild(headerRow);
                    table.appendChild(thead);
                    
                    // Body
                    const tbody = document.createElement('tbody');
                    data.slice(0, 10).forEach(item => { // Limit to 10 rows
                        const row = document.createElement('tr');
                        columns.forEach(col => {
                            const td = document.createElement('td');
                            td.textContent = item[col] || 'N/A';
                            row.appendChild(td);
                        });
                        tbody.appendChild(row);
                    });
                    table.appendChild(tbody);
                    
                    tableContainer.appendChild(table);
                    this.chatContainer.appendChild(tableContainer);
                    this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
                }

                addStatsCards(stats) {
                    const statsContainer = document.createElement('div');
                    statsContainer.className = 'stats-grid';
                    
                    Object.entries(stats).forEach(([key, value]) => {
                        if (typeof value === 'number') {
                            const card = document.createElement('div');
                            card.className = 'stat-card';
                            card.innerHTML = `
                                <div class="stat-value">${value.toLocaleString()}</div>
                                <div class="stat-label">${key.replace('_', ' ')}</div>
                            `;
                            statsContainer.appendChild(card);
                        }
                    });
                    
                    if (statsContainer.children.length > 0) {
                        this.chatContainer.appendChild(statsContainer);
                        this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
                    }
                }

                addUserCreationForm(fields) {
                    const formContainer = document.createElement('div');
                    formContainer.className = 'form-container';
                    formContainer.id = 'user-creation-form';
                    
                    let formHTML = '<h3>Create New User</h3>';
                    
                    fields.forEach(field => {
                        formHTML += `
                            <div class="form-row">
                                <label class="form-label" for="${field.name}">
                                    ${field.label} ${field.required ? '*' : ''}
                                </label>
                        `;
                        
                        if (field.type === 'select') {
                            formHTML += `<select class="form-select" id="${field.name}" name="${field.name}">`;
                            field.options.forEach(option => {
                                const selected = option === field.default ? 'selected' : '';
                                formHTML += `<option value="${option}" ${selected}>${option}</option>`;
                            });
                            formHTML += '</select>';
                        } else {
                            formHTML += `<input type="${field.type}" class="form-input" id="${field.name}" name="${field.name}">`;
                        }
                        
                        formHTML += '</div>';
                    });
                    
                    formHTML += `
                        <div class="form-actions">
                            <button type="button" class="btn secondary" onclick="document.getElementById('user-creation-form').remove()">Cancel</button>
                            <button type="button" class="btn" onclick="mlmUI.submitUserForm()">Create User</button>
                        </div>
                    `;
                    
                    formContainer.innerHTML = formHTML;
                    this.chatContainer.appendChild(formContainer);
                    this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
                }

                submitUserForm() {
                    const form = document.getElementById('user-creation-form');
                    const formData = {};
                    
                    form.querySelectorAll('input, select').forEach(input => {
                        if (input.value.trim()) {
                            formData[input.name] = input.value.trim();
                        }
                    });
                    
                    // Validate required fields
                    const requiredFields = ['full_name', 'phone_number', 'ghana_card_id'];
                    const missingFields = requiredFields.filter(field => !formData[field]);
                    
                    if (missingFields.length > 0) {
                        alert(`Please fill in required fields: ${missingFields.join(', ')}`);
                        return;
                    }
                    
                    // Send create user request
                    this.websocket.send(JSON.stringify({
                        type: 'create_user',
                        user_data: formData
                    }));
                    
                    form.remove();
                    this.addMessage('processing', 'Creating user...', new Date().toISOString());
                }
            }

            // Initialize the UI when the page loads
            let mlmUI;
            document.addEventListener('DOMContentLoaded', () => {
                mlmUI = new MLMAdminUI();
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
            
            if message["type"] == "command":
                command = message["command"]
                await mlm_dashboard.process_command(command, websocket)
            elif message["type"] == "create_user":
                user_data = message["user_data"]
                await mlm_dashboard.create_user(user_data, websocket)
                
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
        port=8080,
        log_level="info"
    )