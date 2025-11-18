#!/usr/bin/env python3
"""
API Request/Response Models

Pydantic models for the Workflow Execution API.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ExecutionStatus(str, Enum):
    """Status of workflow execution"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class ExecutionPriority(str, Enum):
    """Priority level for workflow execution"""
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


# =====================================================
# REQUEST MODELS
# =====================================================

class WorkflowExecuteRequest(BaseModel):
    """Request to execute a workflow"""
    workflow_name: str = Field(..., description="Name of the workflow to execute")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Workflow parameters")
    timeout: Optional[int] = Field(default=300, description="Execution timeout in seconds", ge=1, le=3600)
    priority: ExecutionPriority = Field(default=ExecutionPriority.NORMAL, description="Execution priority")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "workflow_name": "web_data_extraction",
            "parameters": {
                "navigate_url": "https://example.com",
                "selector": ".product-price"
            },
            "timeout": 300,
            "priority": "normal"
        }
    })


class WorkflowBatchRequest(BaseModel):
    """Request to execute multiple workflows in batch"""
    workflows: List[WorkflowExecuteRequest] = Field(..., description="List of workflows to execute")
    parallel: bool = Field(default=True, description="Execute workflows in parallel")
    fail_fast: bool = Field(default=False, description="Stop on first failure")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "workflows": [
                {
                    "workflow_name": "amazon_price_check",
                    "parameters": {"product_url": "https://amazon.com/product/1"}
                },
                {
                    "workflow_name": "youtube_search",
                    "parameters": {"query": "AI news"}
                }
            ],
            "parallel": True
        }
    })


class WorkflowCancelRequest(BaseModel):
    """Request to cancel a workflow execution"""
    reason: Optional[str] = Field(default=None, description="Reason for cancellation")


# =====================================================
# RESPONSE MODELS
# =====================================================

class ExecutionProgress(BaseModel):
    """Progress information for a running workflow"""
    current_step: int = Field(..., description="Current step number (1-indexed)")
    total_steps: int = Field(..., description="Total number of steps")
    step_name: str = Field(..., description="Name of current step")
    step_tool: Optional[str] = Field(default=None, description="Tool being executed")
    percent_complete: float = Field(..., description="Percentage complete", ge=0, le=100)


class ExecutionSubmittedResponse(BaseModel):
    """Response when workflow execution is submitted"""
    execution_id: str = Field(..., description="Unique execution identifier")
    workflow_name: str = Field(..., description="Name of the workflow")
    status: ExecutionStatus = Field(..., description="Current execution status")
    submitted_at: datetime = Field(..., description="Submission timestamp")
    estimated_duration: Optional[int] = Field(default=None, description="Estimated duration in seconds")
    position_in_queue: Optional[int] = Field(default=None, description="Position in execution queue")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "execution_id": "exec_1731888000_abc123",
            "workflow_name": "web_data_extraction",
            "status": "queued",
            "submitted_at": "2025-11-18T12:00:00Z",
            "estimated_duration": 30,
            "position_in_queue": 2
        }
    })


class ExecutionStatusResponse(BaseModel):
    """Response for execution status query"""
    execution_id: str = Field(..., description="Unique execution identifier")
    workflow_name: str = Field(..., description="Name of the workflow")
    status: ExecutionStatus = Field(..., description="Current execution status")
    progress: Optional[ExecutionProgress] = Field(default=None, description="Execution progress")
    submitted_at: datetime = Field(..., description="Submission timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")
    elapsed_seconds: Optional[float] = Field(default=None, description="Elapsed time in seconds")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "execution_id": "exec_1731888000_abc123",
            "workflow_name": "web_data_extraction",
            "status": "running",
            "progress": {
                "current_step": 3,
                "total_steps": 5,
                "step_name": "execute_javascript",
                "step_tool": "execute_javascript",
                "percent_complete": 60.0
            },
            "submitted_at": "2025-11-18T12:00:00Z",
            "started_at": "2025-11-18T12:00:05Z",
            "elapsed_seconds": 15.5
        }
    })


class ExecutionResultResponse(BaseModel):
    """Response containing execution result"""
    execution_id: str = Field(..., description="Unique execution identifier")
    workflow_name: str = Field(..., description="Name of the workflow")
    status: ExecutionStatus = Field(..., description="Final execution status")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Workflow execution result")
    outputs: Optional[Dict[str, Any]] = Field(default=None, description="Workflow outputs")
    execution_time: Optional[float] = Field(default=None, description="Total execution time in seconds")
    submitted_at: datetime = Field(..., description="Submission timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    error_step: Optional[str] = Field(default=None, description="Step where error occurred")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "execution_id": "exec_1731888000_abc123",
            "workflow_name": "web_data_extraction",
            "status": "completed",
            "result": {
                "success": True,
                "data": {"price": "$29.99"}
            },
            "outputs": {
                "extracted_data": "...",
                "screenshot": "base64..."
            },
            "execution_time": 28.5,
            "completed_at": "2025-11-18T12:00:33Z"
        }
    })


class BatchExecutionResponse(BaseModel):
    """Response for batch workflow execution"""
    batch_id: str = Field(..., description="Unique batch identifier")
    total_workflows: int = Field(..., description="Total number of workflows in batch")
    executions: List[ExecutionSubmittedResponse] = Field(..., description="Individual execution submissions")
    submitted_at: datetime = Field(..., description="Batch submission timestamp")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "batch_id": "batch_1731888000_xyz",
            "total_workflows": 2,
            "executions": [
                {
                    "execution_id": "exec_1731888000_abc123",
                    "workflow_name": "amazon_price_check",
                    "status": "queued"
                },
                {
                    "execution_id": "exec_1731888000_def456",
                    "workflow_name": "youtube_search",
                    "status": "queued"
                }
            ],
            "submitted_at": "2025-11-18T12:00:00Z"
        }
    })


class WorkflowListItem(BaseModel):
    """Information about an available workflow"""
    name: str = Field(..., description="Workflow name")
    description: Optional[str] = Field(default=None, description="Workflow description")
    parameters: List[str] = Field(default_factory=list, description="Required parameter names")
    estimated_duration: Optional[int] = Field(default=None, description="Estimated duration in seconds")
    tags: List[str] = Field(default_factory=list, description="Workflow tags")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")


class WorkflowListResponse(BaseModel):
    """Response listing available workflows"""
    workflows: List[WorkflowListItem] = Field(..., description="Available workflows")
    total: int = Field(..., description="Total number of workflows")


class ActiveExecutionsResponse(BaseModel):
    """Response listing active executions"""
    executions: List[ExecutionStatusResponse] = Field(..., description="Active executions")
    total_active: int = Field(..., description="Total number of active executions")
    queued: int = Field(..., description="Number of queued executions")
    running: int = Field(..., description="Number of running executions")


class HealthResponse(BaseModel):
    """API health check response"""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")
    active_executions: int = Field(..., description="Number of active executions")
    session_pool: Dict[str, Any] = Field(..., description="Session pool status")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "healthy",
            "version": "1.0.0",
            "uptime_seconds": 3600.5,
            "active_executions": 5,
            "session_pool": {
                "available": 10,
                "active": 5,
                "total": 15
            }
        }
    })


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(default=None, description="Detailed error information")
    execution_id: Optional[str] = Field(default=None, description="Related execution ID if applicable")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")
