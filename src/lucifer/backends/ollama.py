"""A real model served by Ollama (https://ollama.com). Temperature is low but not zero, so the seeds can differ; the model tag is pinned
by whoever runs it and is written into the results."""
from __future__ import annotations

import json
import time
import urllib.request

from ..tasks import Task
from .base import Generation


class OllamaBackend:
    def __init__(self, model: str, host: str = "http://127.0.0.1:11434", temperature: float = 0.3, timeout_s: float = 300.0) -> None:
        self.model, self.host, self.temperature, self.timeout_s = model, host.rstrip("/"), temperature, timeout_s
        self.name = f"ollama:{model}"

    def generate(self, prompt: str, *, seed: int, task: Task | None = None) -> Generation:
        body = json.dumps({"model": self.model, "stream": False, "messages": [{"role": "user", "content": prompt}],
                           "options": {"temperature": self.temperature, "seed": seed}}).encode()
        req = urllib.request.Request(f"{self.host}/api/chat", data=body, headers={"content-type": "application/json"})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            data = json.loads(resp.read())
        text = (data.get("message") or {}).get("content", "")
        import re
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)  # reasoning models: keep only the answer
        return Generation(text, int(data.get("prompt_eval_count", len(prompt) // 4)), int(data.get("eval_count", len(text) // 4)), (time.perf_counter() - t0) * 1000)
