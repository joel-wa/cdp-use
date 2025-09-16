#!/usr/bin/env python3
"""
MCP Server for Browser Control using Chrome DevTools Protocol (CDP)

This server provides browser automation capabilities for AI agents through the
Model Context Protocol (MCP). It uses the CDP to control Chrome/Chromium browsers.
"""

import asyncio
import base64
import json
import logging
import sys
from typing import Any, Dict, List, Optional, Sequence

import httpx
from mcp.server import Server
from mcp.types import Resource, Tool, ServerCapabilities
from mcp.server.stdio import stdio_server
from mcp.server import InitializationOptions

from cdp_use.client import CDPClient

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class BrowserMCPServer:
    """MCP Server for browser control using CDP"""
    
    def __init__(self):
        self.server = Server("cdp-browser-control", version="1.0.0")
        self.cdp_client: Optional[CDPClient] = None
        self.session_id: Optional[str] = None
        self.browser_url = "http://localhost:9222"
        
        # Register tools and resources
        self._register_tools()
        self._register_resources()
    
    def _register_tools(self):
        """Register all browser control tools"""
        
        @self.server.call_tool()
        async def navigate(arguments: dict) -> list[dict]:
            """Navigate to a URL
            
            Args:
                url: The URL to navigate to
            """
            url = arguments.get("url")
            if not url:
                return [{"type": "text", "text": "Error: 'url' parameter is required"}]
            
            try:
                await self._ensure_connection()
                result = await self.cdp_client.send.Page.navigate(
                    params={"url": url}, session_id=self.session_id
                )
                return [{"type": "text", "text": f"Successfully navigated to {url}"}]
            except Exception as e:
                return [{"type": "text", "text": f"Error navigating to {url}: {str(e)}"}]
        
        @self.server.call_tool()
        async def click_element(arguments: dict) -> list[dict]:
            """Click an element using a CSS selector
            
            Args:
                selector: CSS selector for the element to click
                timeout: Optional timeout in seconds (default: 5)
            """
            selector = arguments.get("selector")
            timeout = arguments.get("timeout", 5)
            
            if not selector:
                return [{"type": "text", "text": "Error: 'selector' parameter is required"}]
            
            try:
                await self._ensure_connection()
                
                # Enable DOM domain
                await self.cdp_client.send.DOM.enable(session_id=self.session_id)
                
                # Get the document
                doc = await self.cdp_client.send.DOM.getDocument(
                    params={"depth": -1}, session_id=self.session_id
                )
                
                # Find the element using querySelector
                element = await self.cdp_client.send.DOM.querySelector(
                    params={"nodeId": doc["root"]["nodeId"], "selector": selector},
                    session_id=self.session_id
                )
                
                if element["nodeId"] == 0:
                    return [{"type": "text", "text": f"Error: Element not found with selector '{selector}'"}]
                
                # Get the box model to find click coordinates
                box_model = await self.cdp_client.send.DOM.getBoxModel(
                    params={"nodeId": element["nodeId"]}, session_id=self.session_id
                )
                
                # Calculate center of the element
                border = box_model["model"]["border"]
                x = (border[0] + border[4]) / 2
                y = (border[1] + border[5]) / 2
                
                # Enable Input domain and click
                await self.cdp_client.send.Input.dispatchMouseEvent(
                    params={
                        "type": "mousePressed",
                        "x": x,
                        "y": y,
                        "button": "left",
                        "clickCount": 1
                    },
                    session_id=self.session_id
                )
                
                await self.cdp_client.send.Input.dispatchMouseEvent(
                    params={
                        "type": "mouseReleased", 
                        "x": x,
                        "y": y,
                        "button": "left",
                        "clickCount": 1
                    },
                    session_id=self.session_id
                )
                
                return [{"type": "text", "text": f"Successfully clicked element with selector '{selector}'"}]
                
            except Exception as e:
                return [{"type": "text", "text": f"Error clicking element '{selector}': {str(e)}"}]
        
        @self.server.call_tool()
        async def type_text(arguments: dict) -> list[dict]:
            """Type text into the currently focused element
            
            Args:
                text: The text to type
            """
            text = arguments.get("text")
            if not text:
                return [{"type": "text", "text": "Error: 'text' parameter is required"}]
            
            try:
                await self._ensure_connection()
                
                # Type each character
                for char in text:
                    await self.cdp_client.send.Input.dispatchKeyEvent(
                        params={
                            "type": "char",
                            "text": char
                        },
                        session_id=self.session_id
                    )
                
                return [{"type": "text", "text": f"Successfully typed: {text}"}]
                
            except Exception as e:
                return [{"type": "text", "text": f"Error typing text: {str(e)}"}]
        
        @self.server.call_tool()
        async def take_screenshot(arguments: dict) -> list[dict]:
            """Take a screenshot of the current page
            
            Args:
                format: Image format ('png' or 'jpeg', default: 'png')
                quality: JPEG quality 0-100 (default: 90, only for JPEG)
                fullPage: Whether to capture the full page (default: False)
            """
            format_type = arguments.get("format", "png")
            quality = arguments.get("quality", 90)
            full_page = arguments.get("fullPage", False)
            
            try:
                await self._ensure_connection()
                
                params = {"format": format_type}
                if format_type == "jpeg":
                    params["quality"] = quality
                if full_page:
                    params["captureBeyondViewport"] = True
                
                result = await self.cdp_client.send.Page.captureScreenshot(
                    params=params, session_id=self.session_id
                )
                
                # Return the base64 image data
                return [{
                    "type": "image",
                    "data": result["data"],
                    "mimeType": f"image/{format_type}"
                }]
                
            except Exception as e:
                return [{"type": "text", "text": f"Error taking screenshot: {str(e)}"}]
        
        @self.server.call_tool()
        async def execute_javascript(arguments: dict) -> list[dict]:
            """Execute JavaScript code in the browser
            
            Args:
                expression: JavaScript code to execute
                returnByValue: Whether to return the result by value (default: True)
            """
            expression = arguments.get("expression")
            return_by_value = arguments.get("returnByValue", True)
            
            if not expression:
                return [{"type": "text", "text": "Error: 'expression' parameter is required"}]
            
            try:
                await self._ensure_connection()
                
                # Enable Runtime domain
                await self.cdp_client.send.Runtime.enable(session_id=self.session_id)
                
                result = await self.cdp_client.send.Runtime.evaluate(
                    params={
                        "expression": expression,
                        "returnByValue": return_by_value
                    },
                    session_id=self.session_id
                )
                
                if result.get("exceptionDetails"):
                    error_msg = result["exceptionDetails"].get("text", "JavaScript execution error")
                    return [{"type": "text", "text": f"JavaScript Error: {error_msg}"}]
                
                value = result.get("result", {}).get("value", "undefined")
                return [{"type": "text", "text": f"JavaScript Result: {json.dumps(value, indent=2)}"}]
                
            except Exception as e:
                return [{"type": "text", "text": f"Error executing JavaScript: {str(e)}"}]
        
        @self.server.call_tool()
        async def get_page_content(arguments: dict) -> list[dict]:
            """Get the HTML content of the current page
            
            Args:
                selector: Optional CSS selector to get content of specific element
                human_readable: If True, returns only clean readable text visible to users
            """
            selector = arguments.get("selector")
            human_readable = arguments.get("human_readable", False)
            
            try:
                await self._ensure_connection()
                
                # Enable Runtime domain
                await self.cdp_client.send.Runtime.enable(session_id=self.session_id)
                
                if selector:
                    # Get specific element content
                    expression = f"document.querySelector('{selector}') ? document.querySelector('{selector}').outerHTML : null"
                elif human_readable:
                    # Extract only pure human-readable content
                    expression = r"""
                        (() => {
                            // Function to get clean text from an element, handling cases like buttons, forms, etc.
                            function getCleanText(element) {
                                // Skip hidden elements
                                const style = window.getComputedStyle(element);
                                if (style.display === 'none' || style.visibility === 'hidden' ||
                                    style.opacity === '0' || element.offsetParent === null) {
                                    return '';
                                }

                                // Skip elements likely to be invisible or noise
                                if (element.getAttribute('aria-hidden') === 'true' ||
                                    element.getAttribute('role') === 'presentation' ||
                                    element.id === 'comment-section' ||
                                    (element.classList && element.classList.contains && (element.classList.contains('ad') ||
                                    element.classList.contains('menu') ||
                                    element.classList.contains('cookie') ||
                                    element.classList.contains('navigation')))) {
                                    return '';
                                }

                                // Get direct text from this element (excluding child element text)
                                let text = '';
                                for (const node of element.childNodes) {
                                    if (node.nodeType === Node.TEXT_NODE) {
                                        text += node.textContent;
                                    }
                                }

                                // Trim the direct text
                                text = text.trim();

                                // Determine if this is a heading element to add structure
                                const nodeName = element.nodeName.toLowerCase();
                                if (/^h[1-6]$/.test(nodeName)) {
                                    if (text) {
                                        const level = parseInt(nodeName.charAt(1));
                                        return '\\n' + '#'.repeat(level) + ' ' + text + '\\n';
                                    }
                                }

                                return text;
                            }

                            // Walk the DOM, skipping unwanted elements
                            function walkDOM(root, result = '') {
                                // Skip script, style, noscript, etc.
                                const skipTags = ['script', 'style', 'noscript', 'template', 'iframe'];
                                if (skipTags.includes(root.nodeName.toLowerCase())) {
                                    return result;
                                }

                                // Skip elements typically used for navigation, ads, popups
                                const skipRoles = ['navigation', 'banner', 'complementary', 'contentinfo'];
                                if (skipRoles.includes(root.getAttribute('role'))) {
                                    return result;
                                }

                                // Skip common non-content elements
                                const skipClasses = ['header', 'footer', 'sidebar', 'nav', 'menu', 'ad', 'popup', 'modal', 'cookie'];
                                for (const cls of skipClasses) {
                                    if (root.className && typeof root.className === 'string' &&
                                        (root.className.includes(cls) || (root.id && root.id.includes && root.id.includes(cls)))) {
                                        return result;
                                    }
                                }

                                // Get the element's own text content (not including children)
                                const directText = getCleanText(root);
                                if (directText) {
                                    result += directText + ' ';
                                }

                                // Recursively process child elements
                                for (const child of root.children) {
                                    result = walkDOM(child, result);

                                    // Add separators between block elements
                                    const childName = child.nodeName.toLowerCase();
                                    if (['div', 'p', 'section', 'article', 'header', 'li', 'tr'].includes(childName)) {
                                        result += '\\n';
                                    }
                                }

                                return result;
                            }

                            // Start with the main content element if possible
                            const mainContent = document.querySelector('main') ||
                                                document.querySelector('article') ||
                                                document.querySelector('#content') ||
                                                document.querySelector('.content') ||
                                                document.body;

                            // Get page title
                            let result = '';
                            const title = document.querySelector('h1') || document.querySelector('h2');
                            if (title && title.textContent.trim()) {
                                result += title.textContent.trim() + '\\n\\n';
                            } else if (document.title) {
                                result += document.title + '\\n\\n';
                            }

                            // Walk the DOM to get clean text
                            result += walkDOM(mainContent);

                            // Clean up the text
                            return result
                                .replace(/\\s+/g, ' ')         // Collapse whitespace
                                .replace(/\\n\\s+/g, '\\n')    // Remove leading space after newlines
                                .replace(/\\n{3,}/g, '\\n\\n') // Replace multiple newlines
                                .replace(/\\s+$/gm, '')        // Remove trailing space from each line
                                .trim();                       // Trim the final result
                        })()
                    """
                else:
                    # Extract full content with structured data (original enhanced behavior)
                    expression = r"""
                        (() => {
                            // Remove unwanted elements that might contain noise
                            const elementsToRemove = [
                                'header', 'footer', 'nav', 'aside',
                                '.ads', '.advertisement', '.cookie-notice',
                                '.popup', '.modal', '.newsletter'
                            ];

                            // Create a copy to avoid modifying the actual DOM
                            const docClone = document.cloneNode(true);

                            elementsToRemove.forEach(selector => {
                                docClone.querySelectorAll(selector).forEach(el => {
                                    if (el) el.remove();
                                });
                            });

                            // Get the main content
                            const mainContent = docClone.querySelector('main') ||
                                               docClone.querySelector('article') ||
                                               docClone.querySelector('.content') ||
                                               docClone.body;

                            return {
                                title: document.title,
                                url: window.location.href,
                                text: mainContent ? mainContent.innerText : docClone.body.innerText,
                                html: mainContent ? mainContent.innerHTML : docClone.body.innerHTML
                            };
                        })()
                    """
                
                result = await self.cdp_client.send.Runtime.evaluate(
                    params={
                        "expression": expression,
                        "returnByValue": True
                    },
                    session_id=self.session_id
                )
                
                if result.get("exceptionDetails"):
                    error_msg = result["exceptionDetails"].get("text", "Error getting content")
                    return [{"type": "text", "text": f"Error: {error_msg}"}]
                
                content = result.get("result", {}).get("value")
                
                if content is None and selector:
                    return [{"type": "text", "text": f"Element not found with selector: {selector}"}]
                
                if human_readable:
                    # Return just the clean readable text
                    return [{"type": "text", "text": content or "No readable content found"}]
                elif selector:
                    # Return the specific element content
                    return [{"type": "text", "text": content or "No content found"}]
                else:
                    # Return structured content as JSON
                    if isinstance(content, dict):
                        return [{"type": "text", "text": json.dumps(content, indent=2)}]
                    else:
                        return [{"type": "text", "text": content or "No content found"}]
                
            except Exception as e:
                return [{"type": "text", "text": f"Error getting page content: {str(e)}"}]
        
        @self.server.call_tool()
        async def wait_for_element(arguments: dict) -> list[dict]:
            """Wait for an element to appear on the page
            
            Args:
                selector: CSS selector for the element to wait for
                timeout: Timeout in seconds (default: 10)
            """
            selector = arguments.get("selector")
            timeout = arguments.get("timeout", 10)
            
            if not selector:
                return [{"type": "text", "text": "Error: 'selector' parameter is required"}]
            
            try:
                await self._ensure_connection()
                
                # Enable Runtime domain
                await self.cdp_client.send.Runtime.enable(session_id=self.session_id)
                
                # Wait for element with polling
                expression = f"""
                new Promise((resolve, reject) => {{
                    const startTime = Date.now();
                    const poll = () => {{
                        const element = document.querySelector('{selector}');
                        if (element) {{
                            resolve(true);
                        }} else if (Date.now() - startTime > {timeout * 1000}) {{
                            reject(new Error('Timeout waiting for element'));
                        }} else {{
                            setTimeout(poll, 100);
                        }}
                    }};
                    poll();
                }})
                """
                
                result = await self.cdp_client.send.Runtime.evaluate(
                    params={
                        "expression": expression,
                        "awaitPromise": True,
                        "returnByValue": True
                    },
                    session_id=self.session_id
                )
                
                if result.get("exceptionDetails"):
                    error_msg = result["exceptionDetails"].get("text", "Timeout or error")
                    return [{"type": "text", "text": f"Error waiting for element: {error_msg}"}]
                
                return [{"type": "text", "text": f"Element '{selector}' is now available"}]
                
            except Exception as e:
                return [{"type": "text", "text": f"Error waiting for element: {str(e)}"}]
    
    def _register_resources(self):
        """Register browser state resources"""
        
        @self.server.list_resources()
        async def list_resources() -> list[Resource]:
            """List available browser resources"""
            return [
                Resource(
                    uri="browser://current-page",
                    name="Current Page Info",
                    description="Information about the currently loaded page",
                    mimeType="application/json"
                ),
                Resource(
                    uri="browser://page-source",
                    name="Page HTML Source",
                    description="Full HTML source of the current page", 
                    mimeType="text/html"
                )
            ]
        
        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read browser resource data"""
            try:
                await self._ensure_connection()
                
                if uri == "browser://current-page":
                    # Get current page info
                    await self.cdp_client.send.Runtime.enable(session_id=self.session_id)
                    
                    url_result = await self.cdp_client.send.Runtime.evaluate(
                        params={"expression": "window.location.href", "returnByValue": True},
                        session_id=self.session_id
                    )
                    
                    title_result = await self.cdp_client.send.Runtime.evaluate(
                        params={"expression": "document.title", "returnByValue": True},
                        session_id=self.session_id
                    )
                    
                    info = {
                        "url": url_result.get("result", {}).get("value", "unknown"),
                        "title": title_result.get("result", {}).get("value", "unknown"),
                        "session_id": self.session_id
                    }
                    return json.dumps(info, indent=2)
                
                elif uri == "browser://page-source":
                    # Get page HTML source
                    await self.cdp_client.send.Runtime.enable(session_id=self.session_id)
                    
                    result = await self.cdp_client.send.Runtime.evaluate(
                        params={"expression": "document.documentElement.outerHTML", "returnByValue": True},
                        session_id=self.session_id
                    )
                    
                    return result.get("result", {}).get("value", "No content available")
                
                else:
                    return f"Unknown resource: {uri}"
                    
            except Exception as e:
                return f"Error reading resource {uri}: {str(e)}"
    
    async def _ensure_connection(self):
        """Ensure we have an active CDP connection"""
        if self.cdp_client is None:
            await self._connect_to_browser()
    
    async def _connect_to_browser(self):
        """Connect to Chrome browser via CDP"""
        try:
            # Get browser WebSocket URL
            async with httpx.AsyncClient() as client:
                version_info = await client.get(f"{self.browser_url}/json/version")
                browser_ws_url = version_info.json()["webSocketDebuggerUrl"]
            
            # Connect to CDP
            self.cdp_client = CDPClient(browser_ws_url)
            await self.cdp_client.start()
            
            # Get available targets
            targets = await self.cdp_client.send.Target.getTargets()
            page_targets = [t for t in targets["targetInfos"] if t["type"] == "page"]
            
            if not page_targets:
                # Create a new page if none exists
                new_target = await self.cdp_client.send.Target.createTarget(
                    params={"url": "about:blank"}
                )
                target_id = new_target["targetId"]
            else:
                target_id = page_targets[0]["targetId"]
            
            # Attach to the target
            attach_result = await self.cdp_client.send.Target.attachToTarget(
                params={"targetId": target_id, "flatten": True}
            )
            self.session_id = attach_result["sessionId"]
            
            print(f"Connected to browser, session ID: {self.session_id}", file=sys.stderr)
            
        except Exception as e:
            logger.error(f"Failed to connect to browser: {e}")
            raise

    async def serve(self):
        """Start the MCP server"""
        async with stdio_server() as streams:
            # Create initialization options
            init_options = InitializationOptions(
                server_name="CDP Browser Control Server",
                server_version="1.0.0", 
                capabilities=self.server.get_capabilities()
            )
            await self.server.run(streams[0], streams[1], init_options)

# Tool definitions for the MCP server
TOOLS = [
    Tool(
        name="navigate",
        description="Navigate to a URL",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to navigate to"
                }
            },
            "required": ["url"]
        }
    ),
    Tool(
        name="click_element", 
        description="Click an element using a CSS selector",
        inputSchema={
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector for the element to click"
                },
                "timeout": {
                    "type": "number",
                    "description": "Optional timeout in seconds (default: 5)"
                }
            },
            "required": ["selector"]
        }
    ),
    Tool(
        name="type_text",
        description="Type text into the currently focused element", 
        inputSchema={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to type"
                }
            },
            "required": ["text"]
        }
    ),
    Tool(
        name="take_screenshot",
        description="Take a screenshot of the current page",
        inputSchema={
            "type": "object", 
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["png", "jpeg"],
                    "description": "Image format (default: 'png')"
                },
                "quality": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "JPEG quality 0-100 (default: 90, only for JPEG)"
                },
                "fullPage": {
                    "type": "boolean",
                    "description": "Whether to capture the full page (default: False)"
                }
            }
        }
    ),
    Tool(
        name="execute_javascript",
        description="Execute JavaScript code in the browser",
        inputSchema={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string", 
                    "description": "JavaScript code to execute"
                },
                "returnByValue": {
                    "type": "boolean",
                    "description": "Whether to return the result by value (default: True)"
                }
            },
            "required": ["expression"]
        }
    ),
    Tool(
        name="get_page_content",
        description="Get the HTML content of the current page",
        inputSchema={
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "Optional CSS selector to get content of specific element"
                },
                "human_readable": {
                    "type": "boolean",
                    "description": "If True, returns only clean readable text visible to users (default: False)"
                }
            }
        }
    ),
    Tool(
        name="wait_for_element",
        description="Wait for an element to appear on the page",
        inputSchema={
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector for the element to wait for"
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (default: 10)"
                }
            },
            "required": ["selector"]
        }
    )
]

async def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] == "--list-tools":
        # List available tools
        for tool in TOOLS:
            print(f"Tool: {tool.name}")
            print(f"Description: {tool.description}")
            print(f"Input Schema: {json.dumps(tool.inputSchema, indent=2)}")
            print("-" * 50)
        return
    
    server = BrowserMCPServer()
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())