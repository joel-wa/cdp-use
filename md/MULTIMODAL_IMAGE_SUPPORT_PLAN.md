# Multimodal Image Support Plan

## Overview
Add multimodal image support to the conversational orchestrator so base64 images returned by MCP tools (e.g. `take_screenshot`) are converted to bytes and sent to Gemini as image `Part`s for visual context before each LLM decision.

## Findings
- The `take_screenshot` tool returns objects like `{ "type": "image", "data": "<base64>", "mimeType": "image/png" }`.
- Gemini accepts image bytes via `types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg')`.
- Current orchestrator stores tool results as text-only JSON and does not send images.

## Steps (concise)
1. Detect image tool responses
   - Add helper `_extract_images_from_tool_result(tool_result)` that returns `[{data_base64, mime_type, tool_call_id}]`.

2. Convert base64 to bytes
   - Add `_decode_base64_image(base64_str) -> bytes` and validate size/type.

3. Attach images to Gemini calls
   - Extend the content-building step in `process_user_input()` to include `types.Part.from_bytes(...)` for any images captured since the last model call.
   - Example (sync form):
```py
from google.genai import types

with open('path/to/small-sample.jpg','rb') as f:
    image_bytes = f.read()

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=[
        types.Part.from_bytes(data=image_bytes, mime_type='image/jpeg'),
        'Caption this image.'
    ]
)
```

4. Automatic screenshot integration (optional)
   - Add config flag `ENABLE_VISUAL_CONTEXT` (env var) to auto-call `take_screenshot` before LLM calls.
   - Support throttling or sampling (`AUTO_SCREENSHOT_INTERVAL`) to avoid excessive images.

5. Error handling & cleanup
   - Gracefully skip invalid images and log warnings.
   - Do not persist images in full conversation history; keep only minimal references (or bytes) for immediate LLM calls and then discard.

## Considerations
- **Performance:** Images are large—limit image size and compress if needed. Use `MAX_IMAGE_BYTES` config.
- **Cost & Rate Limits:** Sending images increases model usage and latency. Make this opt-in by default.
- **Security & Privacy:** Images may contain sensitive data; keep them in memory and ensure they are not logged or written to persistent storage unless explicitly requested.
- **Relevance Filtering:** Only include images when they add value (UI changes, visual cues). Consider heuristics: new URL, DOM change, or explicit tool response.
- **MIME detection:** Prefer the `mimeType` returned by MCP; fallback to heuristics from image bytes if absent.

## Integration points
- File to edit: `simple_conversational_orchestrator.py`
  - Add small helpers near the top for base64 decoding and image validation.
  - Update `process_user_input()` when building `contents` for `genai_client.models.generate_content(...)` to prepend `types.Part.from_bytes(...)` entries for available images.
- Optional: Add CLI/env flags to `simple_conversational_orchestrator.py` to turn visual context on/off.

## Minimal config suggestions
```env
ENABLE_VISUAL_CONTEXT=true
MAX_IMAGE_BYTES=1048576  # 1MB
AUTO_SCREENSHOT_INTERVAL=3
```

## Example flow (summary)
1. User input appended to messages.
2. Optionally capture screenshot (if enabled) via MCP `take_screenshot` tool.
3. Convert any image tool results to bytes.
4. Build `contents` for Gemini: image `Part`s first, then text parts.
5. Call Gemini; process model response as before.

## Next steps (implementation)
- Add helpers for base64->bytes and mime validation.
- Update `process_user_input()` to include image `Part`s before text content.
- Add optional auto-screenshot logic and configuration handling.

---

Concise, actionable plan ready to implement. If you want, I can now implement the helpers and patch `simple_conversational_orchestrator.py` to include the image handling and an opt-in env flag. 