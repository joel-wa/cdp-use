# Workflow-Enhanced Conversational Orchestrator

A powerful upgrade to the Enhanced Conversational Orchestrator that adds comprehensive workflow automation capabilities. This system can capture, parameterize, and replay agent actions without requiring an LLM for execution, transforming the orchestrator from a reactive tool into a proactive automation platform.

## 🚀 New Features

### 🎬 Workflow Recording & Learning
- **Automatic Pattern Recognition**: Detects repeatable tool sequences during normal operation
- **Intelligent Parameter Extraction**: Automatically identifies URLs, file paths, and other parameterizable values
- **Session Recording**: Capture tool execution patterns for workflow creation
- **Smart Suggestions**: Proactively suggests workflow creation based on usage patterns

### 🔧 Workflow Execution Engine
- **LLM-Independent Execution**: Run workflows without AI model calls for faster, deterministic results
- **Parameter Validation**: Type checking and validation rules for workflow inputs
- **Dependency Management**: Intelligent step ordering based on dependencies
- **Error Recovery**: Built-in retry policies and recovery strategies
- **Conditional Execution**: Support for conditional steps and branching logic

### 📚 Workflow Management
- **YAML Persistence**: Human-readable workflow definitions
- **Version Control**: Track workflow versions and changes
- **Library System**: Organize and manage workflow collections
- **Search & Discovery**: Find workflows by name, description, or functionality
- **Execution Statistics**: Track success rates, performance metrics, and usage patterns

### 💻 Command Interface
- **Interactive CLI**: Full-featured command interface for workflow management
- **Real-time Status**: Monitor recording sessions and workflow execution
- **Bulk Operations**: Manage multiple workflows efficiently
- **Help System**: Comprehensive documentation and examples

## 🛠️ Installation & Setup

### Prerequisites
```bash
# Install required packages
pip install google-generativeai mcp pyyaml python-dotenv

# Set environment variables
export GEMINI_API_KEY="your_api_key_here"
export MCP_SERVER_COMMAND='"path/to/python" "path/to/mcp_server.py" --server-only'
```

### Configuration Options
```bash
# Workflow-specific settings
export WORKFLOWS_DIR="./workflows"                    # Workflow storage directory
export ENABLE_WORKFLOW_LEARNING="true"               # Enable pattern learning
export WORKFLOW_PATTERN_MIN_LENGTH="3"               # Minimum tools for pattern
export AUTO_SUGGEST_WORKFLOWS="true"                 # Auto-suggest workflows
export WORKFLOW_EXECUTION_MODE="interactive"         # Execution mode
```

## 🎯 Quick Start

### Basic Usage
```python
from workflow_enhanced_orchestrator import WorkflowEnhancedConversationalOrchestrator

# Initialize orchestrator
orchestrator = WorkflowEnhancedConversationalOrchestrator()
await orchestrator.initialize()

# Run interactive session
await orchestrator.run_interactive_session()
```

### Workflow Commands
```bash
# List available workflows
workflow list

# Show workflow details
workflow show web_data_extraction

# Run a workflow
workflow run web_data_extraction

# Start recording a new workflow
workflow record start

# Stop recording and create workflow
workflow record stop

# Search workflows
workflow search "web scraping"

# Show execution statistics
workflow stats

# Get workflow suggestions
workflow suggest

# Delete a workflow
workflow delete old_workflow

# Show help
workflow help
```

## 📋 Workflow Definition Format

Workflows are stored as YAML files with the following structure:

```yaml
name: "web_data_extraction"
version: "1.0"
description: "Extract product data from e-commerce website"
author: "agent_learning"
created_at: "2025-09-17T10:30:00Z"

# Input parameters with validation
parameters:
  - name: "target_url"
    type: "string"
    required: true
    description: "URL of the product page"
    validation:
      pattern: "^https?://.+"
      
  - name: "max_items"
    type: "integer"
    required: false
    default: 10
    validation:
      min: 1
      max: 100

# Workflow steps with dependencies
steps:
  - id: "navigate_to_page"
    tool: "navigate"
    description: "Navigate to target URL"
    parameters:
      url: "{{target_url}}"
    retry_policy:
      max_attempts: 3
      backoff: "exponential"
      
  - id: "take_screenshot"
    tool: "take_screenshot"
    description: "Capture page state"
    depends_on: ["navigate_to_page"]
    
  - id: "extract_data"
    tool: "execute_javascript"
    description: "Extract product information"
    depends_on: ["take_screenshot"]
    parameters:
      expression: |
        const products = [];
        document.querySelectorAll('.product-item').forEach((item, index) => {
          if (index < {{max_items}}) {
            products.push({
              name: item.querySelector('.product-name')?.textContent?.trim(),
              price: item.querySelector('.price')?.textContent?.trim()
            });
          }
        });
        return products;

# Error handling configuration
error_handling:
  global_retry_limit: 3
  timeout_seconds: 60
  continue_on_error: false

# Output configuration
outputs:
  - name: "extracted_data"
    source: "extract_data.result"
    format: "json"
  - name: "execution_log"
    source: "workflow.execution_log"
    format: "json"
```

## 🔄 Workflow Lifecycle

### 1. Pattern Detection
The system continuously analyzes tool execution patterns:
- **Web Automation**: `navigate → screenshot → get_elements → execute_javascript`
- **File Processing**: `list_directory → read_file → process → write_file`
- **UI Testing**: `navigate → type_text → click_element → verify`

### 2. Parameter Extraction
Automatically identifies parameterizable values:
- **URLs**: `https://example.com/page` → `{{target_url}}`
- **File Paths**: `/home/user/data.json` → `{{input_file}}`
- **Text Content**: Search queries, form inputs, etc.
- **Numeric Values**: Timeouts, limits, coordinates

