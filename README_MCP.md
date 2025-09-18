# CDP Browser Control MCP Server

A **Model Context Protocol (MCP) server** that provides browser automation capabilities for AI agents using the **Chrome DevTools Protocol (CDP)**. This server allows AI agents to control web browsers programmatically with full type safety and comprehensive functionality.

## 🚀 Features

- **🤖 AI Agent Ready**: Full MCP compatibility for seamless AI agent integration
- **🌐 Browser Control**: Navigate, click, type, screenshot, and execute JavaScript
- **📊 Resource Access**: Get page content, HTML source, and browser state
- **🔒 Type Safe**: Built on the type-safe CDP client with full error handling
- **⚡ Real-time**: Direct WebSocket communication with Chrome DevTools
- **🎯 CSS Selectors**: Use familiar CSS selectors for element interaction
- **📸 Screenshots**: Capture full page or viewport screenshots
- **🔧 JavaScript**: Execute arbitrary JavaScript with result capture

## 🛠️ Installation & Setup

1. **Install dependencies:**
   ```bash
   cd cdp-use
   uv sync  # or pip install -r requirements.txt
   ```

2. **Start Chrome with debugging:**
   ```bash
   google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-mcp
   ```

3. **Run the MCP server:**
   ```bash
   python examples/mcp_browser_control.py
   ```

## 📖 Available Tools

### 1. **navigate**
Navigate to any URL
```json
{
  "name": "navigate",
  "arguments": {
    "url": "https://example.com"
  }
}
```

### 2. **click_element**
Click elements using CSS selectors
```json
{
  "name": "click_element", 
  "arguments": {
    "selector": "button#submit",
    "timeout": 5
  }
}
```

### 3. **type_text**
Type text into the currently focused element
```json
{
  "name": "type_text",
  "arguments": {
    "text": "Hello, World!"
  }
}
```

### 4. **take_screenshot**
Capture page screenshots
```json
{
  "name": "take_screenshot",
  "arguments": {
    "format": "png",
    "fullPage": true
  }
}
```

### 5. **execute_javascript**
Execute JavaScript code and get results
```json
{
  "name": "execute_javascript",
  "arguments": {
    "expression": "document.title",
    "returnByValue": true
  }
}
```

### 6. **get_page_content**
Get HTML content of the page or specific elements
```json
{
  "name": "get_page_content",
  "arguments": {
    "selector": ".main-content"
  }
}
```

### 7. **wait_for_element**
Wait for elements to appear
```json
{
  "name": "wait_for_element",
  "arguments": {
    "selector": ".loading-complete",
    "timeout": 10
  }
}
```

## 📊 Available Resources

### 1. **browser://current-page**
Get current page information (URL, title, session ID)
```json
{
  "url": "https://example.com",
  "title": "Example Page",
  "session_id": "12345"
}
```

### 2. **browser://page-source**
Get the full HTML source of the current page
```html
<!DOCTYPE html>
<html>
  <head><title>Example</title></head>
  <body>...</body>
</html>
```

## 🤖 AI Agent Integration

### Use with Claude, GPT, or other MCP-compatible AI agents:

1. **Start the server:**
   ```bash
   python examples/mcp_browser_control.py
   ```

2. **Configure your AI agent** to use this MCP server via stdio

3. **Example AI conversation:**
   ```
   AI: I'll help you automate web browsing. Let me navigate to Google.
   
   Action: navigate({"url": "https://google.com"})
   Result: Successfully navigated to https://google.com
   
   AI: Now I'll take a screenshot to see the page.
   
   Action: take_screenshot({"format": "png"})
   Result: [Screenshot data returned]
   
   AI: I can see the Google homepage. Would you like me to search for something?
   ```

## 🎯 Common Use Cases

### **Web Scraping**
```python
# Navigate to page
navigate({"url": "https://example.com"})

# Wait for content to load
wait_for_element({"selector": ".content", "timeout": 10})

# Extract data
get_page_content({"selector": ".product-list"})
```

### **Form Automation**
```python
# Navigate to form
navigate({"url": "https://example.com/form"})

# Fill form fields
click_element({"selector": "input[name='email']"})
type_text({"text": "user@example.com"})

# Submit form
click_element({"selector": "button[type='submit']"})
```

### **Visual Testing**
```python
# Navigate to page
navigate({"url": "https://myapp.com"})

# Take baseline screenshot
take_screenshot({"format": "png", "fullPage": true})

# Interact with UI
click_element({"selector": ".menu-button"})

# Take comparison screenshot
take_screenshot({"format": "png"})
```

### **Dynamic Content Testing**
```python
# Wait for JavaScript to load
wait_for_element({"selector": ".dynamic-content", "timeout": 15})

# Execute JavaScript to get app state
execute_javascript({
  "expression": "JSON.stringify(window.appState)",
  "returnByValue": true
})
```

## 🔧 Advanced Configuration

### **Custom Chrome Launch**
```bash
# Use custom Chrome profile
google-chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/path/to/profile \
  --disable-web-security \
  --disable-features=VizDisplayCompositor
```

### **Headless Mode**
```bash
# Run in headless mode
google-chrome \
  --headless \
  --remote-debugging-port=9222 \
  --disable-gpu \
  --no-sandbox
```

### **Docker Setup**
```dockerfile
FROM browserless/chrome:latest
EXPOSE 9222
CMD ["google-chrome", "--remote-debugging-port=9222", "--remote-debugging-address=0.0.0.0"]
```

## 🛡️ Error Handling

The server provides comprehensive error handling:

- **Connection Errors**: Automatic retry and clear error messages
- **Element Not Found**: Detailed selector validation and suggestions
- **JavaScript Errors**: Full exception details and stack traces
- **Timeout Handling**: Configurable timeouts with graceful failures
- **Resource Validation**: Input validation and sanitization

## 📚 Examples

### **Complete Example Session**
```python
# Start the server
python examples/mcp_browser_control.py

# Example AI agent interaction:
# 1. Navigate to a website
# 2. Take a screenshot
# 3. Find and click a button
# 4. Fill out a form
# 5. Extract results
```

See `examples/mcp_browser_control.py` for a complete working example.

## 🔍 Debugging

### **List Available Tools**
```bash
python examples/mcp_browser_control.py --list-tools
```

### **Start Chrome Only**
```bash
python examples/mcp_browser_control.py --start-chrome
```

### **Server Logs**
The server provides detailed logging for debugging:
- CDP protocol messages
- Browser connection status
- Tool execution results
- Error traces

## 🤝 Contributing

1. Fork the repository
2. Add new tools to `cdp_use/mcp_server.py`
3. Update tool definitions in `TOOLS` list
4. Test with real AI agents
5. Update documentation
6. Submit a pull request

## 🔗 Related

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)
- [CDP-Use Library](README.md)

---

**Ready for AI Agents • Type-Safe • Production Ready**