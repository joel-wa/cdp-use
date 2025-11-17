# Workflow System Guide

## Overview

The Workflow System enables you to capture, parameterize, and replay sequences of tool executions without LLM intervention, providing reliable and repeatable automation.

## Workflow Concepts

### What is a Workflow?

A workflow is a sequence of tool executions with:
- **Parameters**: Configurable inputs
- **Steps**: Individual tool calls with dependencies
- **Validation**: Success criteria and error handling
- **Outputs**: Extracted results

### When to Use Workflows

Use workflows for:
- Repeatable automation tasks
- Multi-step processes
- Scheduled operations
- Batch processing
- Reliable execution without LLM variability

## Creating Workflows

### Method 1: Recording Mode

The simplest way to create a workflow:

```bash
# Start recording
workflow record start

# Perform your tasks (tools will be captured)
navigate https://example.com
get_page_content
execute_javascript document.title

# Stop recording and create workflow
workflow record stop
```

The system will:
1. Analyze captured tool executions
2. Identify patterns
3. Extract parameters
4. Generate workflow definition
5. Save to library

### Method 2: Manual Creation

Create a workflow YAML file in `workflows/` directory:

```yaml
name: web_data_extraction
version: "1.0"
description: Extract data from a webpage
author: your_name
created_at: "2025-01-01T00:00:00"

parameters:
  - name: target_url
    type: string
    required: true
    description: URL to extract data from
    validation:
      pattern: "^https?://.+"
  
  - name: selector
    type: string
    required: true
    description: CSS selector for data elements
    default: ".data-class"

steps:
  - id: step_1_navigate
    tool: navigate
    description: Navigate to target URL
    parameters:
      url: "{{target_url}}"
    retry_policy:
      max_attempts: 3
      backoff_strategy: exponential
      initial_delay: 1.0
    
  - id: step_2_get_elements
    tool: get_interactive_elements
    description: Get page elements
    parameters: {}
    depends_on:
      - step_1_navigate
    
  - id: step_3_extract
    tool: execute_javascript
    description: Extract data using selector
    parameters:
      expression: "Array.from(document.querySelectorAll('{{selector}}')).map(el => el.textContent)"
    depends_on:
      - step_2_get_elements

error_handling:
  global_retry_limit: 3
  timeout_seconds: 300
  continue_on_error: false

outputs:
  - name: extracted_data
    source: step_3_extract.result
    format: json
  
  - name: execution_log
    source: workflow.execution_log
    format: json
```

### Method 3: Automatic Learning

The system can automatically suggest workflows based on your activity:

```bash
workflow suggest
```

This analyzes recent tool executions and identifies patterns with high confidence scores.

## Workflow Structure

### Parameters

Define configurable inputs:

```yaml
parameters:
  - name: search_query
    type: string
    required: true
    description: Search term
    
  - name: max_results
    type: integer
    required: false
    default: 10
    validation:
      min: 1
      max: 100
```

**Supported Types**:
- `string`: Text values
- `integer`: Whole numbers
- `float`: Decimal numbers
- `boolean`: True/False
- `array`: Lists
- `object`: Dictionaries

**Validation Options**:
- `pattern`: Regex pattern for strings
- `min`/`max`: Range for numbers
- `enum`: Allowed values list

### Steps

Define workflow steps with dependencies:

```yaml
steps:
  - id: step_1
    tool: navigate
    description: Navigate to page
    parameters:
      url: "{{base_url}}"
    
  - id: step_2
    tool: type_text
    description: Enter search query
    parameters:
      text: "{{search_query}}"
      selector: "#search-input"
    depends_on:
      - step_1
    retry_policy:
      max_attempts: 2
```

**Key Properties**:
- `id`: Unique step identifier
- `tool`: MCP tool name
- `parameters`: Tool arguments (can use templates)
- `depends_on`: Prerequisites
- `conditional`: Optional execution condition
- `retry_policy`: Retry configuration
- `validation`: Success criteria

