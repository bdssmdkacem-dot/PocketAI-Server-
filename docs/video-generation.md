# PocketAI Video Generation Integration

## Architecture boundary

PocketAI remains a phone-first local AI controller. The Android device runs the GGUF reasoning model through llama.cpp and owns the authenticated Agent task queue. The paired computer runs the optional ComfyUI adapter and performs the GPU-heavy inference.

PocketAI Android (LLM + authenticated task API)
    -> existing pocketai-agent-v1 task protocol
    -> PocketAI Computer Agent (Windows/Linux)
    -> fixed operator-configured endpoint
    -> ComfyUI HTTP API (GPU worker)
    -> Video model workflow and output files on worker

No video model weights or Python video runtime are packaged into the Android APK. Existing browser tasks continue to use the same agent process and queue.

## Current adapter actions

- video.comfyui.status: checks /system_stats and /queue.
- video.comfyui.submit: loads a trusted API-format workflow JSON from the configured workflow directory, optionally replaces explicitly identified CLIPTextEncode prompt nodes, and submits it to /prompt.
- video.comfyui.history: reads /history/{prompt_id} and returns completion state and output metadata.

The adapter intentionally does not invent workflows or node IDs. Each workflow must first be exported in API format and tested in ComfyUI itself. Different video models and custom nodes have different graph structures.

## Configuration and trust boundary

- Local default: http://127.0.0.1:8188.
- Workflow JSON files are restricted to the configured workflow directory; absolute paths and parent-directory traversal are rejected.
- Task payloads cannot choose or override the ComfyUI base URL.
- Remote endpoints are disabled by default. Remote mode requires explicit opt-in, HTTPS, and a bearer token supplied to an authenticated gateway.
- Do not expose an unauthenticated ComfyUI instance directly to the public internet.
- The Android Agent API continues to require its per-installation bearer token.

## Current scope and known limitations

This is the first integration slice: connectivity, trusted workflow submission, and job history. It is not yet a full Flow-like studio. The following remain future work:

1. GPU capability and VRAM preflight with model-specific recommendations.
2. Curated, license-reviewed Wan/LTX workflows and versioned workflow schemas.
3. Long-running job progress streaming and cancellation.
4. Safe retrieval of generated video files to the phone or a user-selected storage location.
5. Multi-shot story planning, character reference management, clip sequencing, audio, and FFmpeg assembly.
6. Real Windows GPU integration tests using the user's actual GPU and model weights.

A successful HTTP submission only means that ComfyUI accepted the workflow into its queue. It does not prove that rendering completed or that the output is visually acceptable.
