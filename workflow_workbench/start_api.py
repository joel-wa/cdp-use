#!/usr/bin/env python3
"""
Workflow Execution API Startup Script

Launches the FastAPI server for asynchronous workflow execution.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from config import API_HOST, API_PORT, API_WORKERS, DEBUG

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Start the API server"""
    logger.info("=" * 60)
    logger.info("  WORKFLOW EXECUTION API")
    logger.info("=" * 60)
    logger.info(f"Host: {API_HOST}")
    logger.info(f"Port: {API_PORT}")
    logger.info(f"Workers: {API_WORKERS}")
    logger.info(f"Debug: {DEBUG}")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Starting server...")
    logger.info(f"API Documentation: http://{API_HOST}:{API_PORT}/docs")
    logger.info(f"Health Check: http://{API_HOST}:{API_PORT}/health")
    logger.info("")
    
    try:
        # Run uvicorn server
        uvicorn.run(
            "api.workflow_api:app",
            host=API_HOST,
            port=API_PORT,
            workers=API_WORKERS,
            reload=DEBUG,
            log_level="debug" if DEBUG else "info"
        )
    except KeyboardInterrupt:
        logger.info("\n\nShutdown requested by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
