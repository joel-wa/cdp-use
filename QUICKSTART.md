# Quick Start Guide: CDP Browser Control MCP Server

Get your AI agent controlling browsers in 5 minutes! 🚀

## 🏃‍♂️ Quick Setup

### 1. Install Dependencies
```bash
cd cdp-use
uv sync  # or pip install -r requirements.txt
```

### 2. Start Chrome with Debugging
```powershell
# Windows
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$env:TEMP\chrome-mcp-profile"
```

```bash
google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-mcp-profile
```

### 3. Run the MCP Server
```bash
python examples/mcp_browser_control.py
```

That's it! Your MCP server is now ready for AI agents. 🎉

## 🤖 For AI Agents

Connect to the server via stdin/stdout and use these tools:

```json
{
  "tool": "navigate",
  "arguments": {"url": "https://google.com"}
}
```

```json
{
  "tool": "take_screenshot", 
  "arguments": {"format": "png", "fullPage": true}
}
```

```json
{
  "tool": "click_element",
  "arguments": {"selector": "input[name='q']"}
}
```

## 📚 Available Tools

| Tool | Description | Required Args |
|------|-------------|---------------|
| `navigate` | Go to any URL | `url` |
| `click_element` | Click using CSS selectors | `selector` |
| `type_text` | Type text into focused element | `text` |
| `take_screenshot` | Capture page screenshots | None |
| `execute_javascript` | Run JavaScript code | `expression` |
| `get_page_content` | Get HTML content | None |
| `wait_for_element` | Wait for elements | `selector` |

## 🔍 Quick Test

```bash
# List all available tools
python examples/mcp_browser_control.py --list-tools

# See demo of AI agent interaction
python demo_ai_agent.py

# Run validation tests
python test_mcp.py
```

## 📖 Full Documentation

- [README_MCP.md](README_MCP.md) - Complete MCP server guide
- [README.md](README.md) - CDP library documentation
- [examples/](examples/) - Working examples

## 🆘 Troubleshooting

**Chrome not found?**
```bash
# Try alternative Chrome commands
chromium-browser --remote-debugging-port=9222
google-chrome-stable --remote-debugging-port=9222
```

**Connection issues?**
- Ensure Chrome is running on port 9222
- Check http://localhost:9222 shows the DevTools interface
- No other process is using port 9222

**Permission errors?**
```bash
# Use a clean profile directory
--user-data-dir=/tmp/chrome-mcp-profile-$(date +%s)
```

## 🎯 Common Use Cases

**Web Scraping**
```json
{"tool": "navigate", "arguments": {"url": "https://example.com"}}
{"tool": "wait_for_element", "arguments": {"selector": ".content"}}
{"tool": "get_page_content", "arguments": {"selector": ".data"}}
```

**Form Automation**
```json
{"tool": "click_element", "arguments": {"selector": "input[name='email']"}}
{"tool": "type_text", "arguments": {"text": "user@example.com"}}
{"tool": "click_element", "arguments": {"selector": "button[type='submit']"}}
```

**Visual Testing**
```json
{"tool": "navigate", "arguments": {"url": "https://myapp.com"}}
{"tool": "take_screenshot", "arguments": {"format": "png"}}
{"tool": "click_element", "arguments": {"selector": ".menu"}}
{"tool": "take_screenshot", "arguments": {"format": "png"}}
```

---

**Ready in minutes • Type-safe • AI-powered** 🚀