# PocketAI Computer Agent

The phone is the controller and local AI brain. The computer runs this small agent and executes approved tasks.

## LAN MVP

1. Install Python 3.9+ on the computer.
2. Connect phone and computer to the same Wi-Fi/LAN.
3. Start PocketAI on the phone and note the LAN address and Pairing token.
4. Run:

    python computer_agent/agent.py --phone http://PHONE_IP:8080 --token YOUR_TOKEN

5. The phone should show Computer Agent connected.
6. Tap Send test task to Computer Agent. The computer should print the received ping task and result.

## Security

The token is a random per-installation bearer token stored on the phone. All /v1/* endpoints except /health require the token. Do not expose port 8080 to the public internet or port-forward it.

## Protocol

- GET /v1/agent/hello
- GET /v1/agent/tasks/next
- POST /v1/agent/tasks
- POST /v1/agent/tasks/result

The current allow-list contains only ping. Browser, filesystem, terminal, screenshot, and desktop-control tools will be added as separate capabilities with explicit permissions.
