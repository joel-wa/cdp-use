#!/usr/bin/env python3
"""
Workflow CLI Interface

Command-line interface for workflow operations including listing, running,
recording, and managing workflows.
"""

import time
import logging
from typing import Optional
from datetime import datetime

from workflow_engine import WorkflowLibrary, WorkflowExecutor, WorkflowRecordingMode

logger = logging.getLogger(__name__)


class WorkflowCLI:
    """Command-line interface for workflow operations"""
    
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.library = WorkflowLibrary()
        self.executor = WorkflowExecutor(orchestrator.mcp_session) if orchestrator.mcp_session else None
        self.recording_mode = WorkflowRecordingMode(orchestrator)
        
    async def process_workflow_command(self, command: str) -> str:
        """Process workflow management command"""
        command = command.strip()
        
        try:
            if command == "workflow help" or command == "workflow":
                return self._get_help_text()
            elif command == "workflow list":
                return await self._list_workflows()
            elif command.startswith("workflow run "):
                workflow_name = command[13:].strip()
                return await self._run_workflow_interactive(workflow_name)
            elif command.startswith("workflow show "):
                workflow_name = command[14:].strip()
                return await self._show_workflow(workflow_name)
            elif command.startswith("workflow delete "):
                workflow_name = command[16:].strip()
                return await self._delete_workflow(workflow_name)
            elif command.startswith("workflow search "):
                query = command[16:].strip()
                return await self._search_workflows(query)
            elif command == "workflow record start":
                return await self._start_recording_interactive()
            elif command == "workflow record stop":
                return await self._stop_recording_interactive()
            elif command == "workflow record status":
                return self._get_recording_status()
            elif command == "workflow stats":
                return await self._show_workflow_stats()
            elif command == "workflow suggest":
                return await self._suggest_workflows()
            else:
                return f"Unknown workflow command: {command}. Type 'workflow help' for available commands."
                
        except Exception as e:
            logger.error(f"Error processing workflow command: {e}")
            return f"❌ Error: {e}"
    
    def _get_help_text(self) -> str:
        """Get help text for workflow commands"""
        return """
🔧 Workflow Management System

Available Commands:
• workflow list                    - List all available workflows
• workflow run <name>              - Execute a workflow interactively
• workflow show <name>             - Show workflow definition
• workflow delete <name>           - Delete a workflow
• workflow search <query>          - Search workflows by name/description
• workflow record start           - Start recording for workflow creation
• workflow record stop            - Stop recording and create workflow
• workflow record status          - Check recording status
• workflow stats                  - Show workflow execution statistics
• workflow suggest                - Get workflow suggestions based on activity
• workflow help                   - Show this help message

Examples:
  workflow run web_data_extraction
  workflow search "web scraping"
  workflow record start
        """
    
    async def _list_workflows(self) -> str:
        """List available workflows"""
        workflows = await self.library.list_workflows()
        
        if not workflows:
            return "📝 No workflows available. Start recording to create your first workflow!"
            
        result = "📋 Available Workflows:\n\n"
        
        for name in workflows:
            try:
                workflow = await self.library.load_workflow(name)
                if workflow:
                    stats = await self.library.get_workflow_stats(name)
                    result += f"• {name}\n"
                    result += f"  Description: {workflow.description}\n"
                    result += f"  Steps: {len(workflow.steps)}, Parameters: {len(workflow.parameters)}\n"
                    if stats["executions"] > 0:
                        result += f"  Executions: {stats['executions']}, Success Rate: {stats['success_rate']:.1%}\n"
                    result += "\n"
            except Exception as e:
                result += f"• {name} (Error loading: {e})\n"
                
        return result.strip()
    
    async def _run_workflow_interactive(self, workflow_name: str) -> str:
        """Run workflow with interactive parameter input"""
        if not self.executor:
            return "❌ Workflow executor not available (MCP session not connected)"
            
        workflow = await self.library.load_workflow(workflow_name)
        if not workflow:
            return f"❌ Workflow '{workflow_name}' not found"
            
        try:
            parameters = {}
            for param in workflow.parameters:
                if param.default is not None:
                    parameters[param.name] = param.default
                else:
                    if param.type == "string":
                        parameters[param.name] = ""
                    elif param.type == "integer":
                        parameters[param.name] = 0
                    elif param.type == "float":
                        parameters[param.name] = 0.0
                    elif param.type == "boolean":
                        parameters[param.name] = False
                    elif param.type == "array":
                        parameters[param.name] = []
                    elif param.type == "object":
                        parameters[param.name] = {}
                        
            result = await self.executor.execute_workflow(workflow, parameters)
            self.library.record_execution(result)
            
            if result.success:
                output = f"✅ Workflow '{workflow_name}' completed successfully in {result.execution_time.total_seconds():.1f}s\n\n"
                output += f"Steps executed: {result.steps_executed}/{len(workflow.steps)}\n"
                
                if result.outputs:
                    output += "\n📤 Outputs:\n"
                    for name, value in result.outputs.items():
                        if isinstance(value, list) and len(value) > 5:
                            output += f"• {name}: {len(value)} items\n"
                        else:
                            output += f"• {name}: {value}\n"
                            
                return output
            else:
                return f"❌ Workflow '{workflow_name}' failed: {result.error}"
                
        except Exception as e:
            return f"❌ Error executing workflow: {e}"
    
    async def _show_workflow(self, workflow_name: str) -> str:
        """Show workflow definition details"""
        workflow = await self.library.load_workflow(workflow_name)
        if not workflow:
            return f"❌ Workflow '{workflow_name}' not found"
            
        output = f"📋 Workflow: {workflow.name}\n"
        output += f"Version: {workflow.version}\n"
        output += f"Description: {workflow.description}\n"
        output += f"Author: {workflow.author}\n"
        output += f"Created: {workflow.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        if workflow.parameters:
            output += "📥 Parameters:\n"
            for param in workflow.parameters:
                output += f"• {param.name} ({param.type})"
                if param.required:
                    output += " *required*"
                if param.default is not None:
                    output += f" = {param.default}"
                output += f"\n  {param.description}\n"
            output += "\n"
            
        output += f"🔄 Steps ({len(workflow.steps)}):\n"
        for i, step in enumerate(workflow.steps, 1):
            output += f"{i}. {step.id} - {step.tool}\n"
            output += f"   {step.description}\n"
            if step.depends_on:
                output += f"   Depends on: {', '.join(step.depends_on)}\n"
        
        return output
    
    async def _delete_workflow(self, workflow_name: str) -> str:
        """Delete a workflow"""
        success = await self.library.delete_workflow(workflow_name)
        if success:
            return f"✅ Deleted workflow: {workflow_name}"
        else:
            return f"❌ Failed to delete workflow: {workflow_name}"
    
    async def _search_workflows(self, query: str) -> str:
        """Search workflows by query"""
        workflows = await self.library.search_workflows(query)
        
        if not workflows:
            return f"🔍 No workflows found matching '{query}'"
            
        output = f"🔍 Found {len(workflows)} workflows matching '{query}':\n\n"
        for workflow in workflows:
            output += f"• {workflow.name}\n"
            output += f"  {workflow.description}\n\n"
            
        return output.strip()
    
    async def _start_recording_interactive(self) -> str:
        """Start workflow recording interactively"""
        if self.recording_mode.is_recording():
            return "⚠️  Already recording a workflow session"
            
        session_name = f"session_{int(time.time())}"
        return await self.recording_mode.start_recording(session_name, "Interactive recording session")
    
    async def _stop_recording_interactive(self) -> str:
        """Stop workflow recording and create workflow"""
        if not self.recording_mode.is_recording():
            return "⚠️  No recording session active"
            
        workflow = await self.recording_mode.stop_recording_and_create_workflow("User-requested workflow")
        
        if workflow:
            return f"✅ Created workflow: {workflow.name} with {len(workflow.steps)} steps"
        else:
            return "❌ No workflow patterns detected in recording session"
    
    def _get_recording_status(self) -> str:
        """Get current recording status"""
        if self.recording_mode.is_recording():
            session = self.recording_mode.recording_session
            duration = datetime.now() - session.start_time
            tool_count = len(self.orchestrator.system_state.tool_execution_history)
            
            return f"🎬 Recording active: {session.name}\n" \
                   f"Duration: {duration.total_seconds():.0f}s\n" \
                   f"Tools executed: {tool_count}"
        else:
            return "⏹️  No recording session active"
    
    async def _show_workflow_stats(self) -> str:
        """Show workflow execution statistics"""
        workflows = await self.library.list_workflows()
        
        if not workflows:
            return "📊 No workflows available"
            
        output = "📊 Workflow Statistics:\n\n"
        
        for name in workflows:
            stats = await self.library.get_workflow_stats(name)
            if stats["executions"] > 0:
                output += f"• {name}\n"
                output += f"  Executions: {stats['executions']}\n"
                output += f"  Success Rate: {stats['success_rate']:.1%}\n"
                output += f"  Avg Duration: {stats['avg_duration']:.1f}s\n"
                output += f"  Last Run: {stats.get('last_execution', 'Never')}\n\n"
                
        return output.strip() or "📊 No execution statistics available"
    
    async def _suggest_workflows(self) -> str:
        """Get workflow suggestions"""
        candidates = await self.recording_mode.auto_suggest_workflows()
        
        if not candidates:
            return "💡 No workflow suggestions available based on recent activity"
            
        output = "💡 Workflow Suggestions:\n\n"
        
        for candidate in candidates:
            output += f"• {candidate.name}\n"
            output += f"  Description: {candidate.description}\n"
            output += f"  Confidence: {candidate.confidence_score:.1%}\n"
            output += f"  Tools: {' → '.join([r.tool_name for r in candidate.tool_chain[:3]])}\n"
            if len(candidate.tool_chain) > 3:
                output += "...\n"
            output += "\n"
            
        output += "To create a workflow from these patterns, use 'workflow record start/stop'"
        
        return output
