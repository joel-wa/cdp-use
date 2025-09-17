#!/usr/bin/env python3
"""
Live Multimodal Test for MCP Browser + Gemini Integration

Tests the complete pipeline:
1. Connect to MCP browser server
2. Navigate to a test page
3. Take a screenshot via MCP take_screenshot tool
4. Send screenshot + prompt to Gemini for analysis
5. Print Gemini's visual analysis

This validates that base64 images from MCP tools are properly
converted and sent to Gemini as image Parts.
"""

import asyncio
import base64
import json
import logging
import os
import sys
from contextlib import AsyncExitStack
from dotenv import load_dotenv

# Add project paths for imports
sys.path.append(os.path.dirname(__file__))

from google import genai
from google.genai import types
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

# Load environment
load_dotenv()

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
MCP_SERVER_COMMAND = os.getenv("MCP_SERVER_COMMAND", 
    '"C:\\Users\\RanVic\\cdp-use\\.venv\\Scripts\\python.exe" "C:\\Users\\RanVic\\cdp-use\\examples\\mcp_browser_control.py" --server-only'
)
TEST_URL = "https:youtube.com"  # Simple, reliable test page

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MultimodalTester:
    """Test multimodal integration between MCP browser tools and Gemini"""
    
    def __init__(self):
        self.mcp_session = None
        self.genai_client = None
        self.exit_stack = AsyncExitStack()
        
    async def initialize(self):
        """Initialize connections to MCP server and Gemini"""
        logger.info("🚀 Initializing multimodal test...")
        
        # Initialize Gemini client
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable is required")
            
        self.genai_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info(f"✅ Gemini client initialized with model: {GEMINI_MODEL}")
        
        # Connect to MCP server
        await self._connect_mcp_server()
        
    async def _connect_mcp_server(self):
        """Connect to MCP browser server via stdio"""
        logger.info(f"📡 Connecting to MCP server: {MCP_SERVER_COMMAND}")
        
        # Parse command
        import shlex
        cmd_parts = shlex.split(MCP_SERVER_COMMAND)
        command = cmd_parts[0]
        args = cmd_parts[1:] if len(cmd_parts) > 1 else []
        
        # Start MCP server process
        server_params = StdioServerParameters(command=command, args=args)
        server_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        
        read, write = server_transport
        self.mcp_session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        await self.mcp_session.initialize()
        
        logger.info("✅ Connected to MCP server")
        
    def _decode_base64_image(self, b64str: str) -> bytes:
        """Decode base64 image data, handling data URL prefixes"""
        if not b64str:
            raise ValueError("Empty base64 string")
            
        # Strip data URL prefix if present
        if b64str.startswith("data:"):
            try:
                _, rest = b64str.split(',', 1)
                b64str = rest
            except ValueError:
                raise ValueError("Malformed data URL")
                
        return base64.b64decode(b64str)
        
    async def _execute_mcp_tool(self, tool_name: str, arguments: dict):
        """Execute an MCP tool and return structured result"""
        logger.info(f"🔧 Executing MCP tool: {tool_name}")
        logger.debug(f"Arguments: {arguments}")
        
        result = await self.mcp_session.call_tool(tool_name, arguments)
        
        # Extract content from MCP result
        if hasattr(result, 'content') and result.content:
            # Convert MCP content to list of dicts
            content_items = []
            for item in result.content:
                if hasattr(item, 'text'):
                    # Text content
                    try:
                        # Try to parse as JSON first
                        parsed = json.loads(item.text)
                        content_items.append(parsed)
                    except json.JSONDecodeError:
                        # Plain text
                        content_items.append({"type": "text", "text": item.text})
                else:
                    # Other content types
                    content_items.append(item)
                    
            return content_items
        else:
            return [{"type": "text", "text": str(result)}]
            
    async def run_test(self):
        """Run the complete multimodal test"""
        try:
            logger.info("🌐 Step 1: Navigate to test page")
            nav_result = await self._execute_mcp_tool("navigate", {"url": TEST_URL})
            logger.info(f"Navigation result: {nav_result}")
            
            # Small delay to let page load
            await asyncio.sleep(2)
            
            logger.info("📸 Step 2: Take screenshot via MCP")
            screenshot_result = await self._execute_mcp_tool("take_screenshot", {
                "format": "png",
                "fullPage": False
            })
            
            # Debug: Print what we actually got
            logger.info(f"Screenshot result structure: {screenshot_result}")
            
            # Find image data in result - handle different possible formats
            image_data = None
            mime_type = "image/png"
            
            for item in screenshot_result:
                logger.info(f"Processing screenshot result item: {type(item)} - {item}")
                
                if isinstance(item, dict):
                    # Check for direct image format: {"type": "image", "data": "...", "mimeType": "..."}
                    if item.get("type") == "image":
                        image_data = item.get("data")
                        mime_type = item.get("mimeType", "image/png")
                        break
                    # Check if it's a text item that contains base64 data
                    elif item.get("type") == "text":
                        text_content = item.get("text", "")
                        # Look for base64 image patterns
                        if "data:image/" in text_content:
                            # Extract from data URL
                            try:
                                _, rest = text_content.split(',', 1)
                                image_data = rest.strip()
                                mime_type = "image/png"
                                break
                            except ValueError:
                                pass
                        # Check if it's just raw base64
                        elif len(text_content) > 1000 and text_content.isalnum():
                            image_data = text_content
                            mime_type = "image/png"
                            break
                            
            if not image_data:
                # Try to get raw MCP result without our parsing
                logger.info("Trying raw MCP result access...")
                raw_result = await self.mcp_session.call_tool("take_screenshot", {"format": "png"})
                logger.info(f"Raw MCP result: {raw_result}")
                
                raise ValueError(f"No image data found in screenshot result. Got: {screenshot_result}")
                
            logger.info(f"✅ Screenshot captured ({len(image_data)} chars base64, {mime_type})")
            
            logger.info("🤖 Step 3: Send image to Gemini for analysis")
            
            # Decode base64 to bytes
            image_bytes = self._decode_base64_image(image_data)
            logger.info(f"📊 Image size: {len(image_bytes)} bytes")
            
            # Create multimodal content for Gemini
            contents = [
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                types.Part(text="What do you see in this screenshot? Describe the main elements, colors, and layout of the webpage.")
            ]
            
            # Call Gemini with image + text prompt
            response = await self.genai_client.aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=1024
                )
            )
            
            if response.candidates and response.candidates[0].content:
                analysis = response.candidates[0].content.parts[0].text
                logger.info("🎉 Gemini visual analysis:")
                print("\n" + "="*60)
                print("🔍 GEMINI'S VISUAL ANALYSIS OF SCREENSHOT:")
                print("="*60)
                print(analysis)
                print("="*60)
                
                return True
            else:
                logger.error("❌ No response from Gemini")
                return False
                
        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
            return False
            
    async def cleanup(self):
        """Clean up resources"""
        if self.exit_stack:
            await self.exit_stack.aclose()


async def main():
    """Main test runner"""
    print("🧪 Multimodal Integration Test")
    print("Testing: MCP Browser → Screenshot → Gemini Analysis")
    print("-" * 50)
    
    tester = MultimodalTester()
    
    try:
        await tester.initialize()
        success = await tester.run_test()
        
        if success:
            print("\n✅ TEST PASSED: Multimodal pipeline working!")
            print("The orchestrator can now send browser screenshots to Gemini.")
        else:
            print("\n❌ TEST FAILED: Check logs for details")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Test setup failed: {e}")
        print(f"\n❌ TEST ERROR: {e}")
        sys.exit(1)
    finally:
        await tester.cleanup()


if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ Error: GEMINI_API_KEY environment variable is required")
        print("Please set your Gemini API key:")
        print("  $env:GEMINI_API_KEY = 'your-api-key-here'  # PowerShell")
        sys.exit(1)
        
    asyncio.run(main())