### Parameter Templating

Use `{{parameter_name}}` syntax in step parameters:

```yaml
parameters:
  url: "{{target_url}}"
  text: "Hello {{user_name}}!"
  count: "{{max_items}}"
```

### Step Dependencies

Control execution order:

```yaml
steps:
  - id: login
    tool: navigate
    # ...
  
  - id: fetch_data
    tool: get_page_content
    depends_on:
      - login  # Won't execute until login completes
```

### Conditional Execution

Execute steps based on conditions:

```yaml
steps:
  - id: check_element
    tool: get_interactive_elements
    # ...
  
  - id: click_if_present
    tool: click_element_by_index
    conditional: "{{element_count}} > 0"
    # Only executes if condition is true
```

### Retry Policies

Configure retry behavior:

```yaml
retry_policy:
  max_attempts: 3
  backoff_strategy: exponential  # exponential, linear, fixed
  initial_delay: 1.0
  max_delay: 60.0
  backoff_multiplier: 2.0
```

**Backoff Strategies**:
- `exponential`: 1s, 2s, 4s, 8s...
- `linear`: 1s, 2s, 3s, 4s...
- `fixed`: 1s, 1s, 1s, 1s...

### Error Handling

Configure workflow-level error handling:

```yaml
error_handling:
  global_retry_limit: 3
  timeout_seconds: 300
  continue_on_error: true  # Continue even if steps fail
  recovery_strategies:
    - type: retry
      max_attempts: 3
    - type: skip
      on_error: timeout
```

### Outputs

Define workflow outputs:

```yaml
outputs:
  - name: page_title
    source: step_1_navigate.result.title
    format: json
  
  - name: execution_time
    source: workflow.execution_time
    format: json
  
  - name: logs
    source: workflow.execution_log
    format: json
```

**Source Patterns**:
- `step_id.result`: Step result
- `step_id.result.property`: Nested property
- `workflow.execution_log`: Execution log
- `workflow.execution_time`: Total time

## Executing Workflows

### Interactive Execution

```bash
workflow run my_workflow_name
```

The system will:
1. Load workflow definition
2. Validate structure
3. Prompt for required parameters (or use defaults)
4. Execute steps in order
5. Display results

### Programmatic Execution

```python
from workflow_workbench import WorkflowExecutor, WorkflowLibrary

# Load workflow
library = WorkflowLibrary()
workflow = await library.load_workflow("web_data_extraction")

# Execute with parameters
executor = WorkflowExecutor(mcp_session)
result = await executor.execute_workflow(workflow, {
    "target_url": "https://example.com",
    "selector": ".data-class"
})

# Check results
if result.success:
    print(f"Completed in {result.execution_time.total_seconds()}s")
    print(f"Outputs: {result.outputs}")
else:
    print(f"Failed: {result.error}")
```

## Managing Workflows

### List Workflows

```bash
workflow list
```

Shows all available workflows with descriptions and statistics.

### Show Workflow Details

```bash
workflow show my_workflow_name
```

Displays complete workflow definition including parameters, steps, and dependencies.

### Search Workflows

```bash
workflow search "web scraping"
```

Finds workflows matching the search query in names or descriptions.

### Delete Workflows

```bash
workflow delete my_workflow_name
```

Removes workflow from library.

### View Statistics

```bash
workflow stats
```

Shows execution statistics for all workflows including:
- Total executions
- Success rate
- Average duration
- Last execution time

## Best Practices

### Naming Conventions

- Use descriptive names: `extract_product_data` not `workflow1`
- Include context: `github_issue_tracker` not `tracker`
- Use underscores: `web_data_extraction` not `webDataExtraction`

### Parameter Design

- Make URLs and paths parameters
- Provide sensible defaults
- Include validation rules
- Write clear descriptions

### Step Organization

- One tool per step
- Clear step IDs: `step_1_navigate`, `step_2_extract`
- Explicit dependencies
- Meaningful descriptions

