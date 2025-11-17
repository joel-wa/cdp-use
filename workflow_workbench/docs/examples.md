# Usage Examples

## Example 1: Web Data Extraction Workflow

### Objective
Extract product information from an e-commerce website.

### Manual Creation

Create `workflows/product_extraction.yaml`:

```yaml
name: product_extraction
version: "1.0"
description: Extract product details from e-commerce site
author: automation_team

parameters:
  - name: product_url
    type: string
    required: true
    description: URL of the product page
    validation:
      pattern: "^https?://.+"
  
  - name: extract_reviews
    type: boolean
    required: false
    default: false
    description: Whether to extract customer reviews

steps:
  - id: step_1_navigate
    tool: navigate
    description: Navigate to product page
    parameters:
      url: "{{product_url}}"
    retry_policy:
      max_attempts: 3
      backoff_strategy: exponential
  
  - id: step_2_wait
    tool: wait_for_element
    description: Wait for product details to load
    parameters:
      selector: ".product-details"
      timeout: 10000
    depends_on:
      - step_1_navigate
  
  - id: step_3_extract_title
    tool: execute_javascript
    description: Extract product title
    parameters:
      expression: "document.querySelector('.product-title')?.textContent"
    depends_on:
      - step_2_wait
  
  - id: step_4_extract_price
    tool: execute_javascript
    description: Extract product price
    parameters:
      expression: "document.querySelector('.product-price')?.textContent"
    depends_on:
      - step_2_wait
  
  - id: step_5_extract_reviews
    tool: execute_javascript
    description: Extract customer reviews
    parameters:
      expression: "Array.from(document.querySelectorAll('.review')).map(r => ({author: r.querySelector('.author')?.textContent, rating: r.querySelector('.rating')?.textContent, comment: r.querySelector('.comment')?.textContent}))"
    depends_on:
      - step_2_wait
    conditional: "{{extract_reviews}} == true"

error_handling:
  global_retry_limit: 2
  timeout_seconds: 60
  continue_on_error: false

outputs:
  - name: product_title
    source: step_3_extract_title.result
  
  - name: product_price
    source: step_4_extract_price.result
  
  - name: reviews
    source: step_5_extract_reviews.result
  
  - name: execution_log
    source: workflow.execution_log
```

### Execute

```bash
workflow run product_extraction
```

or programmatically:

```python
from workflow_workbench import WorkflowExecutor, WorkflowLibrary

library = WorkflowLibrary()
workflow = await library.load_workflow("product_extraction")

executor = WorkflowExecutor(mcp_session)
result = await executor.execute_workflow(workflow, {
    "product_url": "https://example-shop.com/product/123",
    "extract_reviews": True
})

print(f"Title: {result.outputs['product_title']}")
print(f"Price: {result.outputs['product_price']}")
print(f"Reviews: {len(result.outputs['reviews'])} found")
```

---

## Example 2: Automated Form Submission

### Objective
Fill and submit a contact form automatically.

### Recording Approach

```bash
# Start recording
workflow record start

# Perform actions
> navigate https://example.com/contact
> wait_for_element #contact-form
> type_text name=John Doe selector=#name
> type_text text=john@example.com selector=#email
> type_text text=Hello, I have a question selector=#message
> click_element_by_index element_index=5  # Submit button
> wait_for_element .success-message

# Stop and create workflow
workflow record stop
```

The system creates:

```yaml
name: session_1234567890
version: "1.0"
description: Automated workflow
steps:
  - id: step_1_navigate
    tool: navigate
    parameters:
      url: "{{navigate_url}}"
    retry_policy:
      max_attempts: 2
  
  - id: step_2_wait_for_element
    tool: wait_for_element
    parameters:
      selector: "#contact-form"
    depends_on:
      - step_1_navigate
  
  - id: step_3_type_text
    tool: type_text
    parameters:
      text: "{{type_text_text}}"
      selector: "#name"
    depends_on:
      - step_2_wait_for_element
  # ... more steps
```

### Customize and Execute

Edit the generated workflow, then:

```bash
workflow run session_1234567890
```

---

## Example 3: Multi-Page Data Collection

### Objective
Scrape data from multiple pages of search results.

### Implementation

