@echo off
REM Seamless CDP Browser MCP Server Startup for Windows
REM This batch file starts Chrome and the MCP server automatically

echo ============================================================
echo CDP Browser MCP Server - Quick Start
echo ============================================================

REM Change to the script directory
cd /d %~dp0

REM Activate virtual environment and run startup script
call .venv\Scripts\activate.bat
python start_browser_mcp.py

pause