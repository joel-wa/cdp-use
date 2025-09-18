#!/usr/bin/env python3
"""
Workflow Enhanced Orchestrator Demo

This script demonstrates the workflow automation capabilities of the
Workflow-Enhanced Conversational Orchestrator.

Features demonstrated:
1. Workflow recording and pattern recognition
2. Automatic workflow creation from successful tool chains
3. Parameterized workflow execution
4. Workflow management via CLI commands
5. Pattern learning and suggestions

Usage:
    python workflow_demo.py
"""

import asyncio
import logging
from workflow_enhanced_orchestrator import WorkflowEnhancedConversationalOrchestrator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def demo_workflow_features():
    """Demonstrate workflow automation features"""
    
    print("🎭 Workflow Enhanced Orchestrator Demo")
    print("=" * 50)
    
    # Initialize the orchestrator
    orchestrator = WorkflowEnhancedConversationalOrchestrator()
    
    try:
        await orchestrator.initialize()
        print("✅ Orchestrator initialized successfully!\n")
        
        # Demo 1: Show available workflow commands
        print("📋 Demo 1: Available Workflow Commands")
        print("-" * 40)
        help_response = await orchestrator.workflow_cli.process_workflow_command("workflow help")
        print(help_response)
        print()
        
        # Demo 2: List existing workflows
        print("📋 Demo 2: Available Workflows")
        print("-" * 40)
        list_response = await orchestrator.workflow_cli.process_workflow_command("workflow list")
        print(list_response)
        print()
        
        # Demo 3: Show workflow recording status
        print("📋 Demo 3: Recording Status")
        print("-" * 40)
        status_response = await orchestrator.workflow_cli.process_workflow_command("workflow record status")
        print(status_response)
        print()
        
        # Demo 4: Demonstrate workflow suggestions
        print("📋 Demo 4: Workflow Suggestions")
        print("-" * 40)
        
        # Simulate some tool executions to generate patterns
        from workflow_enhanced_orchestrator import ToolExecutionResult, ToolExecutionStatus
        import datetime
        
        # Add some mock tool executions to simulate a pattern
        mock_executions = [
            ToolExecutionResult(
                tool_name="navigate",
                arguments={"url": "https://example.com"},
                status=ToolExecutionStatus.COMPLETED,
                result={"status": "success"},
                timestamp=datetime.datetime.now()
            ),
            ToolExecutionResult(
                tool_name="take_screenshot", 
                arguments={},
                status=ToolExecutionStatus.COMPLETED,
                result={"screenshot": "mock_data"},
                timestamp=datetime.datetime.now()
            ),
            ToolExecutionResult(
                tool_name="get_interactive_elements",
                arguments={},
                status=ToolExecutionStatus.COMPLETED,
                result={"elements": ["button1", "button2"]},
                timestamp=datetime.datetime.now()
            ),
            ToolExecutionResult(
                tool_name="execute_javascript",
                arguments={"expression": "document.title"},
                status=ToolExecutionStatus.COMPLETED,
                result={"result": "Example Page"},
                timestamp=datetime.datetime.now()
            )
        ]
        
        # Add mock executions to history
        orchestrator.system_state.tool_execution_history.extend(mock_executions)
        
        suggest_response = await orchestrator.workflow_cli.process_workflow_command("workflow suggest")
        print(suggest_response)
        print()
        
        # Demo 5: Show system status with workflow information
        print("📋 Demo 5: System Status")
        print("-" * 40)
        orchestrator._print_system_status()
        print()
        
        # Demo 6: Demonstrate workflow creation from pattern
        print("📋 Demo 6: Creating Workflow from Pattern")
        print("-" * 40)
        
        # Start recording
        record_start = await orchestrator.workflow_cli.process_workflow_command("workflow record start")
        print(f"Start recording: {record_start}")
        
        # Stop recording and create workflow
        record_stop = await orchestrator.workflow_cli.process_workflow_command("workflow record stop")
        print(f"Stop recording: {record_stop}")
        print()
        
        # Demo 7: List workflows again to show new workflow
        print("📋 Demo 7: Updated Workflow List")
        print("-" * 40)
        updated_list = await orchestrator.workflow_cli.process_workflow_command("workflow list")
        print(updated_list)
        print()
        
        print("🎉 Demo completed successfully!")
        print("\n📚 Key Features Demonstrated:")
        print("• Workflow command interface")
        print("• Pattern recognition and learning")
        print("• Automatic workflow creation")
        print("• Workflow management and storage")
        print("• Integration with existing orchestrator features")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"❌ Demo failed: {e}")
        
    finally:
        await orchestrator.cleanup()


async def interactive_demo():
    """Run interactive demo with user input"""
    
    print("🎮 Interactive Workflow Demo")
    print("=" * 50)
    print("This demo will run the full interactive orchestrator with workflow features.")
    print("You can try commands like:")
    print("• 'workflow help' - Show workflow commands")
    print("• 'workflow record start' - Start recording workflow")
    print("• 'navigate to https://example.com' - Normal operation")
    print("• 'workflow record stop' - Stop and save workflow")
    print("• 'workflow list' - Show saved workflows")
    print("• 'quit' - Exit demo")
    print()
    
    orchestrator = WorkflowEnhancedConversationalOrchestrator()
    
    try:
        await orchestrator.initialize()
        await orchestrator.run_interactive_session()
        
    except Exception as e:
        logger.error(f"Interactive demo failed: {e}")
        print(f"❌ Interactive demo failed: {e}")
        
    finally:
        await orchestrator.cleanup()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        # Run interactive demo
        asyncio.run(interactive_demo())
    else:
        # Run automated demo
        asyncio.run(demo_workflow_features())