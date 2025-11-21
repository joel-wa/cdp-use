
import sys
import os
import asyncio
import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Add parent directories to path to import workflow_workbench modules
current_dir = Path(__file__).resolve().parent
workbench_dir = current_dir.parent
root_dir = workbench_dir.parent
sys.path.append(str(workbench_dir))
sys.path.append(str(root_dir))

# Import the orchestrator
from workflow_enhanced_orchestrator import WorkflowEnhancedConversationalOrchestrator, WorkflowRecordingMode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("studio_server")

app = FastAPI(title="Workflow Studio")

# Mount static files
app.mount("/static", StaticFiles(directory=str(current_dir / "static")), name="static")

# Global orchestrator instance
orchestrator: Optional[WorkflowEnhancedConversationalOrchestrator] = None

async def get_orchestrator():
    global orchestrator
    if orchestrator is None:
        orchestrator = WorkflowEnhancedConversationalOrchestrator()
        await orchestrator.initialize()
    return orchestrator

@app.get("/")
async def read_root():
    return FileResponse(str(current_dir / "static" / "index.html"))

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    orc = await get_orchestrator()
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "user_input":
                user_text = message["content"]
                
                # Send "thinking" status
                await websocket.send_json({"type": "status", "content": "thinking"})
                
                try:
                    # Process input using the orchestrator
                    # Note: process_user_input is async and returns a string response
                    response_text = await orc.process_user_input(user_text)
                    
                    # Send response back
                    await websocket.send_json({
                        "type": "assistant_response", 
                        "content": response_text
                    })
                    
                    # Check if we are recording and send status update
                    if orc.workflow_recording.is_recording():
                         await websocket.send_json({
                            "type": "recording_status",
                            "is_recording": True,
                            "session": orc.workflow_recording.recording_session.name if orc.workflow_recording.recording_session else "Unknown"
                        })

                except Exception as e:
                    logger.error(f"Error processing input: {e}")
                    await websocket.send_json({"type": "error", "content": str(e)})
                    
                await websocket.send_json({"type": "status", "content": "idle"})

    except WebSocketDisconnect:
        logger.info("Client disconnected")

@app.get("/api/workflows")
async def list_workflows():
    orc = await get_orchestrator()
    workflows = await orc.workflow_recording.workflow_library.list_workflows()
    return {"workflows": workflows}

@app.get("/api/workflows/{name}")
async def get_workflow(name: str):
    orc = await get_orchestrator()
    workflow = await orc.workflow_recording.workflow_library.load_workflow(name)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow.to_dict()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
