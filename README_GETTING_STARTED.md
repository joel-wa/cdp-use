# 🌐 CDP Browser Control MCP Server - Getting Started

A powerful **Model Context Protocol (MCP)** server that enables AI agents to control web browsers through Chrome DevTools Protocol (CDP). Perfect for web automation, testing, and AI-driven browser interactions.

## 🚀 Quick Start (30 seconds)

### 1. **One-Click Setup**
```bash
# Clone and setup
git clone https://github.com/joel-wa/cdp-use.git
cd cdp-use
python -m venv .venv
.venv\Scripts\activate  # Windows
# or: source .venv/bin/activate  # macOS/Linux

# Install dependencies  
pip install -r requirements.txt
uv sync
```

### 2. **Launch Everything**
```bash
# This single command does EVERYTHING:
# ✅ Detects or starts Chrome with debugging
# ✅ Launches MCP server with browser tools
# ✅ Ready for AI agent connections
python start_browser_mcp.py
```

**That's it!** 🎉 Your browser automation server is running!

---

## 🛠️ What You Get

### **7 Powerful Browser Tools:**
- **`navigate`** - Go to any website
- **`click_element`** - Click buttons, links, any element
- **`type_text`** - Fill forms, search boxes
- **`take_screenshot`** - Capture page images
- **`execute_javascript`** - Run custom JS code
- **`get_page_content`** - Extract HTML/text
- **`wait_for_element`** - Wait for dynamic content

### **Smart Chrome Management:**
- 🔍 **Auto-detects** existing Chrome processes
- 🚀 **Auto-starts** Chrome if needed (with debugging enabled)
- 🧹 **Auto-cleanup** on shutdown
- 🔧 **Cross-platform** Chrome detection

---

## 💡 Usage Examples

### **For AI Agents & MCP Clients:**
```bash
# Server runs and waits for MCP client connections
python start_browser_mcp.py

# Connect your AI agent via stdio protocol
# Server provides all browser automation tools automatically
```

### **For Gemini MCP Orchestrator:**
```bash
# 1. Configure .env file (see Configuration section)
# 2. Start the server
python start_browser_mcp.py

# 3. Your Gemini agent can now control browsers!
```

### **Direct Testing:**
```bash
# Test browser automation directly
python examples/mcp_browser_control.py --list-tools

# Just start Chrome (useful for development)
python examples/mcp_browser_control.py --start-chrome
```

---

## ⚙️ Configuration

### **For Gemini Integration:**
Create/edit `.env` file:
```bash
# Required: Your Gemini API key
GEMINI_API_KEY=your_api_key_here

# Optional: Model preference  
GEMINI_MODEL=gemini-1.5-pro-latest

# Auto-configured MCP server command (no need to change)
MCP_SERVER_COMMAND="path/to/python" "path/to/examples/mcp_browser_control.py" --server-only
```

### **Chrome Customization:**
Set environment variable if Chrome isn't found automatically:
```bash
# Windows
set CHROME_PATH="C:\Program Files\Google\Chrome\Application\chrome.exe"

# macOS  
export CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Linux
export CHROME_PATH="/usr/bin/google-chrome"
```

---

## 🔧 Advanced Usage

### **Available Commands:**
```bash
# Show all available browser tools
python examples/mcp_browser_control.py --list-tools

# Start only Chrome (for development)
python examples/mcp_browser_control.py --start-chrome  

# Start only MCP server (assumes Chrome running)
python examples/mcp_browser_control.py --server-only

# Show help and options
python examples/mcp_browser_control.py --help

# Easy batch startup (Windows)
start_browser_mcp.bat
```

### **Integration Options:**
- **Stdio Transport** (recommended for AI agents)
- **HTTP Transport** (for web-based clients) 
- **Direct Python Import** (for Python applications)

---

## 🚨 Troubleshooting

### **Common Issues:**

**"Chrome not found"**
```bash
# Solution: Set Chrome path manually
set CHROME_PATH="C:\Path\To\Your\Chrome.exe"  # Windows
export CHROME_PATH="/path/to/chrome"          # macOS/Linux
```

**"Port 9222 already in use"**
```bash
# Solution: Kill existing Chrome processes
taskkill /F /IM chrome.exe          # Windows  
pkill -f "chrome.*remote-debugging" # macOS/Linux
```

**"Module not found errors"**
```bash
# Solution: Make sure you're in the virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

**"Unicode encoding errors" (Windows)**
- ✅ **Already fixed!** All emoji characters replaced with ASCII
- If you still see issues, try: `chcp 65001` in your terminal

---

## 📚 Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   AI Agent      │◄──►│  MCP Server      │◄──►│   Chrome        │
│  (Gemini, etc.) │    │  (FastMCP-based) │    │  (Debug Mode)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
        ▲                        ▲                        ▲
        │                        │                        │
   stdio/JSON-RPC          Browser Tools              WebSocket
                          (7 automation               (Port 9222)
                           functions)
```

### **Key Components:**
- **`start_browser_mcp.py`** - Main launcher (handles everything automatically)
- **`examples/mcp_browser_control.py`** - Server implementation with tools
- **`cdp_use/mcp_server_fastmcp.py`** - FastMCP-based server core
- **`cdp_use/client.py`** - CDP WebSocket client for Chrome communication

---

## 🎯 What's Next?

After getting it running:

1. **Test the tools** - Try navigating to websites, taking screenshots
2. **Connect your AI agent** - Use stdio transport to integrate with AI systems  
3. **Build automation** - Create workflows for testing, scraping, or user interaction
4. **Extend functionality** - Add custom browser tools using the FastMCP framework

---

## 📞 Need Help?

- **🐛 Issues:** Check the troubleshooting section above
- **💡 Ideas:** This is a powerful foundation for browser automation
- **🔧 Customization:** All code is documented and modular

**Happy automating!** 🤖✨