# Workflow Execution UI

Tesla-inspired clean interface for managing and monitoring workflow executions.

## Features

- **Clean Design**: White background with black foreground, minimal accents
- **Real-time Monitoring**: Auto-refreshes every 2 seconds to show execution status
- **Easy Workflow Execution**: Simple form to execute workflows with JSON parameters
- **Progress Tracking**: Live progress bars for running workflows
- **Detailed Results**: View complete execution results without copy-paste
- **Batch Operations**: Monitor multiple workflows simultaneously
- **System Status**: Session pool and health monitoring

## Usage

1. Start the API server:
   ```bash
   cd workflow_workbench
   python start_api.py
   ```

2. Open your browser to:
   ```
   http://localhost:8000/ui/index.html
   ```

## Interface Layout

### Left Sidebar - Available Workflows
- Browse all available workflows
- Click to select and auto-fill parameters
- View workflow descriptions and tags

### Center Panel - Execute & Monitor
- **Execute Workflow**: Fill in parameters and start execution
- **Active Executions**: Real-time list of running/queued workflows
  - View progress with percentage bars
  - Cancel running executions
  - Click to view details

### Right Panel - Details & Stats
- **Execution Details**: 
  - Complete execution information
  - Progress tracking
  - Results and outputs (no copy-paste needed!)
  - Error messages if failed
- **System Status**:
  - API uptime
  - Session pool availability
  - Active execution count

## Keyboard Shortcuts

- Click workflow in sidebar to auto-select
- Form validates JSON parameters automatically
- Toast notifications for all actions

## Customization

The UI uses CSS variables for easy theming. Edit `styles.css`:

```css
:root {
    --bg-primary: #ffffff;      /* Main background */
    --text-primary: #000000;    /* Main text */
    --accent-primary: #171a20;  /* Buttons and accents */
}
```

## Auto-refresh

The UI automatically refreshes:
- Active executions: Every 2 seconds
- System health: Every 2 seconds
- Updates selected execution details in real-time

To change refresh interval, edit `app.js`:
```javascript
const REFRESH_INTERVAL = 2000; // milliseconds
```
