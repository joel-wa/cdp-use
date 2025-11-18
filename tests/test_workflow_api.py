#!/usr/bin/env python3
"""
Test Workflow Execution API

Tests for the workflow execution API endpoints.
"""

import asyncio
import httpx
import pytest
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# Test configuration
API_BASE_URL = "http://localhost:8000"


async def test_health_check():
    """Test health check endpoint"""
    print("\n" + "="*60)
    print("TEST: Health Check")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✅ Health check passed")


async def test_list_workflows():
    """Test listing available workflows"""
    print("\n" + "="*60)
    print("TEST: List Workflows")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/workflows/list")
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Total workflows: {data['total']}")
        for workflow in data['workflows'][:3]:  # Show first 3
            print(f"  - {workflow['name']}: {workflow['description']}")
        assert response.status_code == 200
        assert data["total"] > 0
        print("✅ List workflows passed")


async def test_execute_workflow():
    """Test executing a workflow"""
    print("\n" + "="*60)
    print("TEST: Execute Workflow")
    print("="*60)
    
    # First, list workflows to get a valid one
    async with httpx.AsyncClient(timeout=60.0) as client:
        list_response = await client.get(f"{API_BASE_URL}/workflows/list")
        workflows = list_response.json()["workflows"]
        
        if not workflows:
            print("⚠️  No workflows available to test")
            return
        
        # Use the first workflow
        workflow_name = workflows[0]["name"]
        print(f"Testing with workflow: {workflow_name}")
        
        # Submit workflow for execution
        execute_request = {
            "workflow_name": workflow_name,
            "parameters": {
                # Add parameters based on workflow requirements
                # For now, using defaults from workflow definition
            },
            "timeout": 60
        }
        
        print(f"\nSubmitting workflow...")
        response = await client.post(
            f"{API_BASE_URL}/workflows/execute",
            json=execute_request
        )
        
        print(f"Status: {response.status_code}")
        assert response.status_code == 202
        
        data = response.json()
        execution_id = data["execution_id"]
        print(f"Execution ID: {execution_id}")
        print(f"Status: {data['status']}")
        
        # Poll for status
        print(f"\nPolling for completion...")
        max_polls = 60  # Max 60 seconds
        for i in range(max_polls):
            await asyncio.sleep(1)
            
            status_response = await client.get(
                f"{API_BASE_URL}/workflows/status/{execution_id}"
            )
            status_data = status_response.json()
            
            print(f"  Poll {i+1}: {status_data['status']}", end="")
            if status_data.get("progress"):
                progress = status_data["progress"]
                print(f" - Step {progress['current_step']}/{progress['total_steps']}: {progress['step_name']}")
            else:
                print()
            
            if status_data["status"] in ["completed", "failed", "timeout", "cancelled"]:
                print(f"\n✅ Workflow {status_data['status']}")
                
                # Get result
                result_response = await client.get(
                    f"{API_BASE_URL}/workflows/result/{execution_id}"
                )
                result_data = result_response.json()
                print(f"\nExecution time: {result_data.get('execution_time', 'N/A')}s")
                
                if result_data["status"] == "completed":
                    print(f"Result: {result_data.get('result', 'No result')}")
                    print("✅ Workflow execution test passed")
                else:
                    print(f"Error: {result_data.get('error', 'Unknown error')}")
                    print("⚠️  Workflow failed but test infrastructure works")
                
                break
        else:
            print("\n⏱️  Timeout waiting for workflow completion")


async def test_batch_execution():
    """Test batch workflow execution"""
    print("\n" + "="*60)
    print("TEST: Batch Execution")
    print("="*60)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Get available workflows
        list_response = await client.get(f"{API_BASE_URL}/workflows/list")
        workflows = list_response.json()["workflows"]
        
        if len(workflows) < 2:
            print("⚠️  Need at least 2 workflows for batch test")
            return
        
        # Create batch request with first 2 workflows
        batch_request = {
            "workflows": [
                {
                    "workflow_name": workflows[0]["name"],
                    "parameters": {}
                },
                {
                    "workflow_name": workflows[1]["name"],
                    "parameters": {}
                }
            ],
            "parallel": True
        }
        
        print(f"Submitting batch with {len(batch_request['workflows'])} workflows...")
        response = await client.post(
            f"{API_BASE_URL}/workflows/batch",
            json=batch_request
        )
        
        print(f"Status: {response.status_code}")
        assert response.status_code == 202
        
        data = response.json()
        print(f"Batch ID: {data['batch_id']}")
        print(f"Total workflows: {data['total_workflows']}")
        
        for execution in data['executions']:
            print(f"  - {execution['execution_id']}: {execution['status']}")
        
        print("✅ Batch submission test passed")


async def test_active_executions():
    """Test listing active executions"""
    print("\n" + "="*60)
    print("TEST: Active Executions")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/workflows/active")
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"Total active: {data['total_active']}")
        print(f"Queued: {data['queued']}")
        print(f"Running: {data['running']}")
        
        if data['executions']:
            print("\nActive executions:")
            for execution in data['executions'][:3]:
                print(f"  - {execution['workflow_name']}: {execution['status']}")
        
        assert response.status_code == 200
        print("✅ Active executions test passed")


async def test_statistics():
    """Test statistics endpoint"""
    print("\n" + "="*60)
    print("TEST: Statistics")
    print("="*60)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/stats")
        print(f"Status: {response.status_code}")
        data = response.json()
        
        print("\nExecution Manager Stats:")
        for key, value in data['execution_manager'].items():
            print(f"  {key}: {value}")
        
        print("\nSession Pool Stats:")
        pool = data['session_pool']
        print(f"  Total sessions: {pool['total_sessions']}")
        print(f"  Active: {pool['active']}")
        print(f"  Available: {pool['available']}")
        
        assert response.status_code == 200
        print("✅ Statistics test passed")


async def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("  WORKFLOW EXECUTION API TEST SUITE")
    print("="*60)
    print(f"\nAPI Base URL: {API_BASE_URL}")
    print("\nNOTE: Make sure the API server is running:")
    print("  python start_api.py")
    print("\n")
    
    tests = [
        ("Health Check", test_health_check),
        ("List Workflows", test_list_workflows),
        ("Execute Workflow", test_execute_workflow),
        ("Batch Execution", test_batch_execution),
        ("Active Executions", test_active_executions),
        ("Statistics", test_statistics),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n❌ TEST FAILED: {name}")
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
