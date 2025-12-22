# CDP Browser Control with AI

**Control web browsers with AI agents using Chrome DevTools Protocol (CDP) and Model Context Protocol (MCP)**

## Quick Start

### 1. Install Dependencies
```bash
cd cdp-use
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux
uv sync
```

### 2. Launch Everything
```bash
# This single command does EVERYTHING:
# - Detects or starts Chrome with debugging
# - Launches MCP server with browser tools
# - Ready for AI agent connections
python start_browser_mcp.py
```

**That's it!** The browser for automation is now running (MCP Accessible browser)

### 3. Run the Web UI to Control It
- Open and run the `orchestrator_web_ui.py` file
- Navigate to the MCP Chat UI in your browser
- Start controlling the browser with AI, powered by Gemini

## What You Get

**7 Browser Control Tools:**
- `navigate` - Go to any website
- `click_element` - Click buttons, links, elements
- `type_text` - Fill forms, search boxes
- `take_screenshot` - Capture page images
- `execute_javascript` - Run custom JS code
- `get_page_content` - Extract HTML/text
- `wait_for_element` - Wait for dynamic content

## Configuration

Create a `.env` file:
```bash
GEMINI_API_KEY=your_api_key_here
```

## Troubleshooting

**Chrome not found?**
```bash
set GOOGLE_CHROME_PATH="C:\Path\To\Chrome.exe"  # Windows
```

**Port 9222 already in use?**
```bash
taskkill /F /IM chrome.exe  # Windows
```

## More Documentation

- [Detailed Getting Started Guide](README_GETTING_STARTED.md)
- [MCP Server Documentation](README_MCP.md)
- [Workflow System](WORKFLOW_AUTOMATION_SYSTEM.md)

---

**Ready for AI-powered browser automation!** 🤖✨
