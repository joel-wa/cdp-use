#!/usr/bin/env python3

import urllib.request
import json

def get_chrome_websocket_url():
    """Get the WebSocket URL for Chrome debugging"""
    try:
        with urllib.request.urlopen('http://localhost:9222/json') as response:
            data = response.read().decode()
            tabs = json.loads(data)
            if tabs:
                # Return the WebSocket URL of the first tab/page
                ws_url = tabs[0]['webSocketDebuggerUrl']
                print(f"📡 WebSocket URL: {ws_url}")
                return ws_url
            else:
                print("❌ No tabs/pages found")
                return None
    except Exception as e:
        print(f"❌ Error getting WebSocket URL: {e}")
        return None

if __name__ == "__main__":
    get_chrome_websocket_url()