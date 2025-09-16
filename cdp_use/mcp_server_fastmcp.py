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
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from mcp.server import FastMCP
from cdp_use.client import CDPClient

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

class BrowserFastMCPServer:
    """FastMCP Server for browser control using CDP"""
    
    def __init__(self):
        self.server = FastMCP("CDP Browser Control Server")
        self.cdp_client = None
        self.selector_map: Dict[int, EnhancedDOMTreeNode] = {}
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
        
        @self.server.tool()
        async def get_interactive_elements(show_visual: bool = True, color: str = "rgba(255,0,0,0.25)") -> Dict[str, Any]:
            """Get a list of all interactive elements on the page and optionally show visual indicators.
            Use this tool when you need to interact and take some actions on a web page easily.
            
            Args:
                show_visual: Whether to show visual bounding boxes around elements (default: True)
                color: Color for the visual indicators (default: red with transparency)
            """
            try:
                if not self.cdp_client:
                    await self._connect_to_browser()
                
                # Update the selector map
                await self.update_selector_map()
                
                # Optionally show visual indicators
                if show_visual:
                    await self.show_bounding_boxes(color=color, label=True)
                
                # Format the results for return
                elements = []
                for idx, node in self.selector_map.items():
                    elements.append({
                        "index": node.element_index,
                        "tag": node.tag_name,
                        "text": node.text[:100] + "..." if len(node.text) > 100 else node.text,
                        "attributes": node.attributes,
                        "position": {
                            "x": node.absolute_position.x,
                            "y": node.absolute_position.y,
                            "width": node.absolute_position.width,
                            "height": node.absolute_position.height
                        },
                        "accessibility": {
                            "name": node.ax_node.name
                        }
                    })
                
                return {
                    "total_elements": len(elements),
                    "elements": elements,
                    "visual_indicators_shown": show_visual
                }
                
            except Exception as e:
                return {"error": f"Error getting interactive elements: {str(e)}"}
        
        @self.server.tool()
        async def click_element_by_index(element_index: int) -> str:
            """Click an element using its index from the interactive elements map
            
            Args:
                element_index: The index of the element to click (from get_interactive_elements)
            """
            try:
                if not self.cdp_client:
                    await self._connect_to_browser()
                
                # Make sure we have the latest selector map
                if not self.selector_map:
                    await self.update_selector_map()
                
                # Find the element
                if element_index not in self.selector_map:
                    return f"Element index {element_index} not found. Use get_interactive_elements to see available indices."
                
                node = self.selector_map[element_index]
                
                # Calculate center of the element for clicking
                x = node.absolute_position.x + (node.absolute_position.width / 2)
                y = node.absolute_position.y + (node.absolute_position.height / 2)
                
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
                
                return f"Successfully clicked element {element_index}: {node.tag_name} '{node.text[:50]}'"
                
            except Exception as e:
                return f"Error clicking element {element_index}: {str(e)}"
        
        @self.server.tool()
        async def hide_visual_indicators() -> str:
            """Hide the visual indicators (bounding boxes) from the page"""
            try:
                if not self.cdp_client:
                    await self._connect_to_browser()
                
                # JavaScript to remove the overlay
                js = r"""
                (() => {
                    const overlay = document.getElementById('__ps_overlay_v1');
                    if (overlay) {
                        overlay.remove();
                        return true;
                    }
                    return false;
                })()
                """
                
                result = await self.cdp_client.send.Runtime.evaluate({
                    'expression': js,
                    'returnByValue': True
                })
                
                if result.get('exceptionDetails'):
                    return f"Error hiding visual indicators: {result['exceptionDetails']['text']}"
                
                removed = result.get('result', {}).get('value', False)
                return "Visual indicators hidden" if removed else "No visual indicators found to hide"
                
            except Exception as e:
                return f"Error hiding visual indicators: {str(e)}"
    
    async def update_selector_map(self):
        """Evaluate a script in the page that finds interactive elements and builds selector_map."""
        if not self.cdp_client:
            await self._connect_to_browser()

        js = r"""
        (() => {
            // Collect potential interactive elements in document order
            const nodes = [];
            const walker = document.createTreeWalker(document, NodeFilter.SHOW_ELEMENT, null, false);
            let node;
            let idx = 1;
            const interactiveRoles = new Set(['button','link','menuitem','option','radio','checkbox','tab','textbox']);
            while (node = walker.nextNode()) {
                try {
                    const tag = node.tagName.toLowerCase();
                    const attrs = {};
                    for (let i=0;i<node.attributes.length;i++){
                        const a = node.attributes[i];
                        attrs[a.name] = a.value;
                    }
                    const rect = node.getBoundingClientRect ? node.getBoundingClientRect() : { x: 0, y: 0, width: 0, height: 0 };
                    const hasOnclick = node.getAttribute && (node.getAttribute('onclick') !== null || typeof node.onclick === 'function');
                    const role = node.getAttribute ? node.getAttribute('role') : null;
                    const ariaLabel = node.getAttribute ? (node.getAttribute('aria-label') || node.getAttribute('aria-labelledby') || null) : null;
                    const tabIndex = node.tabIndex || -1;
                    const isInteractiveTag = ['a','button','input','select','textarea'].includes(tag);
                    const maybeInteractive = isInteractiveTag || hasOnclick || tabIndex >= 0 || (role && interactiveRoles.has(role));
                    if (!maybeInteractive) continue;
                    const text = (node.innerText || '').trim().slice(0, 500);
                    nodes.push({
                        index: idx++,
                        tag,
                        attrs,
                        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                        role,
                        ariaLabel,
                        text
                    });
                } catch (e) {
                    // ignore node traversal errors
                }
            }
            return nodes;
        })()
        """

        result = await self.cdp_client.send.Runtime.evaluate({
            'expression': js,
            'returnByValue': True
        })
        
        if result.get('exceptionDetails'):
            raise Exception(f"Error evaluating selector map script: {result['exceptionDetails']['text']}")
        
        items = result.get('result', {}).get('value', [])
        
        # rebuild selector_map
        new_map: Dict[int, EnhancedDOMTreeNode] = {}
        for it in items:
            rect = it.get("rect") or {}
            domrect = DOMRect(x=rect.get("x", 0), y=rect.get("y", 0), width=rect.get("width", 0), height=rect.get("height", 0))
            ax = EnhancedAXNode(name=it.get("ariaLabel") or it.get("role") or None)
            node = EnhancedDOMTreeNode(
                element_index=int(it["index"]),
                tag_name=it.get("tag", ""),
                attributes=it.get("attrs", {}),
                absolute_position=domrect,
                ax_node=ax,
                text=it.get("text", ""),
            )
            new_map[node.element_index] = node

        # replace existing map atomically
        self.selector_map = new_map

    async def show_bounding_boxes(self, indices: Optional[List[int]] = None, color: str = "rgba(255,0,0,0.25)", label: bool = True):
        """
        Render bounding boxes for elements in selector_map.
        - indices: optional list of element_index values to render; if None, render all.
        - color: CSS color for the fill (use rgba for transparency).
        - label: show small label with index/tag.
        """
        if not self.cdp_client:
            await self._connect_to_browser()

        # build serializable list of rects from selector_map
        items = []
        for idx, node in self.selector_map.items():
            if indices and idx not in indices:
                continue
            if not node.absolute_position:
                continue
            r = node.absolute_position
            items.append({
                "index": idx,
                "x": r.x,
                "y": r.y,
                "width": r.width,
                "height": r.height,
                "tag": node.tag_name,
                "text": (node.text or "")[:80],
            })

        js = r"""
        (args) => {
            try {
                const items = args.items || [];
                const color = args.color || "rgba(255,0,0,0.25)";
                const doLabel = !!args.doLabel;
                const ID = "__ps_overlay_v1";
                let root = document.getElementById(ID);
                if (!root) {
                    root = document.createElement("div");
                    root.id = ID;
                    Object.assign(root.style, {
                        position: "fixed",
                        left: "0px",
                        top: "0px",
                        width: "100%",
                        height: "100%",
                        pointerEvents: "none",
                        zIndex: 2147483647, // very top
                    });
                    document.documentElement.appendChild(root);
                } else {
                    // clear previous boxes
                    root.innerHTML = "";
                }

                items.forEach(it => {
                    const box = document.createElement("div");
                    Object.assign(box.style, {
                        position: "fixed", // rect.x/y are viewport coordinates
                        left: (Math.round(it.x) + "px"),
                        top: (Math.round(it.y) + "px"),
                        width: Math.max(0, Math.round(it.width)) + "px",
                        height: Math.max(0, Math.round(it.height)) + "px",
                        background: color,
                        outline: "2px solid rgba(0,0,0,0.5)",
                        boxSizing: "border-box",
                        pointerEvents: "none",
                    });
                    box.dataset.psIndex = String(it.index);
                    root.appendChild(box);

                    if (doLabel) {
                        const lbl = document.createElement("div");
                        lbl.textContent = `${it.index} ${it.tag}`;
                        Object.assign(lbl.style, {
                            position: "absolute",
                            left: "0px",
                            top: "-18px",
                            fontSize: "12px",
                            lineHeight: "14px",
                            padding: "2px 6px",
                            background: "rgba(0,0,0,0.65)",
                            color: "#fff",
                            borderRadius: "3px",
                            pointerEvents: "none",
                            whiteSpace: "nowrap",
                        });
                        box.appendChild(lbl);
                    }
                });
                return true;
            } catch (e) {
                return false;
            }
        }
        """
        # Execute the JavaScript with arguments
        result = await self.cdp_client.send.Runtime.evaluate({
            'expression': f'({js})({{items: {json.dumps(items)}, color: {json.dumps(color)}, doLabel: {json.dumps(label)}}})',
            'returnByValue': True
        })
        
        if result.get('exceptionDetails'):
            raise Exception(f"Error showing bounding boxes: {result['exceptionDetails']['text']}")
        
        return result.get('result', {}).get('value', False)
    
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