#!/usr/bin/env python3

import asyncio
import json
import sys
import base64
import os
import urllib.request
from typing import Any, Dict, List
from urllib.parse import urlparse

from mcp.server import FastMCP
from cdp_use.client import CDPClient

class BrowserFastMCP:
    """FastMCP-based browser automation server"""
    
    def __init__(self):
        self.server = FastMCP("CDP Browser Control Server")
        self.cdp_client = None
        self.session_id = None
        self._setup_tools()
    
    def _setup_tools(self):
        """Setup all browser automation tools"""
        
        @self.server.tool()
        async def navigate(url: str) -> str:
            """Navigate to a URL
            
            Args:
                url: The URL to navigate to
            """
            try:
                if not self.cdp_client:
                    await self._connect_to_browser()
                
                await self.cdp_client.send.Page.navigate({'url': url})
                # Wait a moment for page to load
                await asyncio.sleep(2)
                return f"Successfully navigated to {url}"
                
            except Exception as e:
                return f"Error navigating to {url}: {str(e)}"
        
        @self.server.tool()
        async def click_element(selector: str) -> str:
            """Click an element using a CSS selector
            
            Args:
                selector: CSS selector for the element to click
            """
            try:
                if not self.cdp_client:
                    await self._connect_to_browser()
                
                # Get the document
                doc_result = await self.cdp_client.send.DOM.getDocument()
                root_node_id = doc_result['root']['nodeId']
                
                # Find the element
                node_result = await self.cdp_client.send.DOM.querySelector({
                    'nodeId': root_node_id,
                    'selector': selector
                })
                
                if node_result['nodeId'] == 0:
                    return f"Element not found: {selector}"
                
                # Get the element's position for clicking
                box_result = await self.cdp_client.send.DOM.getBoxModel({
                    'nodeId': node_result['nodeId']
                })
                
                # Calculate center of the element
                content = box_result['model']['content']
                x = (content[0] + content[4]) / 2
                y = (content[1] + content[5]) / 2
                
                # Click the element
                await self.cdp_client.send.Input.dispatchMouseEvent({
                    'type': 'mousePressed',
                    'x': x,
                    'y': y,
                    'button': 'left',
                    'clickCount': 1
                })
                
                await self.cdp_client.send.Input.dispatchMouseEvent({
                    'type': 'mouseReleased',
                    'x': x,
                    'y': y,
                    'button': 'left',
                    'clickCount': 1
                })
                
                return f"Successfully clicked element: {selector}"
                
            except Exception as e:
                return f"Error clicking element {selector}: {str(e)}"
        
        @self.server.tool()
        async def type_text(text: str, selector: str = None) -> str:
            """Type text into an element or the current focus
            
            Args:
                text: Text to type
                selector: Optional CSS selector for the element to focus first
            """
            try:
                if not self.cdp_client:
                    await self._connect_to_browser()
                
                # If selector provided, click the element first to focus it
                if selector:
                    click_result = await click_element(selector)
                    if "Error" in click_result:
                        return click_result
                
                # Type each character
                for char in text:
                    await self.cdp_client.send.Input.dispatchKeyEvent({
                        'type': 'char',
                        'text': char
                    })
                
                return f"Successfully typed text: {text}"
                
            except Exception as e:
                return f"Error typing text: {str(e)}"
        
        @self.server.tool()
        async def take_screenshot(format_type: str = "png", quality: int = 90) -> Dict[str, Any]:
            """Take a screenshot of the current page
            
            Args:
                format_type: Image format (png or jpeg)
                quality: Image quality for JPEG (1-100)
            """
            try:
                if not self.cdp_client:
                    await self._connect_to_browser()
                
                params = {'format': format_type}
                if format_type == 'jpeg':
                    params['quality'] = quality
                
                result = await self.cdp_client.send.Page.captureScreenshot(params)
                
                return {
                    "type": "image",
                    "data": result["data"],
                    "mimeType": f"image/{format_type}"
                }
                
            except Exception as e:
                return {"error": f"Error taking screenshot: {str(e)}"}
        
        @self.server.tool()
        async def execute_javascript(expression: str, returnByValue: bool = True) -> Any:
            """Execute JavaScript code in the browser
            
            Args:
                expression: JavaScript code to execute
                returnByValue: Whether to return the result by value
            """
            try:
                if not self.cdp_client:
                    await self._connect_to_browser()
                
                result = await self.cdp_client.send.Runtime.evaluate({
                    'expression': expression,
                    'returnByValue': returnByValue
                })
                
                if result.get('exceptionDetails'):
                    return f"JavaScript Error: {result['exceptionDetails']['text']}"
                
                return result.get('result', {}).get('value', 'No return value')
                
            except Exception as e:
                return f"Error executing JavaScript: {str(e)}"
        
        @self.server.tool()
        async def get_page_content() -> str:
            """Get the current page's HTML content"""
            try:
                if not self.cdp_client:
                    await self._connect_to_browser()
                
                # Get the document
                doc_result = await self.cdp_client.send.DOM.getDocument()
                
                # Get outer HTML of the document
                html_result = await self.cdp_client.send.DOM.getOuterHTML({
                    'nodeId': doc_result['root']['nodeId']
                })
                
                return html_result['outerHTML']
                
            except Exception as e:
                return f"Error getting page content: {str(e)}"
        
        @self.server.tool()
        async def wait_for_element(selector: str, timeout: int = 10000) -> str:
            """Wait for an element to appear on the page
            
            Args:
                selector: CSS selector for the element to wait for
                timeout: Timeout in milliseconds
            """
            try:
                if not self.cdp_client:
                    await self._connect_to_browser()
                
                # Use Runtime.evaluate to wait for element with timeout
                wait_script = f"""
                new Promise((resolve, reject) => {{
                    const timeout = setTimeout(() => {{
                        reject(new Error('Timeout waiting for element: {selector}'));
                    }}, {timeout});
                    
                    const checkElement = () => {{
                        const element = document.querySelector('{selector}');
                        if (element) {{
                            clearTimeout(timeout);
                            resolve('Element found');
                        }} else {{
                            setTimeout(checkElement, 100);
                        }}
                    }};
                    checkElement();
                }})
                """
                
                result = await self.cdp_client.send.Runtime.evaluate({
                    'expression': wait_script,
                    'returnByValue': True,
                    'awaitPromise': True
                })
                
                if result.get('exceptionDetails'):
                    return f"Timeout waiting for element: {selector}"
                
                return f"Element found: {selector}"
                
            except Exception as e:
                return f"Error waiting for element {selector}: {str(e)}"
    
    async def _connect_to_browser(self):
        """Connect to Chrome browser"""
        if self.cdp_client:
            return
            
        try:
            # Get the WebSocket URL from Chrome debugging port
            import urllib.request
            with urllib.request.urlopen('http://localhost:9222/json') as response:
                data = response.read().decode()
                tabs = json.loads(data)
                if not tabs:
                    raise Exception("No tabs/pages found in Chrome")
                
                ws_url = tabs[0]['webSocketDebuggerUrl']
                print(f"Connecting to Chrome at: {ws_url}", file=sys.stderr)
            
            self.cdp_client = CDPClient(ws_url)
            await self.cdp_client.start()
            
            # Enable required domains
            await self.cdp_client.send.Page.enable()
            await self.cdp_client.send.DOM.enable()  
            await self.cdp_client.send.Runtime.enable()
            
            print(f"Connected to browser successfully", file=sys.stderr)
            
        except Exception as e:
            print(f"Failed to connect to browser: {e}", file=sys.stderr)
            raise
    
    def run(self):
        """Run the FastMCP server"""
        self.server.run()

def main():
    """Main entry point"""
    if len(sys.argv) > 1 and sys.argv[1] == "--server-only":
        # Server-only mode for testing
        pass
    elif len(sys.argv) > 1 and sys.argv[1] == "--list-tools":
        # List available tools (placeholder - FastMCP handles this)
        print("Use FastMCP introspection", file=sys.stderr)
        return
    
    print("🚀 Starting CDP Browser Control FastMCP Server...", file=sys.stderr)
    server = BrowserFastMCP()
    server.run()

if __name__ == "__main__":
    main()