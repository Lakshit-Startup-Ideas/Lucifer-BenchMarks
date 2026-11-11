"""Groq's hosted open-weight models (OpenAI-compatible API, https://console.groq.com).

The API key is read ONLY from the environment variable GROQ_API_KEY, never from a file or the command line, so it cannot end up in
the repo, in shell history or in saved results. Hosted models can change under the same name, so the exact model id and the time of
the run are written into the results; for the final claim, prefer a model you run yourself.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request

from ..tasks import Task
from .base import Generation

API = "https://api.groq.com/openai/v1/chat/completions"


class GroqBackend:
    def __init__(self, model: str, *, temperature: float = 0.3, min_interval_s: float = 2.2, max_retries: int = 6,
                 reasoning_effort: str | None = None, base_url: str = API, timeout_s: float = 120.0) -> None:
        key = os.environ.get("GROQ_API_KEY", "")
        if not key:
            raise RuntimeError("Set GROQ_API_KEY in your shell (export GROQ_API_KEY=...) before using --backend groq.")
        self._key = key
        self.model, self.temperature, self.min_interval_s, self.max_retries = model, temperature, min_interval_s, max_retries
        self.reasoning_effort, self.base_url, self.timeout_s = reasoning_effort, base_url, timeout_s
        self.name = f"groq:{model}"
        self._last = 0.0
        self._lock = threading.Lock()

    def _wait_turn(self) -> None:
        with self._lock:  # stay under the free tier's requests-per-minute limit
            wait = self._last + self.min_interval_s - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()

    def generate(self, prompt: str, *, seed: int, task: Task | None = None) -> Generation:
        payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": self.temperature, "seed": seed, "max_completion_tokens": 2048}
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        body = json.dumps(payload).encode()
        t0 = time.perf_counter()
        for attempt in range(self.max_retries + 1):
            self._wait_turn()
            req = urllib.request.Request(self.base_url, data=body, headers={"content-type": "application/json", "authorization": f"Bearer {self._key}", "user-agent": "lucifer-lab/0.1"})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    data = json.loads(resp.read())
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503) and attempt < self.max_retries:
                    retry_after = e.headers.get("retry-after")
                    time.sleep(min(60.0, float(retry_after)) if retry_after and retry_after.replace(".", "", 1).isdigit() else min(30.0, 2.0 ** attempt))
                    continue
                detail = e.read().decode(errors="replace")[:200].replace(self._key, "***")
                raise RuntimeError(f"Groq HTTP {e.code}: {detail}") from None
        message = (data.get("choices") or [{}])[0].get("message") or {}
        text = re.sub(r"<think>.*?</think>", "", message.get("content") or "", flags=re.DOTALL | re.IGNORECASE)
        usage = data.get("usage") or {}
        return Generation(text, int(usage.get("prompt_tokens", len(prompt) // 4)), int(usage.get("completion_tokens", len(text) // 4)), (time.perf_counter() - t0) * 1000)
