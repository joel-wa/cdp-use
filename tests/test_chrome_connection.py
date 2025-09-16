#!/usr/bin/env python3

import aiohttp
import asyncio
import json

async def test_chrome_connection():
    """Test if Chrome debugging is accessible"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:9222/json') as resp:
                print(f"✅ Chrome debugging port accessible (Status: {resp.status})")
                data = await resp.text()
                tabs = json.loads(data)
                print(f"📄 Found {len(tabs)} tabs/pages")
                for i, tab in enumerate(tabs[:3]):  # Show first 3 tabs
                    print(f"  Tab {i+1}: {tab.get('title', 'No title')} - {tab.get('url', 'No URL')}")
    except aiohttp.ClientConnectorError:
        print("❌ Chrome debugging port not accessible. Chrome needs to be started with --remote-debugging-port=9222")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_chrome_connection())