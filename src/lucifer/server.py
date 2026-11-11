"""A small local web server for the dashboard: a JSON API over the saved runs, plus the static front end. Bound to 127.0.0.1 only."""
from __future__ import annotations

import json
import mimetypes
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .insights import Run, list_runs, load_run, memory_view, summary, trace_list

WEB = Path(__file__).parent / "web"
_SAFE_ID = re.compile(r"^[\w.\-]+$")


class Store:
    """Loads a run once and reloads it if its files change."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._cache: dict[str, tuple[float, Run, dict | None]] = {}
        self._lock = threading.Lock()

    def run(self, run_id: str) -> Run | None:
        if not _SAFE_ID.match(run_id):
            return None
        folder = self.root / run_id
        if not (folder / "rows.json").exists():
            return None
        stamp = max(f.stat().st_mtime for f in folder.iterdir() if f.is_file())
        with self._lock:
            hit = self._cache.get(run_id)
            if not hit or hit[0] != stamp:
                self._cache[run_id] = (stamp, load_run(folder), None)
            return self._cache[run_id][1]

    def summary(self, run_id: str) -> dict | None:
        run = self.run(run_id)
        if run is None:
            return None
        with self._lock:
            stamp, r, cached = self._cache[run_id]
            if cached is None:
                cached = summary(r)
                self._cache[run_id] = (stamp, r, cached)
            return cached


def make_handler(store: Store):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, data, status=200):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.send_header("cache-control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _static(self, rel: str):
            target = (WEB / rel).resolve()
            if WEB.resolve() not in target.parents and target != WEB.resolve():
                return self._json({"error": "not found"}, 404)
            if target.is_dir():
                target = target / "index.html"
            if not target.exists():
                return self._json({"error": "not found"}, 404)
            body = target.read_bytes()
            self.send_response(200)
            self.send_header("content-type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
            self.send_header("content-length", str(len(body)))
            self.send_header("cache-control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            path = unquote(url.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            if not path.startswith("/api/"):
                return self._static(path.lstrip("/"))
            parts = [p for p in path.split("/") if p][1:]
            if parts == ["runs"]:
                return self._json(list_runs(store.root))
            if len(parts) >= 3 and parts[0] == "runs":
                run = store.run(parts[1])
                if run is None:
                    return self._json({"error": "unknown run"}, 404)
                what = parts[2]
                if what == "summary" and len(parts) == 3:
                    return self._json(store.summary(parts[1]))
                if what == "traces" and len(parts) == 3:
                    seed = int(q["seed"]) if q.get("seed", "").lstrip("-").isdigit() else None
                    return self._json(trace_list(run, condition=q.get("condition"), seed=seed, phase=q.get("phase"), task=q.get("task"),
                                                 failed=q.get("failed") == "1", q=q.get("q", ""), limit=min(int(q.get("limit", 200)), 1000), offset=int(q.get("offset", 0))))
                if what == "traces" and len(parts) >= 4:
                    spans = run.trace("/".join(parts[3:]))
                    return self._json({"trace_id": "/".join(parts[3:]), "spans": spans}) if spans else self._json({"error": "unknown trace"}, 404)
                if what == "memory":
                    seed = int(q["seed"]) if q.get("seed", "").lstrip("-").isdigit() else None
                    return self._json(memory_view(run, q.get("condition"), seed))
            return self._json({"error": "not found"}, 404)

        def log_message(self, *a):
            pass

    return Handler


def serve(root: Path, port: int = 8765, open_browser: bool = True) -> None:
    store = Store(root)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(store))
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Lucifer dashboard on {url}  (results folder: {root})  Ctrl+C to stop")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
