#!/usr/bin/env python3
"""Guarded HTTP client for an operator-configured ComfyUI instance."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


class ComfyUIError(RuntimeError):
    pass


class ComfyUIClient:
    def __init__(self, base_url: str, workflows_dir: str, allow_remote: bool = False,
                 timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.workflows_dir = Path(workflows_dir).expanduser().resolve()
        self.allow_remote = allow_remote
        self.timeout = timeout
        self._validate_base_url()

    def _validate_base_url(self) -> None:
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ComfyUIError("ComfyUI URL must be an absolute http:// or https:// URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ComfyUIError("ComfyUI URL must not contain credentials, query, or fragment")
        host = parsed.hostname.lower()
        local_hosts = {"localhost", "127.0.0.1", "::1"}
        if not self.allow_remote and host not in local_hosts:
            raise ComfyUIError("Remote ComfyUI is disabled; explicitly enable --allow-remote-comfyui")
        if self.allow_remote and host not in local_hosts and parsed.scheme != "https":
            raise ComfyUIError("Remote ComfyUI connections must use HTTPS")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = self.base_url + path
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise ComfyUIError(f"ComfyUI HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ComfyUIError(f"ComfyUI connection failed: {type(exc).__name__}: {exc}") from exc
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ComfyUIError("ComfyUI returned invalid JSON") from exc

    def status(self) -> dict[str, Any]:
        stats = self._request("GET", "/system_stats")
        queue = self._request("GET", "/queue")
        return {
            "available": True,
            "base_url": self.base_url,
            "system": stats,
            "queue": {
                "running": len(queue.get("queue_running", [])),
                "pending": len(queue.get("queue_pending", [])),
            },
        }

    def _workflow_path(self, filename: str) -> Path:
        candidate = Path(filename)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ComfyUIError("workflow_file must be a relative path inside the configured workflows directory")
        if candidate.suffix.lower() != ".json":
            raise ComfyUIError("workflow_file must reference a .json API workflow")
        root = self.workflows_dir
        path = (root / candidate).resolve()
        if not path.is_relative_to(root):
            raise ComfyUIError("workflow_file escapes the configured workflows directory")
        if not path.is_file():
            raise ComfyUIError(f"workflow file not found: {candidate.as_posix()}")
        return path

    @staticmethod
    def _set_text_node(workflow: dict[str, Any], node_id: str, text: str, label: str) -> None:
        node = workflow.get(str(node_id))
        if not isinstance(node, dict):
            raise ComfyUIError(f"{label} node {node_id!r} does not exist in the workflow")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict) or "text" not in inputs:
            raise ComfyUIError(f"{label} node {node_id!r} has no text input")
        node_type = str(node.get("class_type", ""))
        if not node_type.startswith("CLIPTextEncode"):
            raise ComfyUIError(f"{label} node {node_id!r} is not a CLIPTextEncode node")
        inputs["text"] = text

    def submit(self, workflow_file: str, prompt: str = "", negative_prompt: str = "",
               prompt_node_id: str = "", negative_prompt_node_id: str = "") -> dict[str, Any]:
        path = self._workflow_path(workflow_file)
        try:
            workflow = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ComfyUIError(f"Unable to read workflow JSON: {exc}") from exc
        if not isinstance(workflow, dict) or not workflow:
            raise ComfyUIError("Workflow must be a non-empty ComfyUI API-format JSON object")
        if prompt_node_id:
            self._set_text_node(workflow, prompt_node_id, prompt, "positive prompt")
        if negative_prompt_node_id:
            self._set_text_node(workflow, negative_prompt_node_id, negative_prompt, "negative prompt")
        result = self._request("POST", "/prompt", {"prompt": workflow})
        prompt_id = result.get("prompt_id")
        if not prompt_id:
            raise ComfyUIError("ComfyUI did not return a prompt_id; check workflow validation errors")
        return {
            "queued": True,
            "prompt_id": str(prompt_id),
            "queue_number": result.get("number"),
            "node_errors": result.get("node_errors", {}),
            "workflow_file": path.name,
        }

    def history(self, prompt_id: str) -> dict[str, Any]:
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        if not prompt_id or len(prompt_id) > 128 or any(ch not in allowed for ch in prompt_id):
            raise ComfyUIError("prompt_id contains invalid characters")
        result = self._request("GET", "/history/" + urllib.parse.quote(prompt_id, safe=""))
        record = result.get(prompt_id) if isinstance(result, dict) else None
        if not isinstance(record, dict):
            return {"found": False, "prompt_id": prompt_id}
        status = record.get("status") or {}
        outputs = []
        for node_id, node_output in (record.get("outputs") or {}).items():
            if not isinstance(node_output, dict):
                continue
            for kind in ("videos", "gifs", "images"):
                for item in node_output.get(kind, []) or []:
                    if isinstance(item, dict) and item.get("filename"):
                        outputs.append({
                            "node_id": str(node_id), "kind": kind,
                            "filename": item.get("filename"),
                            "subfolder": item.get("subfolder", ""),
                            "type": item.get("type", "output"),
                        })
        return {
            "found": True, "prompt_id": prompt_id,
            "completed": bool(status.get("completed", False)),
            "status": status.get("status_str", "unknown"),
            "outputs": outputs,
        }