```yaml
name: multi_page_scraper
version: "1.0"
description: Scrape data from paginated search results
author: data_team

parameters:
  - name: search_url
    type: string
    required: true
    description: Initial search URL
  
  - name: max_pages
    type: integer
    required: false
    default: 5
    validation:
      min: 1
      max: 20

steps:
  - id: init_data
    tool: execute_javascript
    description: Initialize data collection
    parameters:
      expression: "window.scrapedData = []"
  
  - id: page_1_navigate
    tool: navigate
    description: Navigate to first page
    parameters:
      url: "{{search_url}}"
    depends_on:
      - init_data
  
  - id: page_1_scrape
    tool: execute_javascript
    description: Scrape first page
    parameters:
      expression: "window.scrapedData.push(...Array.from(document.querySelectorAll('.result')).map(el => ({title: el.querySelector('.title')?.textContent, link: el.querySelector('a')?.href})))"
    depends_on:
      - page_1_navigate
  
  - id: check_next_page
    tool: get_interactive_elements
    description: Check if next page button exists
    parameters:
      show_visual: false
    depends_on:
      - page_1_scrape
  
  - id: click_next
    tool: click_element_by_index
    description: Click next page button
    parameters:
      element_index: 10  # Adjust based on page structure
    depends_on:
      - check_next_page
    conditional: "{{page_number}} < {{max_pages}}"
  
  - id: page_n_scrape
    tool: execute_javascript
    description: Scrape subsequent page
    parameters:
      expression: "window.scrapedData.push(...Array.from(document.querySelectorAll('.result')).map(el => ({title: el.querySelector('.title')?.textContent, link: el.querySelector('a')?.href})))"
    depends_on:
      - click_next
  
  - id: get_all_data
    tool: execute_javascript
    description: Retrieve all scraped data
    parameters:
      expression: "JSON.stringify(window.scrapedData)"
    depends_on:
      - page_n_scrape

outputs:
  - name: scraped_data
    source: get_all_data.result
    format: json
```

---

## Example 4: File Processing Workflow

### Objective
Read a CSV file, process data, and generate a report.

### Implementation

```yaml
name: csv_report_generator
version: "1.0"
description: Process CSV data and generate report

parameters:
  - name: input_file
    type: string
    required: true
    description: Path to input CSV file
  
  - name: output_file
    type: string
    required: true
    description: Path for output report

steps:
  - id: read_csv
    tool: read_file
    description: Read input CSV file
    parameters:
      path: "{{input_file}}"
  
  - id: process_data
    tool: execute_javascript
    description: Process CSV data
    parameters:
      expression: |
        const lines = {{read_csv.result}}.split('\n');
        const headers = lines[0].split(',');
        const data = lines.slice(1).map(line => {
          const values = line.split(',');
          return headers.reduce((obj, header, i) => {
            obj[header] = values[i];
            return obj;
          }, {});
        });
        const stats = {
          total_rows: data.length,
          averages: {},
          // ... calculations
        };
        JSON.stringify(stats);
    depends_on:
      - read_csv
  
  - id: generate_report
    tool: execute_javascript
    description: Generate HTML report
    parameters:
      expression: |
        const stats = JSON.parse({{process_data.result}});
        `<html><body><h1>Report</h1><p>Total Rows: ${stats.total_rows}</p></body></html>`
    depends_on:
      - process_data
  
  - id: write_report
    tool: write_file
    description: Write report to file
    parameters:
      path: "{{output_file}}"
      content: "{{generate_report.result}}"
    depends_on:
      - generate_report

outputs:
  - name: report_path
    source: write_report.result
  
  - name: statistics
    source: process_data.result
```

---

## Example 5: API Integration Workflow

### Objective
Fetch data from an API and display in browser.

### Implementation

```yaml
name: api_data_display
version: "1.0"
description: Fetch API data and render in browser

parameters:
  - name: api_endpoint
    type: string
    required: true
    description: API endpoint URL
    validation:
      pattern: "^https?://.+/api/.+"
  
  - name: api_key
    type: string
    required: false
    description: API authentication key

steps:
  - id: fetch_api_data
    tool: execute_javascript
    description: Fetch data from API
    parameters:
      expression: |
        fetch('{{api_endpoint}}', {
          headers: {
            'Authorization': 'Bearer {{api_key}}'
          }
        }).then(r => r.json())
    retry_policy:
      max_attempts: 3
      backoff_strategy: exponential
  
  - id: create_html
    tool: execute_javascript
    description: Create HTML visualization
    parameters:
      expression: |
        const data = {{fetch_api_data.result}};
        const html = `
          <div id="data-display">
            <h2>API Data</h2>
            <pre>${JSON.stringify(data, null, 2)}</pre>
          </div>
        `;
        document.body.innerHTML = html;
    depends_on:
      - fetch_api_data
  
  - id: take_screenshot
    tool: take_screenshot
    description: Capture the rendered data
    parameters:
      format_type: "png"
    depends_on:
      - create_html

outputs:
  - name: api_response
    source: fetch_api_data.result
  
  - name: screenshot
    source: take_screenshot.result
```

---

## Example 6: Error Handling and Recovery

### Objective
Demonstrate robust error handling with fallbacks.

### Implementation

