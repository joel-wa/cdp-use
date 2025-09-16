#!/usr/bin/env python3
"""
MCP Server for Browser Control using Chrome DevTools Protocol (CDP) - FastMCP Version

This server provides browser automation capabilities for AI agents through the
Model Context Protocol (MCP). It uses the CDP to control Chrome/Chromium browsers.
Updated to use FastMCP for better compatibility.
"""

import asyncio
import json
import sys
import urllib.request
import urllib.error
from typing import Any, Dict, List

from mcp.server import FastMCP
from cdp_use.client import CDPClient

class BrowserFastMCPServer:
    """FastMCP Server for browser control using CDP"""
    
    def __init__(self):
        self.server = FastMCP("CDP Browser Control Server")
        self.cdp_client = None
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
                await asyncio.sleep(2)  # Wait for page to load
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
        async def get_page_content(selector: str = None, human_readable: bool = True) -> str:
            """Get the current page's content
            
            Args:
                selector: Optional CSS selector to get content of specific element
                human_readable: If True, returns only clean readable text visible to users (default: True)
            """
            try:
                if not self.cdp_client:
                    await self._connect_to_browser()
                
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
                                .replace(/[\u200f\u200b\ufeff\u202f\u200d\u00ad\u034f\u061c\u180e\u2000-\u200f\u2028-\u202f\u205f-\u206f\ufeff]/g, '') // Remove invisible Unicode characters
                                .replace(/͏/g, '')             // Remove invisible separator
                                .trim();                       // Trim the final result
                        })()
                    """
                else:
                    # Extract full content with structured data
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

                            return JSON.stringify({
                                title: document.title,
                                url: window.location.href,
                                text: mainContent ? mainContent.innerText : docClone.body.innerText,
                                html: mainContent ? mainContent.innerHTML : docClone.body.innerHTML
                            });
                        })()
                    """

                # Execute the JavaScript to get content
                result = await self.cdp_client.send.Runtime.evaluate({
                    'expression': expression,
                    'returnByValue': True
                })
                
                if result.get('exceptionDetails'):
                    return f"Error getting content: {result['exceptionDetails']['text']}"
                
                content = result.get('result', {}).get('value')
                
                if content is None and selector:
                    return f"Element not found with selector: {selector}"
                
                if human_readable or selector:
                    # Return the content directly
                    return content or "No content found"
                else:
                    # Return structured content (it's already JSON stringified)
                    return content or "No content found"
                
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
            try:
                with urllib.request.urlopen('http://localhost:9222/json', timeout=5) as response:
                    data = response.read().decode()
                    tabs = json.loads(data)
            except urllib.error.URLError as e:
                raise Exception(
                    "Chrome debugging not accessible on port 9222. "
                    "Please start Chrome with: chrome --remote-debugging-port=9222 --user-data-dir=C:\\temp\\chrome_debug"
                ) from e
            
            if not tabs:
                raise Exception("No tabs/pages found in Chrome. Please open a tab in Chrome.")
                
            ws_url = tabs[0]['webSocketDebuggerUrl']
            print(f"🔗 Connecting to Chrome at: {ws_url}", file=sys.stderr)
            
            self.cdp_client = CDPClient(ws_url)
            await self.cdp_client.start()
            
            # Enable required domains
            await self.cdp_client.send.Page.enable()
            await self.cdp_client.send.DOM.enable()  
            await self.cdp_client.send.Runtime.enable()
            
            print(f"✅ Browser connection established successfully", file=sys.stderr)
            
        except Exception as e:
            error_msg = f"Failed to connect to browser: {e}"
            print(error_msg, file=sys.stderr)
            raise Exception(error_msg) from e
    
    def run(self):
        """Run the FastMCP server"""
        print("[START] Starting CDP Browser Control FastMCP Server...", file=sys.stderr)
        print("[INFO] Waiting for MCP client connection via stdio...", file=sys.stderr)
        print("[INFO] Connect using an MCP client or press Ctrl+C to stop", file=sys.stderr)
        try:
            self.server.run()
        except KeyboardInterrupt:
            print("\n🛑 Server stopped by user", file=sys.stderr)
        except Exception as e:
            print(f"\n❌ Server error: {e}", file=sys.stderr)
            raise

def main():
    """Main entry point for backward compatibility"""
    server = BrowserFastMCPServer()
    server.run()

if __name__ == "__main__":
    main()