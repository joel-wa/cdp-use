#!/usr/bin/env python3
"""
MCP Session Pool

Manages pooling and lifecycle of MCP ClientSession connections for parallel
workflow execution.
"""

import asyncio
import logging
import time
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, List
from uuid import uuid4

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


@dataclass
class MCPSession:
    """Represents a single MCP client session"""
    session_id: str
    client_session: Optional[ClientSession] = None
    exit_stack: Optional[AsyncExitStack] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    reuse_count: int = 0
    is_active: bool = False
    current_workflow: Optional[str] = None
    
    def touch(self):
        """Update last_used timestamp"""
        self.last_used = datetime.now()
    
    def is_healthy(self) -> bool:
        """Check if session is healthy and usable"""
        return (
            self.client_session is not None and
            not self.is_active and
            self.reuse_count < 50  # Max reuse limit
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for status reporting"""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat(),
            "reuse_count": self.reuse_count,
            "is_active": self.is_active,
            "current_workflow": self.current_workflow,
            "age_seconds": (datetime.now() - self.created_at).total_seconds()
        }


class SessionPool:
    """
    Pool manager for MCP ClientSession connections.
    
    Provides efficient session reuse while managing lifecycle and resource limits.
    """
    
    def __init__(
        self,
        server_command: str,
        max_size: int = 15,
        idle_timeout: int = 300,
        max_reuse: int = 50
    ):
        """
        Initialize session pool.
        
        Args:
            server_command: Command to start MCP server (e.g., "python mcp_server.py")
            max_size: Maximum number of concurrent sessions
            idle_timeout: Seconds before idle session is cleaned up
            max_reuse: Maximum times a session can be reused
        """
        self.server_command = server_command
        self.max_size = max_size
        self.idle_timeout = idle_timeout
        self.max_reuse = max_reuse
        
        # Pool state
        self.available: asyncio.Queue[MCPSession] = asyncio.Queue()
        self.active: Dict[str, MCPSession] = {}
        self.all_sessions: Dict[str, MCPSession] = {}
        
        # Concurrency control
        self.semaphore = asyncio.Semaphore(max_size)
        self._lock = asyncio.Lock()
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Statistics
        self.stats = {
            "created": 0,
            "reused": 0,
            "destroyed": 0,
            "acquisitions": 0,
            "releases": 0
        }
        
        logger.info(f"SessionPool initialized: max_size={max_size}, idle_timeout={idle_timeout}s")
    
    async def start(self):
        """Start the session pool and cleanup task"""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("SessionPool started")
    
    async def stop(self):
        """Stop the session pool and cleanup all sessions"""
        logger.info("Stopping SessionPool...")
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Close all sessions
        async with self._lock:
            for session in list(self.all_sessions.values()):
                await self._destroy_session(session)
        
        logger.info("SessionPool stopped")
    
    async def acquire(self, workflow_name: Optional[str] = None) -> MCPSession:
        """
        Acquire a session from the pool.
        
        Args:
            workflow_name: Name of workflow using this session
            
        Returns:
            MCPSession ready for use
        """
        await self.semaphore.acquire()
        self.stats["acquisitions"] += 1
        
        session = None
        
        # Try to get existing healthy session from available pool
        while not self.available.empty():
            try:
                candidate = await asyncio.wait_for(self.available.get(), timeout=0.1)
                if candidate.is_healthy():
                    session = candidate
                    session.reuse_count += 1
                    self.stats["reused"] += 1
                    logger.debug(f"Reusing session {session.session_id} (reuse #{session.reuse_count})")
                    break
                else:
                    # Session not healthy, destroy it
                    await self._destroy_session(candidate)
            except asyncio.TimeoutError:
                break
        
        # Create new session if needed
        if session is None:
            session = await self._create_session()
            self.stats["created"] += 1
            logger.info(f"Created new session {session.session_id}")
        
        # Mark session as active
        async with self._lock:
            session.is_active = True
            session.current_workflow = workflow_name
            session.touch()
            self.active[session.session_id] = session
        
        return session
    
    async def release(self, session: MCPSession):
        """
        Release a session back to the pool.
        
        Args:
            session: Session to release
        """
        self.stats["releases"] += 1
        
        async with self._lock:
            session.is_active = False
            session.current_workflow = None
            session.touch()
            
            # Remove from active
            self.active.pop(session.session_id, None)
            
            # Return to available pool if healthy
            if session.is_healthy():
                await self.available.put(session)
                logger.debug(f"Released session {session.session_id} back to pool")
            else:
                # Destroy if not healthy
                await self._destroy_session(session)
                logger.debug(f"Destroyed unhealthy session {session.session_id}")
        
        self.semaphore.release()
    
    async def _create_session(self) -> MCPSession:
        """Create a new MCP client session"""
        import shlex
        
        session_id = f"session_{uuid4().hex[:8]}"
        
        try:
            # Parse command
            if isinstance(self.server_command, str):
                cmd_parts = shlex.split(self.server_command)
            else:
                cmd_parts = list(self.server_command)
            
            command = cmd_parts[0] if cmd_parts else "python"
            args = cmd_parts[1:] if len(cmd_parts) > 1 else []
            
            # Create server parameters
            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=None
            )
            
            # Create exit stack for cleanup
            exit_stack = AsyncExitStack()
            
            # Connect to MCP server
            stdio_transport = await exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            
            # Create client session
            client_session = await exit_stack.enter_async_context(
                ClientSession(stdio_transport[0], stdio_transport[1])
            )
            
            # Initialize session
            await client_session.initialize()
            
            # Create MCPSession wrapper
            mcp_session = MCPSession(
                session_id=session_id,
                client_session=client_session,
                exit_stack=exit_stack
            )
            
            # Track in all_sessions
            async with self._lock:
                self.all_sessions[session_id] = mcp_session
            
            logger.info(f"Created MCP session {session_id}")
            return mcp_session
            
        except Exception as e:
            logger.error(f"Failed to create MCP session: {e}")
            raise
    
    async def _destroy_session(self, session: MCPSession):
        """Destroy a session and cleanup resources"""
        try:
            if session.exit_stack:
                await session.exit_stack.aclose()
            
            async with self._lock:
                self.all_sessions.pop(session.session_id, None)
                self.active.pop(session.session_id, None)
            
            self.stats["destroyed"] += 1
            logger.debug(f"Destroyed session {session.session_id}")
            
        except Exception as e:
            logger.error(f"Error destroying session {session.session_id}: {e}")
    
    async def _cleanup_loop(self):
        """Background task to cleanup idle sessions"""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_idle_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _cleanup_idle_sessions(self):
        """Remove idle sessions that exceed timeout"""
        now = datetime.now()
        to_cleanup = []
        
        # Find idle sessions
        async with self._lock:
            for session in list(self.all_sessions.values()):
                if not session.is_active:
                    idle_seconds = (now - session.last_used).total_seconds()
                    if idle_seconds > self.idle_timeout:
                        to_cleanup.append(session)
        
        # Cleanup idle sessions
        for session in to_cleanup:
            logger.info(f"Cleaning up idle session {session.session_id}")
            await self._destroy_session(session)
    
    def get_status(self) -> dict:
        """Get current pool status"""
        return {
            "max_size": self.max_size,
            "total_sessions": len(self.all_sessions),
            "active": len(self.active),
            "available": self.available.qsize(),
            "idle_timeout": self.idle_timeout,
            "max_reuse": self.max_reuse,
            "statistics": self.stats.copy(),
            "active_sessions": [
                session.to_dict() 
                for session in self.active.values()
            ]
        }
