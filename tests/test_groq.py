import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from lucifer.backends.groq import GroqBackend
from lucifer.calibrate import calibrate, render_calibration
from lucifer.sandbox import SandboxExecutor
from lucifer.tasks import TASKS

KEY = "gsk_test_key_do_not_leak"


class Handler(BaseHTTPRequestHandler):
    fail_first = {"count": 1, "status": 429}
    seen_auth: list[str] = []

    def do_POST(self):
        Handler.seen_auth.append(self.headers.get("authorization", ""))
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        if Handler.fail_first["count"] > 0:
            Handler.fail_first["count"] -= 1
            self.send_response(Handler.fail_first["status"]); self.send_header("retry-after", "0"); self.send_header("content-length", "0"); self.end_headers()
            return
        prompt = body["messages"][0]["content"]
        task = next(t for t in TASKS if f"`{t.entry}`" in prompt.split("Write a Python function", 1)[-1][:80])
        data = json.dumps({"choices": [{"message": {"content": f"<think>x</think>```python\n{task.reference}\n```"}}], "usage": {"prompt_tokens": 20, "completion_tokens": 9}}).encode()
        self.send_response(200); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(data))); self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", KEY)
    Handler.fail_first = {"count": 1, "status": 429}
    Handler.seen_auth = []
    s = HTTPServer(("127.0.0.1", 0), Handler)
    Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}/v1/chat/completions"
    s.shutdown()


def test_key_must_come_from_the_environment(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        GroqBackend("m")


def test_retries_after_a_rate_limit_and_reads_usage(server):
    g = GroqBackend("m", base_url=server, min_interval_s=0).generate("Write a Python function `mean`.", seed=1)
    assert "<think>" not in g.text and g.prompt_tokens == 20 and g.completion_tokens == 9
    assert len(Handler.seen_auth) == 2 and all(a == f"Bearer {KEY}" for a in Handler.seen_auth)  # first call was rate limited, second worked


def test_a_hard_error_does_not_leak_the_key(server):
    Handler.fail_first = {"count": 5, "status": 401}
    with pytest.raises(RuntimeError) as err:
        GroqBackend("m", base_url=server, min_interval_s=0, max_retries=0).generate("x", seed=1)
    assert "401" in str(err.value) and KEY not in str(err.value)


def test_calibration_over_http(server, tmp_path):
    per_task = calibrate(GroqBackend("m", base_url=server, min_interval_s=0), SandboxExecutor(), (0,), tmp_path)
    assert len(per_task) == len(TASKS) and all(v == 1.0 for v in per_task.values())
    text = render_calibration(per_task, "groq:m")
    assert f"too easy (above 80%): {len(TASKS)}" in text and "must be made harder" in text
    assert (tmp_path / "per_task.json").exists()
