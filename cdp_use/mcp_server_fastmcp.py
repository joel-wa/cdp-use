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
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from mcp.server import FastMCP
from cdp_use.client import CDPClient
from cdp_use.browser_tools import BrowserTools, register_browser_tools

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
        """Setup all browser automation tools using the external BrowserTools module"""
        # Create browser tools instance with references to this server's methods
        browser_tools = BrowserTools(
            cdp_client_ref=self._get_cdp_client,
            selector_map_ref=lambda: self.selector_map
        )
        
        # Add references to server methods that the tools need
        browser_tools._update_selector_map_func = self.update_selector_map
        browser_tools._show_bounding_boxes_func = self.show_bounding_boxes
        
        # Register all browser tools with this server
        register_browser_tools(self.server, browser_tools)
    
    async def _get_cdp_client(self):
        """Get the CDP client, connecting if necessary"""
        if not self.cdp_client:
            await self._connect_to_browser()
        return self.cdp_client
    
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
                # Use pathlib for the user data directory path
                chrome_debug_path = Path.home() / "temp" / "chrome_debug"
                raise Exception(
                    f"Chrome debugging not accessible on port 9222. "
                    f"Please start Chrome with: chrome --remote-debugging-port=9222 --user-data-dir={chrome_debug_path}"
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