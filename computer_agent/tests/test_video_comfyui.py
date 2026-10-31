import json
import tempfile
import unittest
from pathlib import Path

from video_comfyui import ComfyUIClient, ComfyUIError


class ComfyUIClientTests(unittest.TestCase):
    def test_remote_http_is_rejected_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ComfyUIError):
                ComfyUIClient("http://192.168.1.20:8188", directory)

    def test_remote_requires_explicit_https_opt_in(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ComfyUIError):
                ComfyUIClient("http://gpu.example.com:8188", directory, allow_remote=True)
            client = ComfyUIClient("https://gpu.example.com", directory, allow_remote=True)
            self.assertEqual(client.base_url, "https://gpu.example.com")

    def test_workflow_path_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as directory:
            client = ComfyUIClient("http://127.0.0.1:8188", directory)
            with self.assertRaises(ComfyUIError):
                client._workflow_path("../outside.json")

    def test_prompt_node_must_be_clip_text_encode(self):
        workflow = {"1": {"class_type": "KSampler", "inputs": {"text": "old"}}}
        client = ComfyUIClient.__new__(ComfyUIClient)
        with self.assertRaises(ComfyUIError):
            client._set_text_node(workflow, "1", "new", "positive prompt")

    def test_submit_updates_only_explicit_text_nodes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflow = {
                "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "old positive"}},
                "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "old negative"}},
                "3": {"class_type": "KSampler", "inputs": {"seed": 7}},
            }
            (root / "test.json").write_text(json.dumps(workflow), encoding="utf-8")
            client = ComfyUIClient("http://127.0.0.1:8188", directory)
            captured = {}

            def fake_request(method, path, payload=None):
                captured["method"] = method
                captured["path"] = path
                captured["workflow"] = payload["prompt"]
                return {"prompt_id": "job-123", "number": 4, "node_errors": {}}

            client._request = fake_request
            result = client.submit("test.json", "a lion in the savannah", "blurry", "1", "2")
            self.assertTrue(result["queued"])
            self.assertEqual(result["prompt_id"], "job-123")
            self.assertEqual(captured["workflow"]["1"]["inputs"]["text"], "a lion in the savannah")
            self.assertEqual(captured["workflow"]["2"]["inputs"]["text"], "blurry")
            self.assertEqual(captured["workflow"]["3"]["inputs"]["seed"], 7)


if __name__ == "__main__":
    unittest.main()
