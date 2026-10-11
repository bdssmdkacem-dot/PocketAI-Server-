# PocketAI Computer Agent

The phone is the controller and local AI runtime. The Windows/Linux computer runs this agent and executes the currently implemented task actions.

## LAN setup

1. Install Python 3.9+ on the computer.
2. In the repository root, install the browser dependency:

   ```powershell
   python -m pip install -r computer_agent/requirements.txt
   python -m playwright install chromium
   ```

3. Connect the phone and computer to the same trusted Wi-Fi/LAN.
4. Start PocketAI on the phone. Confirm the local API is running and copy its current LAN address and per-installation pairing token.
5. From the repository root on the computer, run:

   ```powershell
   python computer_agent/agent.py --phone http://PHONE_IP:8080 --token YOUR_CURRENT_TOKEN
   ```

6. The phone should show **Computer Agent connected**. Keep the agent terminal open while testing.

Do not paste the token into issues, logs, screenshots, source code, or public chats. If a token was exposed, clear the app's data/reinstall to generate a new per-installation token, then pair again. Do not expose port 8080 to the public internet or configure port forwarding.

## Connection preflight

From the repository root, run the new diagnostic script. It checks health, validates that missing authentication returns a well-formed HTTP 401 response, and (when a token is supplied) verifies the authenticated agent hello endpoint:

```powershell
python scripts/test_agent_connection.py --phone http://PHONE_IP:8080 --token YOUR_CURRENT_TOKEN
```

With the computer agent already running, add `--send-ping` to queue a unique ping task:

```powershell
python scripts/test_agent_connection.py --phone http://PHONE_IP:8080 --token YOUR_CURRENT_TOKEN --send-ping
```

A queued task is not proof of execution. Acceptance requires the PC terminal to print the matching task ID and an `ok=true` result, and the phone UI to reflect the agent connection/task result.

## Implemented actions

- `ping` — reports the computer name and platform.
- `agent.status` — reports agent and Playwright/Chromium runtime status.
- `browser.open`, `browser.search`, `browser.read`
- `browser.click`, `browser.type`, `browser.scroll`
- `browser.back`, `browser.forward`, `browser.screenshot`, `browser.close`

Browser actions require Playwright and its Chromium runtime. Use only systems and accounts you are authorized to access. Do not automate consequential actions such as purchases, financial operations, account changes, deletion, or sending messages without explicit user confirmation and a suitable permission system.

## Protocol endpoints

- `GET /health` — unauthenticated health status only.
- `GET /v1/agent/hello` — authenticated agent handshake.
- `GET /v1/agent/tasks/next` — authenticated task polling.
- `POST /v1/agent/tasks` — authenticated task submission.
- `POST /v1/agent/tasks/result` — authenticated task result reporting.
- `GET /v1/agent/tasks/results` — reads and drains completed results.

All `/v1/*` endpoints require the current bearer token. The phone and computer must be on a trusted LAN. The token is a per-installation secret, not a production-grade pairing UX; token rotation, revocation, TLS, permission prompts, audit logs, cancellation, and task-result verification remain part of commercial hardening.

## Acceptance checklist

- [ ] Install and launch the current APK on the target Android phone.
- [ ] `/health` returns HTTP 200 and native/model status matches the actual app state.
- [ ] Missing or incorrect token returns HTTP 401 with valid JSON.
- [ ] Correct token completes `/v1/agent/hello` with protocol `pocketai-agent-v1`.
- [ ] Phone reports the agent connected while the PC process is alive.
- [ ] A ping task appears on the PC and returns `ok=true` to the phone.
- [ ] `agent.status` reports Playwright and Chromium available.
- [ ] A harmless browser-open/search/read test succeeds and its result is visible.
- [ ] Stop/restart the phone server and repeat the handshake.
- [ ] Close/reopen the Android UI and test server/agent lifecycle behavior on the actual phone.

A CI build alone does not satisfy these acceptance checks. Do not create production signing keys or claim commercial readiness until the real-device and computer tests pass.
