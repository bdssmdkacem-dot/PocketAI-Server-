#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import time
import urllib.error
import urllib.request
from pathlib import Path


class PocketAIComputerAgent:
    def __init__(self, phone: str, token: str, interval: float = 0.7, headless: bool = False) -> None:
        self.phone = phone.rstrip("/")
        self.token = token
        self.interval = max(0.2, interval)
        self.agent_name = platform.node() or "computer"
        self.headless = headless
        self.browser = None
        self.page = None
        self._playwright = None
        self.last_error = None

    def request(self, method, path, payload=None, timeout=8.0):
        data = json.dumps(payload).encode() if payload is not None else None
        headers = {"Authorization": "Bearer " + self.token, "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.phone + path, data=data, headers=headers, method=method)
        return urllib.request.urlopen(req, timeout=timeout)

    def hello(self):
        try:
            with self.request("GET", "/v1/agent/hello") as response:
                self.last_error = None if response.status == 200 else f"HTTP {response.status}"
                return response.status == 200
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace").strip()
            except Exception:
                body = ""
            self.last_error = f"HTTP {exc.code}: {body[:300]}" if body else f"HTTP {exc.code}"
            return False
        except urllib.error.URLError as exc:
            self.last_error = f"Network error: {exc.reason}"
            return False
        except (TimeoutError, OSError) as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return False

    def poll(self):
        try:
            with self.request("GET", "/v1/agent/tasks/next", timeout=30) as response:
                if response.status == 204:
                    return None
                return json.loads(response.read().decode())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            return None

    def browser_runtime_status(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {
                "available": False,
                "error_code": "PLAYWRIGHT_MISSING",
                "message": "Playwright is not installed"
            }

        try:
            playwright = sync_playwright().start()
            try:
                executable = playwright.chromium.executable_path
                if not Path(executable).exists():
                    return {
                        "available": False,
                        "error_code": "CHROMIUM_MISSING",
                        "message": "Playwright is installed but Chromium is not installed",
                        "executable": executable,
                    }
                return {
                    "available": True,
                    "error_code": None,
                    "message": "Chromium runtime ready",
                    "executable": executable,
                }
            finally:
                playwright.stop()
        except Exception as exc:
            return {
                "available": False,
                "error_code": "BROWSER_RUNTIME_ERROR",
                "message": f"{type(exc).__name__}: {exc}",
            }

    def browser_start(self):
        if self.page is not None:
            return
        status = self.browser_runtime_status()
        if not status["available"]:
            raise RuntimeError(
                f'{status["error_code"]}: {status["message"]}'
            )
        from playwright.sync_api import sync_playwright
        self._playwright = sync_playwright().start()
        try:
            self.browser = self._playwright.chromium.launch(headless=self.headless)
            context = self.browser.new_context(viewport={"width": 1440, "height": 900})
            self.page = context.new_page()
        except Exception:
            self.browser_stop()
            raise

    def browser_stop(self):
        if self.browser is not None:
            self.browser.close()
        self.browser = None
        self.page = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None

    def browser_read(self):
        self.browser_start()
        body = self.page.locator("body").inner_text(timeout=10000)
        return {"url": self.page.url, "title": self.page.title(), "text": body[:12000]}

    def execute(self, task):
        task_id = str(task.get("id", "unknown"))
        action = str(task.get("action", "")).strip()
        args = task.get("args") or {}

        if action == "ping":
            return {"id": task_id, "ok": True, "action": action, "computer": self.agent_name,
                    "platform": platform.platform(), "message": str(args.get("message", "pong"))}

        if action == "agent.status":
            return {
                "id": task_id,
                "ok": True,
                "action": action,
                "computer": self.agent_name,
                "platform": platform.platform(),
                "browser": self.browser_runtime_status(),
            }

        if action == "browser.open":
            url = str(args.get("url", "")).strip()
            if not url.startswith(("http://", "https://")):
                return {"id": task_id, "ok": False, "action": action, "error_code": "INVALID_URL",
                        "error": "url must use http:// or https://"}
            self.browser_start()
            self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return {"id": task_id, "ok": True, "action": action, **self.browser_read()}

        if action == "browser.search":
            query = str(args.get("query", "")).strip()
            if not query:
                return {"id": task_id, "ok": False, "action": action, "error_code": "INVALID_QUERY",
                        "error": "query is required"}
            from urllib.parse import quote_plus
            self.browser_start()
            self.page.goto("https://www.google.com/search?q=" + quote_plus(query),
                           wait_until="domcontentloaded", timeout=30000)
            return {"id": task_id, "ok": True, "action": action, "query": query, **self.browser_read()}

        if action == "browser.read":
            return {"id": task_id, "ok": True, "action": action, **self.browser_read()}

        if action == "browser.click":
            selector = str(args.get("selector", "")).strip()
            if not selector:
                return {"id": task_id, "ok": False, "action": action, "error_code": "INVALID_SELECTOR",
                        "error": "selector is required"}
            self.browser_start()
            self.page.locator(selector).first.click(timeout=15000)
            self.page.wait_for_load_state("domcontentloaded", timeout=10000)
            return {"id": task_id, "ok": True, "action": action, **self.browser_read()}

        if action == "browser.type":
            selector = str(args.get("selector", "")).strip()
            text = str(args.get("text", ""))
            if not selector:
                return {"id": task_id, "ok": False, "action": action, "error_code": "INVALID_SELECTOR",
                        "error": "selector is required"}
            self.browser_start()
            self.page.locator(selector).first.fill(text, timeout=15000)
            return {"id": task_id, "ok": True, "action": action, "url": self.page.url}

        if action == "browser.scroll":
            amount = int(args.get("amount", 700))
            self.browser_start()
            self.page.mouse.wheel(0, amount)
            self.page.wait_for_timeout(300)
            return {"id": task_id, "ok": True, "action": action, **self.browser_read()}

        if action == "browser.back":
            self.browser_start()
            self.page.go_back(wait_until="domcontentloaded", timeout=15000)
            return {"id": task_id, "ok": True, "action": action, **self.browser_read()}

        if action == "browser.forward":
            self.browser_start()
            self.page.go_forward(wait_until="domcontentloaded", timeout=15000)
            return {"id": task_id, "ok": True, "action": action, **self.browser_read()}

        if action == "browser.screenshot":
            self.browser_start()
            output = Path(str(args.get("path", "pocketai_screenshot.png"))).expanduser().resolve()
            self.page.screenshot(path=str(output), full_page=True)
            return {"id": task_id, "ok": True, "action": action, "path": str(output), "url": self.page.url}

        if action == "browser.close":
            self.browser_stop()
            return {"id": task_id, "ok": True, "action": action}

        return {"id": task_id, "ok": False, "action": action, "error_code": "ACTION_NOT_ENABLED",
                "error": "action not enabled"}

    def report(self, result):
        try:
            with self.request("POST", "/v1/agent/tasks/result", result, timeout=8) as response:
                response.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            pass

    def run(self):
        print("PocketAI Computer Agent: " + self.agent_name)
        print("Phone: " + self.phone)
        print("Browser actions: open, search, read, click, type, scroll, back, forward, screenshot")
        connected = False
        last_error_printed = None
        while True:
            now = self.hello()
            if now != connected:
                connected = now
                if connected:
                    print("Connected to PocketAI phone.")
                else:
                    print("Phone connection lost.")
                    if self.last_error:
                        print("Connection error:", self.last_error)
                    last_error_printed = self.last_error
            elif not connected and self.last_error != last_error_printed:
                print("Connection error:", self.last_error or "unknown error")
                last_error_printed = self.last_error
            if connected:
                task = self.poll()
                if task:
                    print("Task:", task.get("id"), "action=", task.get("action"))
                    try:
                        result = self.execute(task)
                    except Exception as exc:
                        result = {"id": str(task.get("id", "unknown")), "ok": False,
                                  "action": str(task.get("action", "")),
                                  "error_code": "EXECUTION_ERROR",
                                  "error": f"{type(exc).__name__}: {exc}"}
                    self.report(result)
                    print("Result:", json.dumps(result, ensure_ascii=False))
            time.sleep(self.interval)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phone", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--interval", type=float, default=0.7)
    parser.add_argument("--headless", action="store_true", help="Run Chromium without showing a browser window")
    args = parser.parse_args()
    PocketAIComputerAgent(args.phone, args.token, args.interval, args.headless).run()


if __name__ == "__main__":
    main()
