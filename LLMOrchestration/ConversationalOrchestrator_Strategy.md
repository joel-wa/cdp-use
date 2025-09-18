
Core Strategy: Conversational Tool Execution Loop
At the heart of the MCP client is a messages array that maintains full conversational context. The loop operates as follows:

1. Wait for User Input
The client pauses until the user types a message.

This input is immediately appended to the messages array with the role "user".

2. Send Messages to the LLM
The entire messages array (not just the latest message) is sent to the LLM.

This ensures the model has full context, including prior tool calls and responses.

3. Receive Assistant Response
The LLM returns an "assistant" message.

This may contain either a direct reply or one or more tool calls.

4. Execute Tool Calls
If tool calls are present, the client enters a sub-loop:

Each tool call is executed via the MCP server.

The result is wrapped in a "tool" message and appended to the messages array.

The tool response includes a tool_call_id to match it with the original request.

5. Send Updated Messages Back to LLM
The updated messages array (now including tool responses) is sent back to the LLM.

The LLM may:

Call additional tools (if dependencies exist).

Or finalize the response to the user.

6. Repeat Until Done
The loop continues until the LLM stops requesting tools.

At that point, the final assistant message is sent to the user.