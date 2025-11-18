# Workflow Execution API

A FastAPI-based service for asynchronous workflow execution with MCP integration and session pooling.

## 🚀 Features

- **Asynchronous Execution**: Submit workflows and get results without blocking
- **Session Pooling**: Efficient MCP session reuse for parallel execution
- **Parameter Injection**: Dynamic parameter substitution per request
- **REST API**: Standard HTTP interface accessible from any language
- **Real-time Status**: Track workflow progress and execution state
- **Batch Execution**: Execute multiple workflows in parallel
- **Auto-cleanup**: Automatic cleanup of idle sessions and old results

## 📦 Installation

1. Install dependencies:
```bash
pip install fastapi uvicorn httpx pydantic
```

2. Configure environment (optional):
```bash
# .env file
API_HOST=0.0.0.0
API_PORT=8000
MAX_CONCURRENT_EXECUTIONS=10
SESSION_POOL_SIZE=15
```

## 🎮 Usage

### Start the API Server

```bash
cd workflow_workbench
python start_api.py
```

The API will be available at `http://localhost:8000`

- API Documentation: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

### Execute a Workflow

**Python:**
```python
import httpx
import asyncio

async def run_workflow():
    async with httpx.AsyncClient() as client:
        # Submit workflow
        response = await client.post(
            "http://localhost:8000/workflows/execute",
            json={
                "workflow_name": "ajio_image",
                "parameters": {
                    "navigate_url": "https://www.ajio.com/product/12345"
                },
                "timeout": 300
            }
        )
        
        execution_id = response.json()["execution_id"]
        print(f"Execution ID: {execution_id}")
        
        # Poll for result
        while True:
            status = await client.get(
                f"http://localhost:8000/workflows/status/{execution_id}"
            )
            status_data = status.json()
            
            if status_data["status"] in ["completed", "failed"]:
                break
            
            await asyncio.sleep(1)
        
        # Get result
        result = await client.get(
            f"http://localhost:8000/workflows/result/{execution_id}"
        )
        print(result.json())

asyncio.run(run_workflow())
```

**cURL:**
```bash
# Submit workflow
curl -X POST http://localhost:8000/workflows/execute \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_name": "ajio_image",
    "parameters": {
      "navigate_url": "https://www.ajio.com/product/12345"
    }
  }'

# Check status
curl http://localhost:8000/workflows/status/exec_1731888000_abc123

# Get result
curl http://localhost:8000/workflows/result/exec_1731888000_abc123
```

### Batch Execution

```python
response = await client.post(
    "http://localhost:8000/workflows/batch",
    json={
        "workflows": [
            {
                "workflow_name": "amazon_image_test",
                "parameters": {"navigate_url": "https://amazon.com/product/1"}
            },
            {
                "workflow_name": "yt_search_bar_test",
                "parameters": {"query": "AI news"}
            }
        ],
        "parallel": True
    }
)
```

## 📚 API Endpoints

### Execution
- `POST /workflows/execute` - Submit workflow for execution
- `POST /workflows/batch` - Execute multiple workflows
- `GET /workflows/status/{execution_id}` - Get execution status
- `GET /workflows/result/{execution_id}` - Get execution result
- `DELETE /workflows/cancel/{execution_id}` - Cancel execution

### Workflows
- `GET /workflows/list` - List available workflows
- `GET /workflows/active` - List active executions

### Status
- `GET /health` - Health check
- `GET /stats` - Detailed statistics

## 🔧 Configuration

Configuration via environment variables or `.env` file:

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1

# Execution Configuration
MAX_CONCURRENT_EXECUTIONS=10
SESSION_POOL_SIZE=15
SESSION_IDLE_TIMEOUT=300
RESULT_RETENTION_SECONDS=3600

# MCP Server
MCP_SERVER_COMMAND="python mcp_server.py"
```

## 🧪 Testing

Run the test suite:

```bash
# Make sure API server is running first
python start_api.py

# In another terminal
cd tests
python test_workflow_api.py
```

## 🏗️ Architecture

```
┌─────────────────┐
│   API Client    │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│   FastAPI App   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│ ExecutionManager├─────▶ SessionPool  │
└────────┬────────┘     └──────┬───────┘
         │                     │
         │                     ▼
         │              ┌──────────────┐
         │              │ MCP Sessions │
         │              └──────┬───────┘
         │                     │
         ▼                     ▼
┌─────────────────┐     ┌──────────────┐
│ WorkflowExecutor├─────▶  MCP Server  │
└─────────────────┘     └──────────────┘
```

## 📊 Status Flow

```
QUEUED → RUNNING → COMPLETED
              ↓
           FAILED
              ↓
          CANCELLED
              ↓
           TIMEOUT
```

## 🎯 Use Cases

1. **Parallel Web Scraping**: Execute multiple scraping workflows simultaneously
2. **Automated Testing**: Run test workflows in parallel
3. **Data Extraction**: Extract data from multiple sources concurrently
4. **Monitoring**: Periodic workflow execution via cron/scheduler
5. **Integration**: Integrate with other services via REST API

## 🔍 Monitoring

Check system health:
```bash
curl http://localhost:8000/health
```

Get detailed statistics:
```bash
curl http://localhost:8000/stats
```

List active executions:
```bash
curl http://localhost:8000/workflows/active
```

## 🚦 Best Practices

1. **Always check health** before submitting workflows
2. **Set appropriate timeouts** for long-running workflows
3. **Poll status** instead of long polling
4. **Handle failures** gracefully with error checking
5. **Clean up** by letting auto-cleanup handle old results
6. **Use batch execution** for related workflows

## 🔒 Security Notes

- API runs without authentication by default
- Add authentication middleware for production
- Use HTTPS in production
- Validate all user inputs
- Rate limit requests to prevent abuse

## 📝 Example: Complete Workflow Execution

```python
import httpx
import asyncio
import time

async def execute_and_wait(workflow_name: str, parameters: dict):
    """Execute workflow and wait for completion"""
    async with httpx.AsyncClient(timeout=300.0) as client:
        # Submit
        response = await client.post(
            "http://localhost:8000/workflows/execute",
            json={
                "workflow_name": workflow_name,
                "parameters": parameters
            }
        )
        
        if response.status_code != 202:
            print(f"Error: {response.json()}")
            return None
        
        execution_id = response.json()["execution_id"]
        print(f"Submitted: {execution_id}")
        
        # Wait for completion
        while True:
            status_resp = await client.get(
                f"http://localhost:8000/workflows/status/{execution_id}"
            )
            status = status_resp.json()
            
            print(f"Status: {status['status']}", end="")
            if status.get("progress"):
                p = status["progress"]
                print(f" - {p['percent_complete']:.0f}%")
            else:
                print()
            
            if status["status"] in ["completed", "failed", "timeout"]:
                break
            
            await asyncio.sleep(2)
        
        # Get result
        result_resp = await client.get(
            f"http://localhost:8000/workflows/result/{execution_id}"
        )
        return result_resp.json()

# Run it
result = asyncio.run(execute_and_wait(
    "ajio_image",
    {"navigate_url": "https://www.ajio.com/product/12345"}
))
print(f"Result: {result}")
```

## 🆘 Troubleshooting

**API won't start:**
- Check MCP_SERVER_COMMAND is correct
- Ensure all dependencies are installed
- Check port 8000 is not in use

**Workflows fail:**
- Verify MCP server is accessible
- Check workflow parameters are correct
- Review logs for detailed errors

**Slow execution:**
- Increase SESSION_POOL_SIZE
- Check MAX_CONCURRENT_EXECUTIONS
- Monitor session pool statistics