```yaml
name: resilient_scraper
version: "1.0"
description: Web scraping with comprehensive error handling

parameters:
  - name: primary_url
    type: string
    required: true
  
  - name: fallback_url
    type: string
    required: false

steps:
  - id: try_primary
    tool: navigate
    description: Try primary URL
    parameters:
      url: "{{primary_url}}"
    retry_policy:
      max_attempts: 3
      backoff_strategy: exponential
    validation:
      timeout_seconds: 10
  
  - id: extract_from_primary
    tool: get_page_content
    description: Extract from primary source
    parameters:
      human_readable: true
    depends_on:
      - try_primary
  
  - id: check_primary_success
    tool: execute_javascript
    description: Verify primary extraction succeeded
    parameters:
      expression: "{{extract_from_primary.result}} ? 'success' : 'failed'"
    depends_on:
      - extract_from_primary
  
  - id: try_fallback
    tool: navigate
    description: Navigate to fallback URL
    parameters:
      url: "{{fallback_url}}"
    depends_on:
      - check_primary_success
    conditional: "{{check_primary_success.result}} == 'failed' && {{fallback_url}} != ''"
    retry_policy:
      max_attempts: 2
  
  - id: extract_from_fallback
    tool: get_page_content
    description: Extract from fallback source
    parameters:
      human_readable: true
    depends_on:
      - try_fallback

error_handling:
  global_retry_limit: 3
  timeout_seconds: 120
  continue_on_error: true
  recovery_strategies:
    - type: retry
      max_attempts: 3
    - type: fallback
      on_error: timeout

outputs:
  - name: data
    source: extract_from_primary.result
  
  - name: data_fallback
    source: extract_from_fallback.result
  
  - name: source_used
    source: check_primary_success.result
```

---

## Example 7: Conditional Branching

### Objective
Execute different paths based on runtime conditions.

### Implementation

```yaml
name: conditional_processor
version: "1.0"
description: Process data differently based on conditions

parameters:
  - name: data_type
    type: string
    required: true
    validation:
      enum: ["csv", "json", "xml"]

steps:
  - id: detect_format
    tool: read_file
    description: Read input file
    parameters:
      path: "{{input_file}}"
  
  - id: process_csv
    tool: execute_javascript
    description: Process CSV format
    parameters:
      expression: "/* CSV processing logic */"
    depends_on:
      - detect_format
    conditional: "{{data_type}} == 'csv'"
  
  - id: process_json
    tool: execute_javascript
    description: Process JSON format
    parameters:
      expression: "/* JSON processing logic */"
    depends_on:
      - detect_format
    conditional: "{{data_type}} == 'json'"
  
  - id: process_xml
    tool: execute_javascript
    description: Process XML format
    parameters:
      expression: "/* XML processing logic */"
    depends_on:
      - detect_format
    conditional: "{{data_type}} == 'xml'"
  
  - id: finalize
    tool: execute_javascript
    description: Final processing step
    parameters:
      expression: "/* Finalization logic */"
    depends_on:
      - process_csv
      - process_json
      - process_xml
```

---

## Running Examples

### From Command Line

```bash
# List available examples
workflow list

# Run an example
workflow run product_extraction

# Show example details
workflow show api_data_display
```

### From Python

```python
import asyncio
from workflow_workbench import (
    WorkflowExecutor,
    WorkflowLibrary,
    WorkflowEnhancedConversationalOrchestrator
)

async def run_example():
    # Initialize orchestrator
    orchestrator = WorkflowEnhancedConversationalOrchestrator()
    await orchestrator.initialize()
    
    # Load and execute workflow
    library = WorkflowLibrary()
    workflow = await library.load_workflow("product_extraction")
    
    executor = WorkflowExecutor(orchestrator.mcp_session)
    result = await executor.execute_workflow(workflow, {
        "product_url": "https://example.com/product/123",
        "extract_reviews": True
    })
    
    # Process results
    if result.success:
        print("✅ Workflow completed successfully")
        print(f"Outputs: {result.outputs}")
    else:
        print(f"❌ Workflow failed: {result.error}")
    
    # Cleanup
    await orchestrator.cleanup()

# Run
asyncio.run(run_example())
```

---

## Tips for Creating Your Own Workflows

1. **Start Simple**: Begin with 2-3 steps, then expand
2. **Test Incrementally**: Test each step before adding the next
3. **Use Recording**: Let the system capture your actions
4. **Parameterize Early**: Make values configurable from the start
5. **Add Error Handling**: Plan for failures
6. **Document Well**: Clear descriptions help future use
7. **Version Control**: Save workflows in git
8. **Monitor Execution**: Review logs and statistics

## Next Steps

- Read the [Workflow Guide](workflows.md) for detailed documentation
- Explore [API Reference](api_reference.md) for programmatic usage
- Check [Architecture Documentation](architecture.md) for system internals
- View [Diagrams](../diagrams/) for visual understanding
