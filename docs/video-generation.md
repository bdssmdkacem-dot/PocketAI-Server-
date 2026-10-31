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

## Product roadmap: Flow-like long-form Video Studio

The product goal is to let a user create a coherent long-form video from a brief, not merely submit one prompt to a video model. PocketAI is the orchestrator and ComfyUI is the replaceable GPU rendering backend.

### Phase 0 — hardware and model feasibility (gate before model downloads)

- [ ] Capture the paired Windows PC GPU report with `nvidia-smi` (GPU model, VRAM, driver/CUDA information).
- [ ] Record system RAM, free disk space, and available storage for model weights and generated clips.
- [ ] Verify the installed Python, PyTorch, ComfyUI and custom-node versions.
- [ ] Benchmark a small test workflow and record peak VRAM, render time, resolution, frame count, and failure behavior.
- [ ] Select a model only after comparing measured hardware requirements and its code/weight license. Evaluate Wan and LTX as candidates; do not assume either is compatible before checking the exact model variant and workflow.
- [ ] Keep large model downloads opt-in and show expected disk/VRAM requirements before installation.

**Current gate:** exact PC GPU/VRAM is not yet confirmed. Do not select or download a large video model, and do not claim local generation is ready, until this phase is complete.

### Phase 1 — dependable single-clip generation

- [ ] Add versioned, license-reviewed API workflows for the selected model.
- [ ] Validate workflow schema, required custom nodes, model files, input dimensions, frame count, and VRAM estimate before queue submission.
- [ ] Add queue progress polling/streaming, cancellation, retry policy, and useful failure diagnostics.
- [ ] Retrieve completed output safely from the PC to a user-selected destination on the phone.
- [ ] Verify the actual video file (exists, decodes, duration, dimensions, frame rate, audio streams) rather than treating a queued prompt as success.
- [ ] Run repeated real GPU jobs and record resource use and output quality.

### Phase 2 — Story Studio and continuity

- [ ] Convert a user brief into a structured story: premise, duration, target aspect ratio, language, narration, scenes, and shot list.
- [ ] Let the user review/edit the script and storyboard before spending GPU time.
- [ ] Create a character bible with stable visual descriptions, reference images, wardrobe, proportions, and negative constraints.
- [ ] Store location/style references and continuity rules per project.
- [ ] Generate each shot as a separately tracked job with prompt, seed/settings, reference assets, model/workflow version, and output provenance.
- [ ] Add per-shot preview, regeneration, approval, and reorder controls. Never silently replace an approved shot.

### Phase 3 — long-form assembly

- [ ] Assemble approved clips in story order with FFmpeg.
- [ ] Add configurable transitions, titles, subtitles, narration, ambience, and licensed music.
- [ ] Normalize frame size, frame rate, pixel format, loudness, and audio sample rate before final muxing.
- [ ] Support checkpoints and resumable rendering so a failed scene does not restart the whole film.
- [ ] Export a review copy and a final high-quality copy; verify duration, playback, audio sync, and output integrity.

### Phase 4 — scale and commercial hardening

- [ ] Support projects around 5–10 minutes as the first long-form acceptance target.
- [ ] After the first target passes quality, continuity, and performance checks, test 30-minute projects using resumable scene batches.
- [ ] Add storage quotas, cleanup controls, job history, progress notifications, and estimated compute/time costs.
- [ ] Add explicit confirmation before large downloads, GPU jobs, overwriting files, or deleting project assets.
- [ ] Test Android phone ↔ Windows PC reconnects, interrupted LAN, PC sleep/restart, and partial job recovery.
- [ ] Document model and custom-node licenses, attribution obligations, and permitted commercial use for every shipped workflow.

### Definition of done for a long-form project

A project is not accepted merely because every ComfyUI request returned a prompt ID. Acceptance requires: all approved scenes rendered; every output file decodes; scene order and character identity are reviewed; audio is synchronized; final duration and resolution match the project settings; the assembled file plays from beginning to end; and the project can recover from an interrupted job without losing approved work.

## Immediate next action

On the Windows PC paired with PocketAI, run:

```powershell
nvidia-smi
```

Save the complete output with the PC's RAM and free disk-space figures. Use that evidence to choose a compatible model variant and workflow. If `nvidia-smi` is unavailable, identify the GPU in Windows Device Manager and collect its exact model and dedicated VRAM instead.
