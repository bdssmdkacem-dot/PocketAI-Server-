# PocketAI Computer Agent

The phone is the controller and local AI runtime. The Windows/Linux computer runs this agent and executes the currently implemented task actions.

## LAN setup

1. Install Python 3.10+ on the computer.
2. Install the optional browser dependency when browser automation is needed:

    python -m pip install playwright
    python -m playwright install chromium

3. Connect the phone and computer to the same trusted Wi-Fi/LAN.
4. Start PocketAI on the phone. Confirm the local API is running and copy its current LAN address and per-installation pairing token.
5. From the repository root on the computer, run:

    python computer_agent/agent.py --phone http://PHONE_IP:8080 --token YOUR_CURRENT_TOKEN

6. The phone should show Computer Agent connected. Keep the agent terminal open while testing.

Do not paste the token into issues, logs, screenshots, source code, or public chats. If a token was exposed, clear the app's data/reinstall to generate a new per-installation token, then pair again. Do not expose port 8080 to the public internet or configure port forwarding.

## Optional ComfyUI video worker

PocketAI's Android app remains the controller and local LLM runtime. Video inference runs on the paired Windows/Linux computer (or an explicitly configured HTTPS GPU endpoint), not inside the Android APK and not inside llama.cpp.

1. Install ComfyUI on the paired computer and install the video model/workflow required by your GPU. Model weights are not included in this repository.
2. Start ComfyUI on the same computer, preferably bound to 127.0.0.1:8188.
3. Export a ComfyUI API-format workflow JSON and place it under computer_agent/workflows/.
4. Start the PocketAI computer agent with:

    python computer_agent/agent.py --phone http://PHONE_IP:8080 --token YOUR_CURRENT_TOKEN --comfyui-url http://127.0.0.1:8188

5. Check availability with the video.comfyui.status task.
6. Submit a workflow with video.comfyui.submit, passing a relative workflow_file. To replace text prompts, provide the exact positive and negative CLIPTextEncode node IDs from that workflow. The workflow must be tested in ComfyUI before using it from PocketAI.
7. Inspect completion with video.comfyui.history and the returned prompt_id.

For a remote GPU endpoint, use HTTPS and explicitly add --allow-remote-comfyui. The endpoint is configured by the computer-agent operator; task payloads cannot change the destination URL. Do not expose an unauthenticated ComfyUI instance to the public internet. Use a private tunnel/VPN or an authenticated gateway for remote access.

The first integration intentionally submits and tracks jobs; it does not claim to download or edit model weights, invent model-specific workflows, or guarantee generation speed. Video generation quality and performance depend on the selected model, workflow, GPU VRAM, and model license.

## Implemented actions

- ping — reports the computer name and platform.
- agent.status — reports agent and optional video-worker configuration.
- browser.open, browser.search, browser.read
- browser.click, browser.type, browser.scroll
- browser.back, browser.forward, browser.screenshot, browser.close
- video.comfyui.status — checks the configured ComfyUI service and queue.
- video.comfyui.submit — submits a trusted API-format workflow from the configured workflows directory.
- video.comfyui.history — retrieves status and output metadata for a ComfyUI prompt ID.

Browser actions require Playwright and its Chromium runtime. Video actions require ComfyUI to be installed and running separately. Use only systems and accounts you are authorized to access. Do not automate consequential actions without explicit user confirmation and a suitable permission system.

## Protocol endpoints

- GET /health — unauthenticated health status only.
- GET /v1/agent/hello — authenticated agent handshake.
- GET /v1/agent/tasks/next — authenticated task polling.
- POST /v1/agent/tasks — authenticated task submission.
- POST /v1/agent/tasks/result — authenticated task result reporting.
- GET /v1/agent/tasks/results — reads and drains completed results.

All /v1/* endpoints require the current bearer token. The phone and computer must be on a trusted LAN. The token is a per-installation secret, not a production-grade pairing UX; token rotation, revocation, TLS, permission prompts, audit logs, cancellation, and task-result verification remain part of commercial hardening.

## Acceptance checklist

- [ ] Install and launch the current APK on the target Android phone.
- [ ] /health returns HTTP 200 and native/model status matches the actual app state.
- [ ] Missing or incorrect token returns HTTP 401 with valid JSON.
- [ ] Correct token completes /v1/agent/hello with protocol pocketai-agent-v1.
- [ ] Phone reports the agent connected while the PC process is alive.
- [ ] A ping task appears on the PC and returns ok=true to the phone.
- [ ] agent.status reports Playwright and Chromium available when installed.
- [ ] A harmless browser-open/search/read test succeeds and its result is visible.
- [ ] ComfyUI status is reachable from the paired computer.
- [ ] A validated API workflow can be queued and its prompt ID returned.
- [ ] Workflow history reports completion and generated output metadata.
- [ ] Stop/restart the phone server and repeat the handshake.
- [ ] Close/reopen the Android UI and test server/agent lifecycle behavior on the actual phone.

A CI build alone does not satisfy these acceptance checks. Do not create production signing keys or claim commercial readiness until the real-device and computer tests pass.
