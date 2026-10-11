#!/usr/bin/env python3
"""Preflight checks for the PocketAI phone API and Computer Agent pairing.

Examples:
  python scripts/test_agent_connection.py --phone http://192.168.1.123:8080
  python scripts/test_agent_connection.py --phone http://192.168.1.123:8080 --token YOUR_TOKEN --send-ping

This script never prints the supplied token. It does not prove browser automation
or physical-device lifecycle behavior; those require the full acceptance steps.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def request(base: str, path: str, token: str | None = None, method: str = "GET", payload=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base.rstrip("/") + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"{type(exc).__name__}: {exc}") from exc


def parse_json(body: str, label: str):
    try:
        return json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} returned invalid JSON: {body[:200]!r}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phone", required=True, help="Phone API base URL, e.g. http://192.168.1.123:8080")
    parser.add_argument("--token", default="", help="Current per-installation pairing token")
    parser.add_argument("--send-ping", action="store_true", help="Queue a ping task (requires the PC agent to be running)")
    args = parser.parse_args()
    base = args.phone.rstrip("/")

    try:
        status, body = request(base, "/health")
        health = parse_json(body, "/health")
        if status != 200 or health.get("status") != "ok":
            raise RuntimeError(f"/health failed: HTTP {status}, body={body[:300]}")
        print(f"PASS /health: HTTP {status}; native_ready={health.get('native_ready')}; model_loaded={health.get('model_loaded')}")

        status, body = request(base, "/v1/agent/hello")
        if status != 401:
            raise RuntimeError(f"Unauthenticated /v1/agent/hello should return HTTP 401, got HTTP {status}: {body[:300]}")
        parse_json(body, "unauthenticated /v1/agent/hello")
        status, body = request(base, "/v1/agent/hello", token="invalid-acceptance-test-token")
        rejected = parse_json(body, "invalid-token /v1/agent/hello")
        if status != 401 or rejected.get("error") != "unauthorized":
            raise RuntimeError(f"Invalid token should return HTTP 401 with an unauthorized error, got HTTP {status}: {body[:300]}")
        print("PASS auth rejection: missing and incorrect tokens return valid JSON with HTTP 401")

        if not args.token:
            print("SKIP authenticated pairing and ping: pass --token to continue")
            return 0

        status, body = request(base, "/v1/agent/hello", token=args.token)
        hello = parse_json(body, "authenticated /v1/agent/hello")
        if status != 200 or hello.get("protocol") != "pocketai-agent-v1":
            raise RuntimeError(f"Authenticated hello failed: HTTP {status}, body={body[:300]}")
        print(f"PASS authenticated pairing endpoint: HTTP {status}; protocol={hello.get('protocol')}")

        if args.send_ping:
            import secrets
            task_id = "acceptance-ping-" + secrets.token_hex(6)
            status, body = request(
                base, "/v1/agent/tasks", token=args.token, method="POST",
                payload={"id": task_id, "action": "ping", "args": {"message": "PocketAI acceptance test"}},
            )
            queued = parse_json(body, "ping task submission")
            if status != 202 or not queued.get("queued") or queued.get("id") != task_id:
                raise RuntimeError(f"Ping task was not queued: HTTP {status}, body={body[:300]}")
            print(f"PASS ping task queued: {task_id}")
            print("VERIFY ON PC: the running agent must print this task and an ok=true result.")
            print("VERIFY ON PHONE: wait for Computer Agent connected and confirm the task result is shown.")
        else:
            print("SKIP ping queue test: add --send-ping while the PC agent is running")

    except RuntimeError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
