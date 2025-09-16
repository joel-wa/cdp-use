# Orchestrator Debug Flow Analysis

## Current Issue: Generic Fallback Responses

The web UI is showing generic fallback responses instead of actual AI-generated content. Here's the analysis of what's happening:

```mermaid
flowchart TD
    A[User Enters Goal] --> B[GeminiMCPOrchestrator.run_goal]
    B --> C[Start Orchestration Loop]
    C --> D[Execute Planner Role]
    
    D --> E{Gemini API Call<br/>_generate_content}
    E --> F{Response Processing}
    
    F --> G{Has Candidates?}
    G -->|No| H[Log Warning: No candidates]
    G -->|Yes| I{Has Content Parts?}
    
    I -->|No| J[Log Warning: No content parts]
    I -->|Yes| K[Extract Text from Parts]
    
    K --> L{JSON Parsing}
    L -->|Success| M[Return Structured Response]
    L -->|Fail| N[JSON Parse Error]
    
    H --> O[Create Fallback Response]
    J --> O
    N --> O
    
    O --> P{Role Type?}
    P -->|Planner| Q[Return: FALLBACK planning failed]
    P -->|Executor| R[Return: FALLBACK execution failed]
    P -->|Critic| S[Return: FALLBACK analysis failed]
    P -->|Reviewer| T[Return: FALLBACK review failed]
    
    Q --> U[Web UI Shows Fallback Text]
    R --> U
    S --> U
    T --> U
    
    M --> V[Continue to Next Role]
    V --> W[Execute Executor Role]
    W --> E
    
    style O fill:#ff9999
    style P fill:#ff9999
    style Q fill:#ff9999
    style R fill:#ff9999
    style S fill:#ff9999
    style T fill:#ff9999
    style U fill:#ff9999
```

## Problem Areas Identified:

1. **Gemini API Response Issues**: The API might not be returning proper candidates or content
2. **JSON Schema Mismatch**: The response schema might not match what Gemini is actually returning
3. **Missing Error Logging**: We don't see what the actual Gemini response looks like
4. **Generic Fallbacks**: Instead of showing real errors, we show generic messages

## Solution Applied:

1. ✅ Added detailed logging to track API responses
2. ✅ Improved fallback responses to show actual error details
3. ✅ Added better error handling for API initialization
4. ✅ Enhanced JSON parsing error messages

## Next Steps:

Run the orchestrator and check the logs to see:
- If Gemini API is responding
- What the actual response format looks like
- Where exactly the failure is occurring