### Error Handling

- Set appropriate retry policies
- Use `continue_on_error` wisely
- Define success conditions
- Handle timeouts

### Testing

Test workflows with:
- Valid parameters
- Invalid parameters
- Edge cases
- Network failures
- Timeout scenarios

### Documentation

Document in the workflow:
- Purpose and use case
- Required parameters
- Expected outputs
- Known limitations
- Example usage

### Versioning

- Use semantic versioning: `1.0.0`
- Increment for breaking changes
- Save old versions before modifying
- Document changes in metadata

## Common Patterns

### Web Scraping Pattern

```yaml
steps:
  - navigate to target
  - wait for content
  - extract data
  - format results
```

### Form Automation Pattern

```yaml
steps:
  - navigate to form
  - fill fields
  - submit form
  - verify submission
```

### Data Processing Pattern

```yaml
steps:
  - read input file
  - process data
  - validate results
  - write output file
```

### Multi-Page Navigation Pattern

```yaml
steps:
  - navigate to page 1
  - extract data
  - click next page
  - repeat extraction
  - aggregate results
```

## Troubleshooting

### Workflow Won't Load

**Symptoms**: Error loading workflow file

**Solutions**:
- Check YAML syntax
- Verify file exists in `workflows/` directory
- Check file permissions
- Validate required fields

### Step Fails Immediately

**Symptoms**: Step marked as failed without execution

**Solutions**:
- Check step dependencies
- Verify tool name is correct
- Validate parameters
- Review conditional logic

### Parameters Not Resolving

**Symptoms**: Template strings like `{{url}}` appear in output

**Solutions**:
- Ensure parameter is defined in workflow
- Check parameter name spelling
- Verify parameter is passed during execution
- Review template syntax

### Circular Dependency Detected

**Symptoms**: Validation error about circular dependencies

**Solutions**:
- Review `depends_on` relationships
- Draw dependency graph
- Ensure no cycles exist
- Reorder step dependencies

### Timeout Errors

**Symptoms**: Steps timing out consistently

**Solutions**:
- Increase `timeout_seconds` in error_handling
- Increase `TOOL_EXECUTION_TIMEOUT` globally
- Check network connectivity
- Optimize step operations

## Advanced Features

### Dynamic Step Execution

Use conditionals for dynamic behavior:

```yaml
- id: process_large_dataset
  conditional: "{{data_size}} > 1000"
  # Only runs for large datasets
```

### Multi-Path Workflows

Create branches based on conditions:

```yaml
- id: check_status
  tool: get_page_content
  
- id: path_a
  conditional: "{{status}} == 'active'"
  depends_on: [check_status]
  
- id: path_b
  conditional: "{{status}} != 'active'"
  depends_on: [check_status]
```

### Workflow Composition

Reference other workflows:

```yaml
- id: run_subworkflow
  tool: workflow_execute
  parameters:
    workflow_name: "data_preprocessing"
    parameters:
      input: "{{raw_data}}"
```

## Integration

### CI/CD Integration

```bash
#!/bin/bash
# Run workflow as part of CI pipeline
python orchestrator.py --workflow "data_validation" --params '{"source": "prod_db"}'
```

### Scheduling

```bash
# Cron job example
0 * * * * cd /path/to/workflow_workbench && python orchestrator.py --workflow "hourly_sync"
```

### API Integration

```python
from fastapi import FastAPI
from workflow_workbench import WorkflowExecutor, WorkflowLibrary

app = FastAPI()

@app.post("/execute/{workflow_name}")
async def execute_workflow(workflow_name: str, parameters: dict):
    library = WorkflowLibrary()
    workflow = await library.load_workflow(workflow_name)
    
    executor = WorkflowExecutor(mcp_session)
    result = await executor.execute_workflow(workflow, parameters)
    
    return {"success": result.success, "outputs": result.outputs}
```