### 3. Workflow Creation
```bash
# Start recording session
workflow record start

# Perform actions (navigate, click, extract, etc.)
# System captures all tool executions

# Stop and create workflow
workflow record stop
```

### 4. Workflow Execution
```bash
# Execute with default parameters
workflow run my_workflow

# Execute with custom parameters (in interactive mode)
workflow run my_workflow
# System prompts for required parameters
```

## 📊 Advanced Features

### Pattern Recognition Engine
```python
# Analyze execution patterns
candidates = await learning_engine.analyze_session_for_workflows()

# Get pattern confidence scores
for candidate in candidates:
    print(f"Pattern: {candidate.name}")
    print(f"Confidence: {candidate.confidence_score:.1%}")
    print(f"Reusability: {candidate.estimated_reusability:.1%}")
```

### Workflow Validation
```python
# Validate workflow definition
is_valid, errors = validator.validate_workflow_definition(workflow)

# Validate parameters
validation_result = validator.validate_parameters(workflow, parameters)
```

### Execution Monitoring
```python
# Execute with monitoring
result = await executor.execute_workflow(workflow, parameters)

# Check results
if result.success:
    print(f"Completed in {result.execution_time.total_seconds():.1f}s")
    print(f"Steps executed: {result.steps_executed}")
    print("Outputs:", result.outputs)
```

## 🎯 Use Cases

### 1. Web Data Extraction
```yaml
# Automatically extract product data from e-commerce sites
# Parameters: target_url, max_items, output_format
# Steps: navigate → screenshot → get_elements → extract → format
```

### 2. Automated Testing
```yaml
# Test web application workflows
# Parameters: base_url, test_credentials, expected_outcomes
# Steps: navigate → login → perform_actions → verify → logout
```

### 3. File Processing Pipelines
```yaml
# Process files in batch operations
# Parameters: input_directory, file_pattern, output_format
# Steps: list_files → read → transform → write → cleanup
```

### 4. Report Generation
```yaml
# Generate reports from multiple sources
# Parameters: data_sources, template, output_path
# Steps: collect_data → merge → format → generate → save
```

## 🔧 Integration with Existing Features

The workflow system seamlessly integrates with all existing Enhanced Orchestrator features:

- **Tool Validation**: All workflow steps use existing validation logic
- **Error Recovery**: Leverages existing error analysis and recovery strategies  
- **Context Management**: Maintains conversation context and state awareness
- **Streaming Responses**: Supports progress updates during workflow execution
- **System State Tracking**: Updates system state as workflows execute

## 🚀 Performance Benefits

### Speed Improvements
- **No LLM Calls**: Workflow execution bypasses AI model inference
- **Parallel Execution**: Independent steps can run concurrently
- **Cached Results**: Repeated workflows benefit from cached data

### Reliability Gains
- **Deterministic Execution**: Same inputs always produce same outputs
- **Built-in Retries**: Automatic retry logic for transient failures
- **Validation Checks**: Parameter and result validation prevent errors

### Cost Optimization
- **Reduced API Calls**: Workflows eliminate repeated LLM usage
- **Resource Efficiency**: Lower CPU and memory usage for routine tasks
- **Scalability**: Execute hundreds of workflows without model limits

## 📈 Analytics & Monitoring

### Execution Statistics
```python
# Get workflow performance metrics
stats = await library.get_workflow_stats("web_scraping")
print(f"Success rate: {stats['success_rate']:.1%}")
print(f"Average duration: {stats['avg_duration']:.1f}s")
print(f"Total executions: {stats['executions']}")
```

### Usage Analytics
- **Pattern Frequency**: Track most common tool sequences
- **Success Rates**: Monitor workflow reliability over time
- **Performance Trends**: Identify optimization opportunities
- **Error Analysis**: Understand and fix common failure modes

## 🛡️ Security & Safety

### Parameter Validation
- **Type Safety**: Strict type checking for all parameters
- **Input Sanitization**: Validation rules prevent malicious inputs
- **Range Limits**: Numeric constraints prevent resource abuse

### Execution Safety
- **Timeout Controls**: Prevent runaway workflow execution
- **Resource Limits**: Memory and CPU usage constraints
- **Permission Checks**: Validate access to files and URLs

### Audit Trails
- **Execution Logs**: Complete record of all workflow actions
- **Parameter Tracking**: Log all inputs for debugging
- **Error Recording**: Detailed error information for analysis

## 🔮 Future Enhancements

### Planned Features
- **Visual Workflow Builder**: Drag-and-drop workflow creation interface
- **Workflow Marketplace**: Share workflows across organizations
- **AI-Powered Optimization**: Automatic workflow improvement suggestions
- **REST API**: HTTP interface for workflow execution
- **Webhook Triggers**: Event-driven workflow execution
- **CI/CD Integration**: Workflows as part of deployment pipelines

### Advanced Capabilities  
- **Conditional Branching**: Complex decision trees in workflows
- **Loop Constructs**: Iterative operations and batch processing
- **Parallel Execution**: Concurrent step execution for performance
- **Dynamic Parameters**: Runtime parameter resolution
- **Workflow Composition**: Combine workflows into larger processes

## 📝 License

This project extends the Enhanced Conversational Orchestrator and maintains the same licensing terms.

## 🤝 Contributing

Contributions are welcome! Please read the contributing guidelines and submit pull requests for any improvements.

## 📞 Support

For questions, issues, or feature requests, please:
1. Check the documentation and examples
2. Search existing issues
3. Create a new issue with detailed information
4. Join the community discussions

---

Transform your agent interactions into powerful, reusable workflows with the Workflow-Enhanced Conversational Orchestrator! 🚀