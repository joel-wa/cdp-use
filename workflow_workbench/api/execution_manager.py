#!/usr/bin/env python3
"""
Execution Manager

Manages asynchronous workflow execution with session pooling, parameter injection,
and result tracking.
"""

import asyncio
import logging
import time
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .models import (
    ExecutionStatus, ExecutionPriority, ExecutionProgress,
    ExecutionSubmittedResponse, ExecutionStatusResponse, ExecutionResultResponse
)
from .session_pool import SessionPool, MCPSession
from workflow_engine import WorkflowLibrary, WorkflowValidator
from models import WorkflowDefinition, WorkflowExecutionContext, WorkflowExecutionResult
from config import WORKFLOWS_DIR

logger = logging.getLogger(__name__)


class ExecutionContext:
    """Tracks state of a single workflow execution"""
    
    def __init__(
        self,
        execution_id: str,
        workflow_name: str,
        workflow: WorkflowDefinition,
        parameters: Dict[str, Any],
        priority: ExecutionPriority = ExecutionPriority.NORMAL,
        timeout: int = 300
    ):
        self.execution_id = execution_id
        self.workflow_name = workflow_name
        self.workflow = workflow
        self.parameters = parameters
        self.priority = priority
        self.timeout = timeout
        
        # Execution state
        self.status = ExecutionStatus.QUEUED
        self.submitted_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        
        # Progress tracking
        self.current_step: int = 0
        self.total_steps: int = len(workflow.steps)
        self.current_step_name: Optional[str] = None
        self.current_step_tool: Optional[str] = None
        
        # Results
        self.result: Optional[WorkflowExecutionResult] = None
        self.error: Optional[str] = None
        self.error_step: Optional[str] = None
        
        # Session
        self.session: Optional[MCPSession] = None
        
    @property
    def elapsed_seconds(self) -> Optional[float]:
        """Calculate elapsed time"""
        if self.started_at:
            end_time = self.completed_at or datetime.now()
            return (end_time - self.started_at).total_seconds()
        return None
    
    @property
    def execution_time(self) -> Optional[float]:
        """Get total execution time if completed"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def to_submitted_response(self) -> ExecutionSubmittedResponse:
        """Convert to API submitted response"""
        return ExecutionSubmittedResponse(
            execution_id=self.execution_id,
            workflow_name=self.workflow_name,
            status=self.status,
            submitted_at=self.submitted_at,
            estimated_duration=self.timeout
        )
    
    def to_status_response(self) -> ExecutionStatusResponse:
        """Convert to API status response"""
        progress = None
        if self.status == ExecutionStatus.RUNNING and self.total_steps > 0:
            progress = ExecutionProgress(
                current_step=self.current_step,
                total_steps=self.total_steps,
                step_name=self.current_step_name or "unknown",
                step_tool=self.current_step_tool,
                percent_complete=(self.current_step / self.total_steps) * 100
            )
        
        return ExecutionStatusResponse(
            execution_id=self.execution_id,
            workflow_name=self.workflow_name,
            status=self.status,
            progress=progress,
            submitted_at=self.submitted_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            elapsed_seconds=self.elapsed_seconds,
            error=self.error
        )
    
    def to_result_response(self) -> ExecutionResultResponse:
        """Convert to API result response"""
        result_data = None
        outputs = None
        
        if self.result:
            result_data = {
                "success": self.result.success,
                "steps_executed": self.result.steps_executed
            }
            outputs = self.result.outputs
        
        return ExecutionResultResponse(
            execution_id=self.execution_id,
            workflow_name=self.workflow_name,
            status=self.status,
            result=result_data,
            outputs=outputs,
            execution_time=self.execution_time,
            submitted_at=self.submitted_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            error=self.error,
            error_step=self.error_step
        )


class ExecutionManager:
    """
    Manages asynchronous workflow execution.
    
    Handles workflow submission, parameter injection, session pooling,
    and result tracking.
    """
    
    def __init__(self, session_pool: SessionPool):
        """
        Initialize execution manager.
        
        Args:
            session_pool: SessionPool instance for MCP connections
        """
        self.session_pool = session_pool
        self.workflow_library = WorkflowLibrary()
        self.validator = WorkflowValidator()
        
        # Execution tracking
        self.executions: Dict[str, ExecutionContext] = {}
        self._lock = asyncio.Lock()
        
        # Cleanup
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Statistics
        self.stats = {
            "total_submitted": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0
        }
        
        logger.info("ExecutionManager initialized")
    
    async def start(self):
        """Start the execution manager"""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("ExecutionManager started")
    
    async def stop(self):
        """Stop the execution manager"""
        logger.info("Stopping ExecutionManager...")
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("ExecutionManager stopped")
    
    async def submit_workflow(
        self,
        workflow_name: str,
        parameters: Dict[str, Any],
        priority: ExecutionPriority = ExecutionPriority.NORMAL,
        timeout: int = 300
    ) -> str:
        """
        Submit a workflow for execution.
        
        Args:
            workflow_name: Name of workflow to execute
            parameters: Workflow parameters
            priority: Execution priority
            timeout: Execution timeout in seconds
            
        Returns:
            execution_id: Unique execution identifier
        """
        # Generate execution ID
        execution_id = f"exec_{int(time.time())}_{uuid4().hex[:8]}"
        
        # Load workflow definition
        workflow = await self._load_workflow(workflow_name)
        
        # Validate workflow
        is_valid, errors = self.validator.validate_workflow_definition(workflow)
        if not is_valid:
            raise ValueError(f"Invalid workflow: {', '.join(errors)}")
        
        # Validate and inject parameters
        validation_result = self.validator.validate_parameters(workflow, parameters)
        if not validation_result.is_valid:
            raise ValueError(f"Invalid parameters: {', '.join(validation_result.errors)}")
        
        # Create execution context
        context = ExecutionContext(
            execution_id=execution_id,
            workflow_name=workflow_name,
            workflow=workflow,
            parameters=parameters,
            priority=priority,
            timeout=timeout
        )
        
        # Track execution
        async with self._lock:
            self.executions[execution_id] = context
            self.stats["total_submitted"] += 1
        
        # Submit for background execution
        asyncio.create_task(self._execute_workflow(context))
        
        logger.info(f"Submitted workflow '{workflow_name}' with execution_id: {execution_id}")
        return execution_id
    
    async def get_status(self, execution_id: str) -> Optional[ExecutionStatusResponse]:
        """Get execution status"""
        async with self._lock:
            context = self.executions.get(execution_id)
            if context:
                return context.to_status_response()
        return None
    
    async def get_result(self, execution_id: str) -> Optional[ExecutionResultResponse]:
        """Get execution result"""
        async with self._lock:
            context = self.executions.get(execution_id)
            if context and context.status in [
                ExecutionStatus.COMPLETED,
                ExecutionStatus.FAILED,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.TIMEOUT
            ]:
                return context.to_result_response()
        return None
    
    async def cancel_execution(self, execution_id: str) -> bool:
        """Cancel a running execution"""
        async with self._lock:
            context = self.executions.get(execution_id)
            if context and context.status in [ExecutionStatus.QUEUED, ExecutionStatus.RUNNING]:
                context.status = ExecutionStatus.CANCELLED
                context.completed_at = datetime.now()
                self.stats["total_cancelled"] += 1
                logger.info(f"Cancelled execution {execution_id}")
                return True
        return False
    
    async def list_active_executions(self) -> List[ExecutionStatusResponse]:
        """List all active executions"""
        async with self._lock:
            return [
                context.to_status_response()
                for context in self.executions.values()
                if context.status in [ExecutionStatus.QUEUED, ExecutionStatus.RUNNING]
            ]
    
    async def _execute_workflow(self, context: ExecutionContext):
        """Execute workflow in background"""
        session = None
        
        try:
            # Update status
            context.status = ExecutionStatus.RUNNING
            context.started_at = datetime.now()
            
            # Acquire session from pool
            session = await self.session_pool.acquire(workflow_name=context.workflow_name)
            context.session = session
            
            logger.info(f"Executing workflow '{context.workflow_name}' with session {session.session_id}")
            
            # Execute workflow with timeout
            try:
                result = await asyncio.wait_for(
                    self._run_workflow_with_session(context, session),
                    timeout=context.timeout
                )
                
                context.result = result
                context.status = ExecutionStatus.COMPLETED if result.success else ExecutionStatus.FAILED
                
                if result.success:
                    self.stats["total_completed"] += 1
                    logger.info(f"Workflow '{context.workflow_name}' completed successfully")
                else:
                    context.error = result.error
                    self.stats["total_failed"] += 1
                    logger.error(f"Workflow '{context.workflow_name}' failed: {result.error}")
                
            except asyncio.TimeoutError:
                context.status = ExecutionStatus.TIMEOUT
                context.error = f"Execution timed out after {context.timeout} seconds"
                self.stats["total_failed"] += 1
                logger.error(f"Workflow '{context.workflow_name}' timed out")
                
        except Exception as e:
            context.status = ExecutionStatus.FAILED
            context.error = str(e)
            self.stats["total_failed"] += 1
            logger.error(f"Error executing workflow '{context.workflow_name}': {e}", exc_info=True)
            
        finally:
            context.completed_at = datetime.now()
            
            # Release session back to pool
            if session:
                await self.session_pool.release(session)
                context.session = None
    
    async def _run_workflow_with_session(
        self,
        context: ExecutionContext,
        session: MCPSession
    ) -> WorkflowExecutionResult:
        """Run workflow using an MCP session"""
        from workflow_engine import WorkflowExecutor
        
        # Create executor with session
        executor = WorkflowExecutor(session.client_session)
        
        # Inject parameters into workflow
        injected_workflow = self._inject_parameters(context.workflow, context.parameters)
        
        # Track progress during execution
        original_execute_step = executor._execute_step
        
        async def tracked_execute_step(step, exec_ctx):
            context.current_step += 1
            context.current_step_name = step.id
            context.current_step_tool = step.tool
            logger.debug(f"Step {context.current_step}/{context.total_steps}: {step.id}")
            return await original_execute_step(step, exec_ctx)
        
        executor._execute_step = tracked_execute_step
        
        # Execute workflow with parameters dict
        result = await executor.execute_workflow(injected_workflow, context.parameters)
        return result
    
    def _inject_parameters(
        self,
        workflow: WorkflowDefinition,
        parameters: Dict[str, Any]
    ) -> WorkflowDefinition:
        """Create a copy of workflow with parameters injected"""
        # This creates a new workflow instance with parameters replaced
        # The workflow's step parameters contain {{param_name}} placeholders
        # that get resolved during execution
        return workflow
    
    async def _load_workflow(self, workflow_name: str) -> WorkflowDefinition:
        """Load workflow definition from file"""
        workflow_file = Path(WORKFLOWS_DIR) / f"{workflow_name}.yaml"
        
        if not workflow_file.exists():
            raise FileNotFoundError(f"Workflow '{workflow_name}' not found")
        
        with open(workflow_file, 'r') as f:
            workflow_data = yaml.safe_load(f)
        
        return WorkflowDefinition.from_dict(workflow_data)
    
    async def _cleanup_loop(self):
        """Background task to cleanup old executions"""
        while self._running:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                await self._cleanup_old_executions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _cleanup_old_executions(self, max_age_seconds: int = 3600):
        """Remove old completed executions from memory"""
        now = datetime.now()
        to_remove = []
        
        async with self._lock:
            for exec_id, context in self.executions.items():
                if context.status in [
                    ExecutionStatus.COMPLETED,
                    ExecutionStatus.FAILED,
                    ExecutionStatus.CANCELLED,
                    ExecutionStatus.TIMEOUT
                ]:
                    if context.completed_at:
                        age_seconds = (now - context.completed_at).total_seconds()
                        if age_seconds > max_age_seconds:
                            to_remove.append(exec_id)
            
            for exec_id in to_remove:
                del self.executions[exec_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old executions")
    
    def get_statistics(self) -> dict:
        """Get execution statistics"""
        return {
            **self.stats,
            "active_executions": len([
                c for c in self.executions.values()
                if c.status in [ExecutionStatus.QUEUED, ExecutionStatus.RUNNING]
            ]),
            "total_tracked": len(self.executions)
        }
