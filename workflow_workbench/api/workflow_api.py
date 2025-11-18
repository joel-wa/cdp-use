#!/usr/bin/env python3
"""
Workflow Execution API

FastAPI application providing REST endpoints for asynchronous workflow execution.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import (
    WorkflowExecuteRequest, WorkflowBatchRequest, WorkflowCancelRequest,
    ExecutionSubmittedResponse, ExecutionStatusResponse, ExecutionResultResponse,
    BatchExecutionResponse, WorkflowListResponse, WorkflowListItem,
    ActiveExecutionsResponse, HealthResponse, ErrorResponse,
    ExecutionStatus, ExecutionPriority
)
from .session_pool import SessionPool
from .execution_manager import ExecutionManager
from workflow_engine import WorkflowLibrary
from config import (
    MCP_SERVER_COMMAND,
    API_HOST,
    API_PORT,
    MAX_CONCURRENT_EXECUTIONS,
    SESSION_POOL_SIZE,
    SESSION_IDLE_TIMEOUT
)

logger = logging.getLogger(__name__)

# Global state
session_pool: Optional[SessionPool] = None
execution_manager: Optional[ExecutionManager] = None
start_time: float = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global session_pool, execution_manager, start_time
    
    logger.info("Starting Workflow Execution API...")
    start_time = time.time()
    
    # Initialize session pool
    session_pool = SessionPool(
        server_command=MCP_SERVER_COMMAND,
        max_size=SESSION_POOL_SIZE,
        idle_timeout=SESSION_IDLE_TIMEOUT
    )
    await session_pool.start()
    
    # Initialize execution manager
    execution_manager = ExecutionManager(session_pool)
    await execution_manager.start()
    
    logger.info("✅ Workflow Execution API ready")
    
    yield
    
    # Cleanup
    logger.info("Shutting down Workflow Execution API...")
    if execution_manager:
        await execution_manager.stop()
    if session_pool:
        await session_pool.stop()
    logger.info("✅ Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Workflow Execution API",
    description="Asynchronous workflow execution service with MCP integration",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for UI
ui_path = Path(__file__).parent.parent / "ui"
if ui_path.exists():
    app.mount("/ui", StaticFiles(directory=str(ui_path), html=True), name="ui")


# =====================================================
# EXCEPTION HANDLERS
# =====================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            timestamp=datetime.now()
        ).model_dump(mode='json')
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc),
            timestamp=datetime.now()
        ).model_dump(mode='json')
    )


# =====================================================
# WORKFLOW EXECUTION ENDPOINTS
# =====================================================

@app.post(
    "/workflows/execute",
    response_model=ExecutionSubmittedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Execution"]
)
async def execute_workflow(request: WorkflowExecuteRequest):
    """
    Submit a workflow for asynchronous execution.
    
    The workflow will be queued and executed as soon as a session is available.
    Use the returned execution_id to check status and retrieve results.
    """
    try:
        execution_id = await execution_manager.submit_workflow(
            workflow_name=request.workflow_name,
            parameters=request.parameters,
            priority=request.priority,
            timeout=request.timeout
        )
        
        # Get initial status
        status_response = await execution_manager.get_status(execution_id)
        return status_response
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error submitting workflow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit workflow: {str(e)}"
        )


@app.post(
    "/workflows/batch",
    response_model=BatchExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Execution"]
)
async def execute_batch(request: WorkflowBatchRequest):
    """
    Execute multiple workflows in batch.
    
    All workflows will be submitted for execution. If parallel=true (default),
    they will execute concurrently. If fail_fast=true, execution will stop
    on the first failure.
    """
    batch_id = f"batch_{int(time.time())}_{len(request.workflows)}"
    executions = []
    
    try:
        for workflow_req in request.workflows:
            try:
                execution_id = await execution_manager.submit_workflow(
                    workflow_name=workflow_req.workflow_name,
                    parameters=workflow_req.parameters,
                    priority=workflow_req.priority,
                    timeout=workflow_req.timeout
                )
                
                status_response = await execution_manager.get_status(execution_id)
                executions.append(status_response)
                
            except Exception as e:
                if request.fail_fast:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Batch failed on workflow '{workflow_req.workflow_name}': {str(e)}"
                    )
                logger.error(f"Failed to submit workflow '{workflow_req.workflow_name}': {e}")
        
        return BatchExecutionResponse(
            batch_id=batch_id,
            total_workflows=len(executions),
            executions=executions,
            submitted_at=datetime.now()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing batch: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch execution failed: {str(e)}"
        )


@app.get(
    "/workflows/status/{execution_id}",
    response_model=ExecutionStatusResponse,
    tags=["Execution"]
)
async def get_execution_status(execution_id: str):
    """
    Get the current status of a workflow execution.
    
    Returns detailed status including progress information for running workflows.
    """
    status_response = await execution_manager.get_status(execution_id)
    
    if not status_response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution '{execution_id}' not found"
        )
    
    return status_response


@app.get(
    "/workflows/result/{execution_id}",
    response_model=ExecutionResultResponse,
    tags=["Execution"]
)
async def get_execution_result(execution_id: str):
    """
    Get the result of a completed workflow execution.
    
    Returns the full execution result including outputs and any errors.
    Only available for completed, failed, or cancelled executions.
    """
    result_response = await execution_manager.get_result(execution_id)
    
    if not result_response:
        # Check if execution exists but isn't complete
        status_response = await execution_manager.get_status(execution_id)
        if status_response:
            raise HTTPException(
                status_code=status.HTTP_425_TOO_EARLY,
                detail=f"Execution '{execution_id}' is still {status_response.status.value}"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution '{execution_id}' not found"
            )
    
    return result_response


@app.delete(
    "/workflows/cancel/{execution_id}",
    status_code=status.HTTP_200_OK,
    tags=["Execution"]
)
async def cancel_execution(execution_id: str, request: Optional[WorkflowCancelRequest] = None):
    """
    Cancel a queued or running workflow execution.
    
    Only queued or running executions can be cancelled.
    """
    success = await execution_manager.cancel_execution(execution_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel execution '{execution_id}' (not found or already completed)"
        )
    
    return {
        "message": f"Execution '{execution_id}' cancelled",
        "reason": request.reason if request else None
    }


# =====================================================
# WORKFLOW MANAGEMENT ENDPOINTS
# =====================================================

@app.get(
    "/workflows/list",
    response_model=WorkflowListResponse,
    tags=["Workflows"]
)
async def list_workflows():
    """
    List all available workflows.
    
    Returns information about all workflows that can be executed.
    """
    try:
        library = WorkflowLibrary()
        workflow_names = await library.list_workflows()
        
        workflows = []
        for name in workflow_names:
            try:
                workflow_def = await library.load_workflow(name)
                
                # Handle created_at - it's already a datetime object from from_dict
                created_at = workflow_def.created_at
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at)
                    except:
                        created_at = None
                
                workflows.append(WorkflowListItem(
                    name=workflow_def.name,
                    description=workflow_def.description,
                    parameters=[p.name for p in workflow_def.parameters],
                    estimated_duration=workflow_def.metadata.get("estimated_duration"),
                    tags=workflow_def.metadata.get("tags", []),
                    created_at=created_at
                ))
            except Exception as e:
                logger.error(f"Error loading workflow '{name}': {e}")
        
        return WorkflowListResponse(
            workflows=workflows,
            total=len(workflows)
        )
        
    except Exception as e:
        logger.error(f"Error listing workflows: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list workflows: {str(e)}"
        )


@app.get(
    "/workflows/active",
    response_model=ActiveExecutionsResponse,
    tags=["Workflows"]
)
async def list_active_executions():
    """
    List all active (queued or running) executions.
    
    Returns current status of all workflows that are being executed.
    """
    try:
        executions = await execution_manager.list_active_executions()
        
        queued = sum(1 for e in executions if e.status == ExecutionStatus.QUEUED)
        running = sum(1 for e in executions if e.status == ExecutionStatus.RUNNING)
        
        return ActiveExecutionsResponse(
            executions=executions,
            total_active=len(executions),
            queued=queued,
            running=running
        )
        
    except Exception as e:
        logger.error(f"Error listing active executions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list active executions: {str(e)}"
        )


# =====================================================
# HEALTH & STATUS ENDPOINTS
# =====================================================

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Status"]
)
async def health_check():
    """
    Check API health and get system status.
    
    Returns information about service health, session pool, and active executions.
    """
    try:
        pool_status = session_pool.get_status()
        exec_stats = execution_manager.get_statistics()
        
        return HealthResponse(
            status="healthy",
            version="1.0.0",
            uptime_seconds=time.time() - start_time,
            active_executions=exec_stats["active_executions"],
            session_pool={
                "available": pool_status["available"],
                "active": pool_status["active"],
                "total": pool_status["total_sessions"],
                "max_size": pool_status["max_size"]
            }
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return HealthResponse(
            status="unhealthy",
            version="1.0.0",
            uptime_seconds=time.time() - start_time,
            active_executions=0,
            session_pool={"error": str(e)}
        )


@app.get(
    "/stats",
    tags=["Status"]
)
async def get_statistics():
    """
    Get detailed statistics about the API.
    
    Returns execution statistics, session pool status, and performance metrics.
    """
    try:
        return {
            "execution_manager": execution_manager.get_statistics(),
            "session_pool": session_pool.get_status(),
            "api": {
                "uptime_seconds": time.time() - start_time,
                "start_time": datetime.fromtimestamp(start_time).isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error getting statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )


# =====================================================
# ROOT ENDPOINT
# =====================================================

@app.get("/", tags=["Root"])
async def root():
    """API root endpoint with basic information"""
    return {
        "name": "Workflow Execution API",
        "version": "1.0.0",
        "status": "running",
        "ui": "/ui/index.html",
        "docs": "/docs",
        "health": "/health"
    }
