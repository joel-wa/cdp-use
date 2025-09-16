#!/usr/bin/env python3

import urllib.request
import json

def test_chrome_connection():
    """Test if Chrome debugging is accessible"""
    try:
        with urllib.request.urlopen('http://localhost:9222/json') as response:
            print(f"✅ Chrome debugging port accessible (Status: {response.status})")
            data = response.read().decode()
            tabs = json.loads(data)
            print(f"📄 Found {len(tabs)} tabs/pages")
            for i, tab in enumerate(tabs[:3]):  # Show first 3 tabs
                print(f"  Tab {i+1}: {tab.get('title', 'No title')} - {tab.get('url', 'No URL')}")
    except urllib.error.URLError:
        print("❌ Chrome debugging port not accessible.")
        print("💡 Start Chrome with: chrome --remote-debugging-port=9222 --user-data-dir=C:\\temp\\chrome_debug")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    return True

if __name__ == "__main__":
    test_chrome_connection()