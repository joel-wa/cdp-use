#!/usr/bin/env python3
"""
Browser automation tools for the FastMCP server.

This module contains all the browser control tools that were previously
embedded in the main server class. Separating them makes the code more
maintainable and easier to test.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from cdp_use.client import CDPClient


class BrowserTools:
    """Collection of browser automation tools for FastMCP server"""
    
    def __init__(self, cdp_client_ref, selector_map_ref):
        """Initialize with references to the main server's CDP client and selector map"""
        self.get_cdp_client = cdp_client_ref
        self.get_selector_map = selector_map_ref
        
    async def navigate(self, url: str) -> str:
        """Navigate to a URL
        
        Args:
            url: The URL to navigate to
        """
        try:
            cdp_client = await self.get_cdp_client()
            
            await cdp_client.send.Page.navigate({'url': url})
            await asyncio.sleep(2)  # Wait for page to load
            return f"Successfully navigated to {url}"
            
        except Exception as e:
            return f"Error navigating to {url}: {str(e)}"
    
    async def click_element(self, selector: str) -> str:
        """Click an element using a CSS selector
        
        Args:
            selector: CSS selector for the element to click
        """
        try:
            cdp_client = await self.get_cdp_client()
            
            # Get the document
            doc_result = await cdp_client.send.DOM.getDocument()
            root_node_id = doc_result['root']['nodeId']
            
            # Find the element
            node_result = await cdp_client.send.DOM.querySelector({
                'nodeId': root_node_id,
                'selector': selector
            })
            
            if node_result['nodeId'] == 0:
                return f"Element not found: {selector}"
            
            # Get the element's position for clicking
            box_result = await cdp_client.send.DOM.getBoxModel({
                'nodeId': node_result['nodeId']
            })
            
            # Calculate center of the element
            content = box_result['model']['content']
            x = (content[0] + content[4]) / 2
            y = (content[1] + content[5]) / 2
            
            # Click the element
            await cdp_client.send.Input.dispatchMouseEvent({
                'type': 'mousePressed',
                'x': x,
                'y': y,
                'button': 'left',
                'clickCount': 1
            })
            
            await cdp_client.send.Input.dispatchMouseEvent({
                'type': 'mouseReleased',
                'x': x,
                'y': y,
                'button': 'left',
                'clickCount': 1
            })
            
            return f"Successfully clicked element: {selector}"
            
        except Exception as e:
            return f"Error clicking element {selector}: {str(e)}"
    
    async def type_text(self, text: str, selector: str = None) -> str:
        """Type text into an element or the current focus
        
        Args:
            text: Text to type
            selector: Optional CSS selector for the element to focus first
        """
        try:
            cdp_client = await self.server._get_cdp_client()
            
            # If selector provided, click the element first to focus it
            if selector:
                click_result = await self.click_element(selector)
                if "Error" in click_result:
                    return click_result
            
            # Type each character
            for char in text:
                await cdp_client.send.Input.dispatchKeyEvent({
                    'type': 'char',
                    'text': char
                })
            
            return f"Successfully typed text: {text}"
            
        except Exception as e:
            return f"Error typing text: {str(e)}"
    
    async def take_screenshot(self, format_type: str = "png", quality: int = 90) -> Dict[str, Any]:
        """Take a screenshot of the current page
        
        Args:
            format_type: Image format (png or jpeg)
            quality: Image quality for JPEG (1-100)
        """
        try:
            cdp_client = await self.server._get_cdp_client()
            
            params = {'format': format_type}
            if format_type == 'jpeg':
                params['quality'] = quality
            
            result = await cdp_client.send.Page.captureScreenshot(params)
            
            return {
                "type": "image",
                "data": result["data"],
                "mimeType": f"image/{format_type}"
            }
            
        except Exception as e:
            return {"error": f"Error taking screenshot: {str(e)}"}
    
    async def execute_javascript(self, expression: str, returnByValue: bool = True) -> Any:
        """Execute JavaScript code in the browser
        
        Args:
            expression: JavaScript code to execute
            returnByValue: Whether to return the result by value
        """
        try:
            cdp_client = await self.server._get_cdp_client()
            
            result = await cdp_client.send.Runtime.evaluate({
                'expression': expression,
                'returnByValue': returnByValue
            })
            
            if result.get('exceptionDetails'):
                return f"JavaScript Error: {result['exceptionDetails']['text']}"
            
            return result.get('result', {}).get('value', 'No return value')
            
        except Exception as e:
            return f"Error executing JavaScript: {str(e)}"
    
    async def get_page_content(self, selector: str = None, human_readable: bool = True) -> str:
        """Get the current page's content
        
        Args:
            selector: Optional CSS selector to get content of specific element
            human_readable: If True, returns only clean readable text visible to users (default: True)
        """
        try:
            cdp_client = await self.server._get_cdp_client()
            
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
            result = await cdp_client.send.Runtime.evaluate({
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
    
    async def wait_for_element(self, selector: str, timeout: int = 10000) -> str:
        """Wait for an element to appear on the page
        
        Args:
            selector: CSS selector for the element to wait for
            timeout: Timeout in milliseconds
        """
        try:
            cdp_client = await self.server._get_cdp_client()
            
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
            
            result = await cdp_client.send.Runtime.evaluate({
                'expression': wait_script,
                'returnByValue': True,
                'awaitPromise': True
            })
            
            if result.get('exceptionDetails'):
                return f"Timeout waiting for element: {selector}"
            
            return f"Element found: {selector}"
            
        except Exception as e:
            return f"Error waiting for element {selector}: {str(e)}"
    
    async def get_interactive_elements(self, show_visual: bool = True, color: str = "rgba(255,0,0,0.25)", 
                                     update_selector_map_func=None, show_bounding_boxes_func=None) -> Dict[str, Any]:
        """Get a list of all interactive elements on the page and optionally show visual indicators.
        Use this tool when you need to interact and take some actions on a web page easily.
        
        Args:
            show_visual: Whether to show visual bounding boxes around elements (default: True)
            color: Color for the visual indicators (default: red with transparency)
            update_selector_map_func: Function to update the selector map
            show_bounding_boxes_func: Function to show bounding boxes
        """
        try:
            cdp_client = await self.server._get_cdp_client()
            
            # Update the selector map
            if update_selector_map_func:
                await update_selector_map_func()
            
            # Optionally show visual indicators
            if show_visual and show_bounding_boxes_func:
                await show_bounding_boxes_func(color=color, label=True)
            
            # Get the current selector map
            selector_map = self.get_selector_map()
            
            # Format the results for return
            elements = []
            for idx, node in selector_map.items():
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
    
    async def click_element_by_index(self, element_index: int, update_selector_map_func=None) -> str:
        """Click an element using its index from the interactive elements map
        
        Args:
            element_index: The index of the element to click (from get_interactive_elements)
            update_selector_map_func: Function to update the selector map
        """
        try:
            cdp_client = await self.server._get_cdp_client()
            
            # Make sure we have the latest selector map
            selector_map = self.get_selector_map()
            if not selector_map and update_selector_map_func:
                await update_selector_map_func()
                selector_map = self.get_selector_map()
            
            # Find the element
            if element_index not in selector_map:
                return f"Element index {element_index} not found. Use get_interactive_elements to see available indices."
            
            node = selector_map[element_index]
            
            # Calculate center of the element for clicking
            x = node.absolute_position.x + (node.absolute_position.width / 2)
            y = node.absolute_position.y + (node.absolute_position.height / 2)
            
            # Click the element
            await cdp_client.send.Input.dispatchMouseEvent({
                'type': 'mousePressed',
                'x': x,
                'y': y,
                'button': 'left',
                'clickCount': 1
            })
            
            await cdp_client.send.Input.dispatchMouseEvent({
                'type': 'mouseReleased',
                'x': x,
                'y': y,
                'button': 'left',
                'clickCount': 1
            })
            
            return f"Successfully clicked element {element_index}: {node.tag_name} '{node.text[:50]}'"
            
        except Exception as e:
            return f"Error clicking element {element_index}: {str(e)}"
    
    async def hide_visual_indicators(self) -> str:
        """Hide the visual indicators (bounding boxes) from the page"""
        try:
            cdp_client = await self.server._get_cdp_client()
            
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
            
            result = await cdp_client.send.Runtime.evaluate({
                'expression': js,
                'returnByValue': True
            })
            
            if result.get('exceptionDetails'):
                return f"Error hiding visual indicators: {result['exceptionDetails']['text']}"
            
            removed = result.get('result', {}).get('value', False)
            return "Visual indicators hidden" if removed else "No visual indicators found to hide"
            
        except Exception as e:
            return f"Error hiding visual indicators: {str(e)}"


def register_browser_tools(server, browser_tools_instance):
    """Register all browser tools with a FastMCP server instance
    
    Args:
        server: FastMCP server instance
        browser_tools_instance: Instance of BrowserTools class
    """
    
    @server.tool()
    async def navigate(url: str) -> str:
        """Navigate to a URL"""
        return await browser_tools_instance.navigate(url)
    
    @server.tool()
    async def click_element(selector: str) -> str:
        """Click an element using a CSS selector"""
        return await browser_tools_instance.click_element(selector)
    
    @server.tool()
    async def type_text(text: str, selector: str = None) -> str:
        """Type text into an element or the current focus"""
        return await browser_tools_instance.type_text(text, selector)
    
    @server.tool()
    async def take_screenshot(format_type: str = "png", quality: int = 90) -> Dict[str, Any]:
        """Take a screenshot of the current page"""
        return await browser_tools_instance.take_screenshot(format_type, quality)
    
    @server.tool()
    async def execute_javascript(expression: str, returnByValue: bool = True) -> Any:
        """Execute JavaScript code in the browser"""
        return await browser_tools_instance.execute_javascript(expression, returnByValue)
    
    @server.tool()
    async def get_page_content(selector: str = None, human_readable: bool = True) -> str:
        """Get the current page's content"""
        return await browser_tools_instance.get_page_content(selector, human_readable)
    
    @server.tool()
    async def wait_for_element(selector: str, timeout: int = 10000) -> str:
        """Wait for an element to appear on the page"""
        return await browser_tools_instance.wait_for_element(selector, timeout)
    
    @server.tool()
    async def get_interactive_elements(show_visual: bool = True, color: str = "rgba(255,0,0,0.25)") -> Dict[str, Any]:
        """Get a list of all interactive elements on the page and optionally show visual indicators"""
        # Note: These functions will be passed from the main server
        return await browser_tools_instance.get_interactive_elements(
            show_visual, color, 
            browser_tools_instance._update_selector_map_func,
            browser_tools_instance._show_bounding_boxes_func
        )
    
    @server.tool()
    async def click_element_by_index(element_index: int) -> str:
        """Click an element using its index from the interactive elements map"""
        return await browser_tools_instance.click_element_by_index(
            element_index, 
            browser_tools_instance._update_selector_map_func
        )
    
    @server.tool()
    async def hide_visual_indicators() -> str:
        """Hide the visual indicators (bounding boxes) from the page"""
        return await browser_tools_instance.hide_visual_indicators()
