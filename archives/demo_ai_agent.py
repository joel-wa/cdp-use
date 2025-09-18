#!/usr/bin/env python3
"""
Demo: AI Agent using CDP Browser Control MCP Server

This demonstrates how an AI agent would interact with the MCP server
to control a web browser.
"""

import asyncio
import json
import sys
from typing import Dict, Any

# This would be replaced by actual MCP client in a real AI agent
class MockAIAgent:
    """Mock AI agent that demonstrates browser automation"""
    
    def __init__(self):
        self.conversation_history = []
        self.available_tools = [
            "navigate", "click_element", "type_text", "take_screenshot",
            "execute_javascript", "get_page_content", "wait_for_element"
        ]
    
    def think(self, message: str):
        """AI thinking process"""
        print(f"🧠 AI: {message}")
        self.conversation_history.append(("thinking", message))
    
    def use_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Simulate using an MCP tool"""
        print(f"🔧 Using tool: {tool_name}")
        print(f"   Arguments: {json.dumps(arguments, indent=2)}")
        
        # In a real implementation, this would call the MCP server
        # For demo purposes, we simulate successful responses
        
        if tool_name == "navigate":
            return f"✅ Successfully navigated to {arguments['url']}"
        elif tool_name == "take_screenshot":
            return "✅ Screenshot captured (base64 image data would be here)"
        elif tool_name == "click_element":
            return f"✅ Clicked element: {arguments['selector']}"
        elif tool_name == "type_text":
            return f"✅ Typed: {arguments['text']}"
        elif tool_name == "execute_javascript":
            return f"✅ JavaScript executed: {arguments['expression']}"
        elif tool_name == "get_page_content":
            if "selector" in arguments:
                return f"✅ Got content for: {arguments['selector']}"
            return "✅ Got full page content"
        elif tool_name == "wait_for_element":
            return f"✅ Element appeared: {arguments['selector']}"
        else:
            return f"❌ Unknown tool: {tool_name}"
    
    def respond(self, message: str):
        """AI response to user"""
        print(f"🤖 AI: {message}")
        self.conversation_history.append(("response", message))

async def demo_web_search():
    """Demo: AI agent helping with web search"""
    agent = MockAIAgent()
    
    print("=" * 60)
    print("🎭 DEMO: AI Agent Web Search Automation")
    print("=" * 60)
    print("👤 User: Can you help me search for information about AI agents on Google?")
    
    agent.think("I need to help the user search for AI agents on Google. Let me break this down:")
    agent.think("1. Navigate to Google")
    agent.think("2. Take a screenshot to see the page")
    agent.think("3. Find and click the search box")
    agent.think("4. Type the search query")
    agent.think("5. Submit the search")
    agent.think("6. Take another screenshot of results")
    
    agent.respond("I'll help you search for AI agents on Google. Let me start by navigating there.")
    
    # Step 1: Navigate
    result = agent.use_tool("navigate", {"url": "https://google.com"})
    print(f"   Result: {result}")
    
    # Step 2: Screenshot
    agent.respond("Now let me take a screenshot to see the Google homepage.")
    result = agent.use_tool("take_screenshot", {"format": "png"})
    print(f"   Result: {result}")
    
    # Step 3: Click search box
    agent.respond("I can see the Google homepage. Let me click on the search box.")
    result = agent.use_tool("click_element", {"selector": "input[name='q']"})
    print(f"   Result: {result}")
    
    # Step 4: Type search query
    agent.respond("Now I'll type your search query about AI agents.")
    result = agent.use_tool("type_text", {"text": "AI agents automation"})
    print(f"   Result: {result}")
    
    # Step 5: Submit search (press Enter key via JavaScript)
    agent.respond("Let me submit the search by pressing Enter.")
    result = agent.use_tool("execute_javascript", {
        "expression": "document.querySelector('input[name=\"q\"]').closest('form').submit()"
    })
    print(f"   Result: {result}")
    
    # Step 6: Wait for results
    agent.respond("Waiting for search results to load...")
    result = agent.use_tool("wait_for_element", {
        "selector": "#search", 
        "timeout": 10
    })
    print(f"   Result: {result}")
    
    # Step 7: Take screenshot of results
    agent.respond("Perfect! Let me take a screenshot of the search results.")
    result = agent.use_tool("take_screenshot", {"format": "png", "fullPage": True})
    print(f"   Result: {result}")
    
    # Step 8: Get search results content
    agent.respond("Let me extract the search results text for you.")
    result = agent.use_tool("get_page_content", {"selector": "#search"})
    print(f"   Result: {result}")
    
    agent.respond("Great! I've successfully searched for 'AI agents automation' on Google and captured the results. The search returned multiple relevant results about AI agents and automation tools.")

async def demo_form_filling():
    """Demo: AI agent filling out a contact form"""
    agent = MockAIAgent()
    
    print("\n" + "=" * 60)
    print("🎭 DEMO: AI Agent Form Filling Automation")
    print("=" * 60)
    print("👤 User: Can you fill out the contact form on example.com with my details?")
    
    agent.think("The user wants me to fill out a contact form. I'll need to:")
    agent.think("1. Navigate to the form page")
    agent.think("2. Take a screenshot to see the form")
    agent.think("3. Fill each field systematically")
    agent.think("4. Submit the form")
    
    agent.respond("I'll help you fill out the contact form on example.com. Let me start by navigating there.")
    
    # Step 1: Navigate
    result = agent.use_tool("navigate", {"url": "https://example.com/contact"})
    print(f"   Result: {result}")
    
    # Step 2: Screenshot to see form
    agent.respond("Let me take a screenshot to see the contact form layout.")
    result = agent.use_tool("take_screenshot", {"format": "png"})
    print(f"   Result: {result}")
    
    # Step 3: Fill name field
    agent.respond("I can see the contact form. Let me start filling it out with your details.")
    result = agent.use_tool("click_element", {"selector": "input[name='name']"})
    print(f"   Result: {result}")
    
    result = agent.use_tool("type_text", {"text": "John Doe"})
    print(f"   Result: {result}")
    
    # Step 4: Fill email field
    agent.respond("Now filling in the email field.")
    result = agent.use_tool("click_element", {"selector": "input[name='email']"})
    print(f"   Result: {result}")
    
    result = agent.use_tool("type_text", {"text": "john.doe@example.com"})
    print(f"   Result: {result}")
    
    # Step 5: Fill message field
    agent.respond("Adding your message to the form.")
    result = agent.use_tool("click_element", {"selector": "textarea[name='message']"})
    print(f"   Result: {result}")
    
    result = agent.use_tool("type_text", {
        "text": "Hello! I'm interested in learning more about your services. This message was sent via AI automation using the CDP MCP server."
    })
    print(f"   Result: {result}")
    
    # Step 6: Submit form
    agent.respond("All fields filled! Now submitting the form.")
    result = agent.use_tool("click_element", {"selector": "button[type='submit']"})
    print(f"   Result: {result}")
    
    # Step 7: Wait for confirmation
    agent.respond("Waiting for form submission confirmation...")
    result = agent.use_tool("wait_for_element", {
        "selector": ".success-message", 
        "timeout": 10
    })
    print(f"   Result: {result}")
    
    agent.respond("Perfect! I've successfully filled out and submitted the contact form with your details. The form has been submitted successfully!")

async def demo_data_extraction():
    """Demo: AI agent extracting data from a webpage"""
    agent = MockAIAgent()
    
    print("\n" + "=" * 60)
    print("🎭 DEMO: AI Agent Data Extraction")
    print("=" * 60)
    print("👤 User: Can you extract the main content from the Wikipedia article about artificial intelligence?")
    
    agent.think("The user wants me to extract content from a Wikipedia article. I'll:")
    agent.think("1. Navigate to the Wikipedia AI article")
    agent.think("2. Wait for the page to load completely")
    agent.think("3. Extract the main article content")
    agent.think("4. Get specific sections like the introduction")
    
    agent.respond("I'll extract the main content from Wikipedia's article on artificial intelligence.")
    
    # Step 1: Navigate
    result = agent.use_tool("navigate", {"url": "https://en.wikipedia.org/wiki/Artificial_intelligence"})
    print(f"   Result: {result}")
    
    # Step 2: Wait for page load
    agent.respond("Waiting for the Wikipedia page to fully load...")
    result = agent.use_tool("wait_for_element", {
        "selector": "#mw-content-text", 
        "timeout": 10
    })
    print(f"   Result: {result}")
    
    # Step 3: Get page title
    agent.respond("Let me get the article title first.")
    result = agent.use_tool("execute_javascript", {
        "expression": "document.querySelector('h1#firstHeading').textContent"
    })
    print(f"   Result: {result}")
    
    # Step 4: Extract introduction paragraph
    agent.respond("Now extracting the introduction paragraph.")
    result = agent.use_tool("get_page_content", {
        "selector": "#mw-content-text .mw-parser-output > p:first-of-type"
    })
    print(f"   Result: {result}")
    
    # Step 5: Get table of contents
    agent.respond("Getting the table of contents to understand the article structure.")
    result = agent.use_tool("execute_javascript", {
        "expression": "Array.from(document.querySelectorAll('#toc .toclevel-1 .toctext')).map(el => el.textContent)"
    })
    print(f"   Result: {result}")
    
    # Step 6: Take a screenshot for reference
    agent.respond("Taking a screenshot of the article for your reference.")
    result = agent.use_tool("take_screenshot", {"format": "png", "fullPage": True})
    print(f"   Result: {result}")
    
    agent.respond("I've successfully extracted key information from the Wikipedia article on artificial intelligence, including the title, introduction, and table of contents. You now have both the text content and a visual reference screenshot!")

async def main():
    """Run all demo scenarios"""
    print("🎬 CDP Browser Control MCP Server - AI Agent Demos")
    print("=" * 70)
    print("This demonstrates how AI agents can use the MCP server to control browsers")
    print("=" * 70)
    
    # Run demo scenarios
    await demo_web_search()
    await demo_form_filling()
    await demo_data_extraction()
    
    print("\n" + "=" * 70)
    print("🎉 All Demos Complete!")
    print("=" * 70)
    print("These demos show how AI agents can use the CDP MCP server to:")
    print("✅ Navigate websites and take screenshots")
    print("✅ Search for information on Google")
    print("✅ Fill out forms automatically")
    print("✅ Extract structured data from web pages")
    print("✅ Execute JavaScript and interact with dynamic content")
    print()
    print("🚀 To run the actual MCP server:")
    print("   python examples/mcp_browser_control.py")
    print()
    print("📚 For full documentation:")
    print("   See README_MCP.md")

if __name__ == "__main__":
    asyncio.run(main())