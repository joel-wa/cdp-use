#!/usr/bin/env python3
"""
Session and Tab Management for Multi-Tab Browser Control

This module provides session management capabilities for controlling multiple
browser tabs concurrently through the CDP (Chrome DevTools Protocol).
"""

import asyncio
import logging
import urllib.request
import urllib.error
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import uuid4

from cdp_use.client import CDPClient

logger = logging.getLogger(__name__)


@dataclass
class DOMRect:
    """Represents a DOM element's bounding rectangle"""
    x: float
    y: float
    width: float
    height: float


@dataclass
class EnhancedAXNode:
    """Represents accessibility information for a DOM element"""
    name: Optional[str] = None


@dataclass
class EnhancedDOMTreeNode:
    """Represents an enhanced DOM tree node with additional metadata"""
    element_index: int
    tag_name: str
    attributes: Dict[str, str]
    absolute_position: DOMRect
    ax_node: EnhancedAXNode
    text: str


@dataclass
class TabSession:
    """Represents a single browser tab session"""
    session_id: str
    target_id: str
    ws_url: str
    cdp_client: Optional[CDPClient] = None
    selector_map: Dict[int, EnhancedDOMTreeNode] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    current_url: str = "about:blank"
    is_connected: bool = False

    def touch(self):
        """Update last_used timestamp"""
        self.last_used = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for serialization"""
        return {
            "session_id": self.session_id,
            "target_id": self.target_id,
            "current_url": self.current_url,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat(),
            "is_connected": self.is_connected,
            "metadata": self.metadata,
            "selector_map_size": len(self.selector_map)
        }


class TabSessionManager:
    """Manages multiple browser tab sessions"""

    def __init__(self, max_sessions: int = 20, idle_timeout_seconds: int = 3600):
        self.sessions: Dict[str, TabSession] = {}
        self.default_session_id: Optional[str] = None
        self.max_sessions = max_sessions
        self.idle_timeout_seconds = idle_timeout_seconds
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the session manager and cleanup task"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Session manager started")

    async def stop(self):
        """Stop the session manager and cleanup all sessions"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Close all sessions
        async with self._lock:
            session_ids = list(self.sessions.keys())
            for session_id in session_ids:
                await self._close_session_internal(session_id)

        logger.info("Session manager stopped")

    async def _cleanup_loop(self):
        """Periodically cleanup idle sessions"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_idle_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_idle_sessions(self):
        """Remove sessions that have been idle for too long"""
        if self.idle_timeout_seconds <= 0:
            return

        async with self._lock:
            now = datetime.now()
            idle_sessions = []

            for session_id, session in self.sessions.items():
                idle_time = (now - session.last_used).total_seconds()
                if idle_time > self.idle_timeout_seconds and session_id != self.default_session_id:
                    idle_sessions.append(session_id)

            for session_id in idle_sessions:
                logger.info(f"Cleaning up idle session: {session_id}")
                await self._close_session_internal(session_id)

    async def create_session(self, url: str = "about:blank", metadata: Optional[Dict[str, Any]] = None) -> TabSession:
        """Create a new browser tab session
        
        Args:
            url: Initial URL to navigate to
            metadata: Optional metadata to attach to the session
            
        Returns:
            TabSession: The created session
            
        Raises:
            RuntimeError: If max sessions reached or tab creation fails
        """
        async with self._lock:
            if len(self.sessions) >= self.max_sessions:
                raise RuntimeError(f"Maximum number of sessions ({self.max_sessions}) reached")

            session_id = f"session-{uuid4().hex[:8]}"
            
            try:
                # First, get the browser WebSocket endpoint to create a new target
                with urllib.request.urlopen('http://localhost:9222/json/version', timeout=5) as response:
                    version_data = response.read().decode()
                    version_info = json.loads(version_data)
                    browser_ws_url = version_info['webSocketDebuggerUrl']

                # Connect to the browser endpoint temporarily to create a new tab
                from cdp_use.client import CDPClient
                browser_client = CDPClient(browser_ws_url)
                await browser_client.start()
                
                try:
                    # Create a new target (tab) using CDP
                    result = await browser_client.send.Target.createTarget({
                        'url': url if url else 'about:blank'
                    })
                    target_id = result['targetId']
                    logger.info(f"Created new browser tab with target ID: {target_id}")
                    
                    # Give Chrome a moment to initialize the new tab
                    await asyncio.sleep(0.5)
                    
                    # Get the WebSocket URL for the new target
                    with urllib.request.urlopen('http://localhost:9222/json', timeout=5) as response:
                        tabs_data = response.read().decode()
                        tabs = json.loads(tabs_data)
                    
                    # Find our newly created tab
                    tab_info = None
                    for tab in tabs:
                        if tab['id'] == target_id:
                            tab_info = tab
                            break
                    
                    if not tab_info:
                        raise RuntimeError(f"Could not find newly created tab with target ID: {target_id}")
                    
                    ws_url = tab_info['webSocketDebuggerUrl']
                    
                finally:
                    # Close the browser client connection
                    await browser_client.stop()

                session = TabSession(
                    session_id=session_id,
                    target_id=target_id,
                    ws_url=ws_url,
                    metadata=metadata or {},
                    current_url=url if url else 'about:blank'
                )

                # Connect to the tab
                await self._connect_session(session)

                self.sessions[session_id] = session

                # Set as default if it's the first session
                if self.default_session_id is None:
                    self.default_session_id = session_id
                    logger.info(f"Set default session: {session_id}")

                logger.info(f"Created session {session_id} with target {target_id}")
                return session

            except Exception as e:
                logger.error(f"Failed to create session: {e}")
                raise RuntimeError(f"Failed to create session: {e}") from e

    async def _connect_session(self, session: TabSession):
        """Connect a session to its CDP client"""
        try:
            session.cdp_client = CDPClient(session.ws_url)
            await session.cdp_client.start()

            # Enable required domains
            await session.cdp_client.send.Page.enable()
            await session.cdp_client.send.DOM.enable()
            await session.cdp_client.send.Runtime.enable()

            session.is_connected = True
            logger.info(f"Connected session {session.session_id} to {session.ws_url}")

        except Exception as e:
            logger.error(f"Failed to connect session {session.session_id}: {e}")
            session.is_connected = False
            raise

    async def get_session(self, session_id: str) -> TabSession:
        """Get a session by ID
        
        Args:
            session_id: The session ID to retrieve
            
        Returns:
            TabSession: The requested session
            
        Raises:
            KeyError: If session not found
        """
        async with self._lock:
            if session_id not in self.sessions:
                raise KeyError(f"Session not found: {session_id}")
            
            session = self.sessions[session_id]
            session.touch()
            return session

    async def get_or_create_default(self) -> TabSession:
        """Get the default session, creating it if necessary
        
        Returns:
            TabSession: The default session
        """
        async with self._lock:
            # If we have a default session, return it
            if self.default_session_id and self.default_session_id in self.sessions:
                session = self.sessions[self.default_session_id]
                session.touch()
                return session

        # Create a new default session (releases lock during creation)
        logger.info("Creating default session")
        return await self.create_session(url="about:blank", metadata={"is_default": True})

    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions
        
        Returns:
            List of session information dictionaries
        """
        async with self._lock:
            return [
                {
                    **session.to_dict(),
                    "is_default": session.session_id == self.default_session_id
                }
                for session in self.sessions.values()
            ]

    async def close_session(self, session_id: str) -> bool:
        """Close a specific session
        
        Args:
            session_id: The session ID to close
            
        Returns:
            bool: True if session was closed, False if not found
        """
        async with self._lock:
            return await self._close_session_internal(session_id)

    async def _close_session_internal(self, session_id: str) -> bool:
        """Internal method to close a session (must be called with lock held)"""
        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]

        # Close the Chrome tab using Target.closeTarget if possible
        if session.cdp_client and session.is_connected:
            try:
                # Try to close the target (tab) in Chrome
                try:
                    # Get browser endpoint to close the target
                    with urllib.request.urlopen('http://localhost:9222/json/version', timeout=2) as response:
                        version_data = response.read().decode()
                        version_info = json.loads(version_data)
                        browser_ws_url = version_info['webSocketDebuggerUrl']
                    
                    # Connect to browser to close the target
                    browser_client = CDPClient(browser_ws_url)
                    await browser_client.start()
                    try:
                        await browser_client.send.Target.closeTarget({'targetId': session.target_id})
                        logger.info(f"Closed Chrome tab for session {session_id}")
                    finally:
                        await browser_client.stop()
                except Exception as e:
                    logger.warning(f"Could not close Chrome tab for session {session_id}: {e}")
                
                # Close CDP connection
                await session.cdp_client.stop()
            except Exception as e:
                logger.error(f"Error closing CDP client for session {session_id}: {e}")

        # Remove from sessions
        del self.sessions[session_id]

        # Clear default if it was the default session
        if self.default_session_id == session_id:
            self.default_session_id = None
            logger.info(f"Cleared default session")

        logger.info(f"Closed session: {session_id}")
        return True

    async def set_default_session(self, session_id: str):
        """Set a session as the default
        
        Args:
            session_id: The session ID to set as default
            
        Raises:
            KeyError: If session not found
        """
        async with self._lock:
            if session_id not in self.sessions:
                raise KeyError(f"Session not found: {session_id}")
            
            self.default_session_id = session_id
            logger.info(f"Set default session: {session_id}")

    def get_session_count(self) -> int:
        """Get the number of active sessions"""
        return len(self.sessions)
