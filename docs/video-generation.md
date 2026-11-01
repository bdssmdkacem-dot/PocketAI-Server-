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

**Confirmed paired-PC profile (reported by the user, 2026-11-01):**

| Component | Confirmed value |
|---|---|
| OS | Windows 10 64-bit |
| CPU | Intel Core i5-6500 @ 3.20 GHz (6th generation, 4 cores) |
| Integrated GPU | Intel HD Graphics 530 |
| System RAM | 7.7 GB |
| NVIDIA/CUDA | Not present |

**Feasibility decision:** this PC is not a practical local worker for modern diffusion video models such as large Wan/LTX variants. Do not download large video weights or advertise local video generation on this machine. Use it initially as the orchestration, file-management, and FFmpeg assembly host. CPU-based AI inference may be tested for lightweight tasks only, with measured latency and memory use.

OpenVINO is a candidate for CPU inference: Intel's current requirements list 6th-generation Intel Core CPUs and Windows 10 64-bit as supported. OpenVINO documentation also lists Intel HD Graphics families for GPU inference, but actual HD Graphics 530 use must be verified against the installed driver, OpenCL support, and the exact runtime/device plugin; generic family support is not proof that this particular machine will accelerate the chosen workload. Prefer CPU as the first validated target. See the [OpenVINO system requirements](https://docs.openvino.ai/2026/about-openvino/release-notes-openvino/system-requirements.html).

- [x] Capture exact CPU, integrated GPU, OS architecture, and system RAM.
- [ ] Record free disk space, Intel graphics driver version/date, and Windows build.
- [ ] Check whether OpenVINO detects the CPU and, separately, whether it detects a usable GPU device. Record the device list and a small inference benchmark; do not assume GPU acceleration.
- [ ] Verify Python, PyTorch, ComfyUI, FFmpeg, and custom-node versions only if those components are installed.
- [ ] Benchmark non-generative workloads first (prompt/story planning, image resizing, video assembly) and record peak RAM, CPU utilization, and elapsed time.
- [ ] If evaluating video generation, use a remote/hosted GPU worker or a separately upgraded machine with adequate dedicated VRAM. Compare exact model variant requirements and code/weight licenses before selecting it.
- [ ] Keep all large model downloads opt-in and show expected disk/RAM/VRAM requirements before installation.

**Current gate:** the confirmed PC is suitable as a controller/assembler candidate, not as the assumed local diffusion-video renderer. Do not select or download Wan/LTX video weights for this PC. Revisit local generation only if a compatible external GPU worker is added or a small model is proven through a measured end-to-end test.

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

On the paired Windows 10 PC, collect the remaining storage, driver, and OS details:

```powershell
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, OSArchitecture
Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, DriverDate, AdapterRAM
Get-PSDrive -PSProvider FileSystem | Select-Object Name, Used, Free
ffmpeg -version
```

The user has already confirmed Windows 10 64-bit, Intel Core i5-6500, Intel HD Graphics 530, and 7.7 GB RAM. Use the remaining evidence to validate the host's practical role and any OpenVINO CPU/GPU path. Keep large model downloads disabled until a compatible rendering backend is available and benchmarked.
