"""M7 browser POLICY layer over an abstract driver. A real browser driver is NOT built (no dependency was justified yet); tests use FakeDriver.
Enforces: exact-origin allow-list, redirect re-check, never filling sensitive fields, one-time approval for submitting, page text treated as untrusted data, audit.
Registered in docs/M7-PREREGISTRATION.md."""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from typing import Protocol
from urllib.parse import urlsplit

from .ledger import Ledger
from .tools import canonical

# Fail-closed: long tokens match anywhere ("creditcard", "card_number"), short ones only as whole words (so "company" is not "pan").
SENSITIVE_NAME = re.compile(r"pass(word|code)?|card|cvv|cvc|aadhaar|secret|token|iban|account|credential|(?<![a-z])(pan|otp|pin|ssn|pwd)(?![a-z])", re.I)
LONG_NUMBER = re.compile(r"(?:\d[ -]?){13,19}")
MAX_TEXT = 20_000


class Driver(Protocol):
    def navigate(self, url: str) -> str: ...
    def text(self) -> str: ...
    def fields(self) -> list[dict]: ...
    def fill(self, name: str, value: str) -> None: ...
    def submit(self) -> str: ...
    def reset(self) -> None: ...


def origin_of(url: str) -> str | None:
    """Exact origin 'scheme://host[:port]' or None if the URL is unsafe or not plain http(s)."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    if parts.scheme not in ("https", "http") or not parts.hostname or parts.username is not None or parts.password is not None:
        return None
    default = {"https": 443, "http": 80}[parts.scheme]
    return f"{parts.scheme}://{parts.hostname.lower()}" + (f":{port}" if port not in (None, default) else "")


class BrowserSession:
    def __init__(self, driver: Driver, allowed_origins: set[str], allow_http: bool = False) -> None:
        self.driver, self.allowed, self.allow_http = driver, set(allowed_origins), allow_http
        self.ledger = Ledger()
        self._approvals: dict[str, str] = {}
        self.url = ""

    def _audit(self, action: str, decision: str, reason: str, **extra) -> None:
        self.ledger.add(action, "browser", canonical({"action": action, "decision": decision, "reason": reason, **extra}), "browser", 0)

    def _allowed(self, url: str) -> bool:
        origin = origin_of(url)
        return origin is not None and origin in self.allowed and (origin.startswith("https://") or self.allow_http)

    def navigate(self, url: str) -> dict:
        origin = origin_of(url) or "invalid"
        if not self._allowed(url):
            self._audit("navigate", "denied", "origin not allowed", origin=origin)
            return {"ok": False, "error": "origin not allowed"}
        final = self.driver.navigate(url)
        if not self._allowed(final):
            self.driver.reset()
            self._audit("navigate", "denied", "redirect left the allow-list", origin=origin, final_origin=origin_of(final) or "invalid")
            return {"ok": False, "error": "redirect blocked"}
        self.url = final
        self._audit("navigate", "allowed", "ok", origin=origin)
        return {"ok": True, "url": final}

    def read(self) -> dict:
        """Page text is DATA from a third party. It is wrapped and never interpreted as an instruction or turned into a tool call."""
        if not self.url:
            return {"ok": False, "error": "no page"}
        self._audit("read", "allowed", "ok", origin=origin_of(self.url))
        return {"ok": True, "untrusted_content": self.driver.text()[:MAX_TEXT]}

    def fill(self, name: str, value: str) -> dict:
        field = next((f for f in self.driver.fields() if f.get("name") == name), None)
        if field is None:
            self._audit("fill", "denied", "no such field", field=str(name)[:32])
            return {"ok": False, "error": "no such field"}
        sensitive = field.get("type") in ("password", "hidden") or bool(SENSITIVE_NAME.search(name)) or bool(LONG_NUMBER.search(value))
        if sensitive:
            self._audit("fill", "denied", "sensitive field", field=name[:32])
            return {"ok": False, "error": "sensitive fields are filled by the user, never by the agent"}
        self.driver.fill(name, value)
        self._audit("fill", "allowed", "ok", field=name[:32], value_sha256=hashlib.sha256(value.encode()).hexdigest())
        return {"ok": True}

    def _form_hash(self, values: dict[str, str]) -> str:
        return hashlib.sha256(canonical({"url": self.url, "values": values}).encode()).hexdigest()

    def approve_submit(self, values: dict[str, str]) -> str:
        """A human step: a one-time approval bound to this page and these exact values."""
        token = secrets.token_hex(16)
        self._approvals[hashlib.sha256(token.encode()).hexdigest()] = self._form_hash(values)
        return token

    def submit(self, values: dict[str, str], approval: str | None) -> dict:
        bound = self._approvals.pop(hashlib.sha256((approval or "").encode()).hexdigest(), None)
        if bound is None or bound != self._form_hash(values):
            self._audit("submit", "denied", "approval required", origin=origin_of(self.url))
            return {"ok": False, "error": "a valid one-time approval for this exact form is required"}
        final = self.driver.submit()
        self._audit("submit", "allowed", "ok", origin=origin_of(self.url))
        if not self._allowed(final):
            self.driver.reset()
            return {"ok": False, "error": "redirect blocked"}
        self.url = final
        return {"ok": True, "url": final}


class FakeDriver:
    """Deterministic stand-in for tests: pages = {url: {"text", "fields", "redirect", "submit_to"}}."""

    def __init__(self, pages: dict[str, dict]) -> None:
        self.pages, self.page, self.filled, self.log = pages, None, {}, []

    def navigate(self, url: str) -> str:
        self.log.append(("navigate", url))
        page = self.pages.get(url, {"text": "", "fields": []})
        final = page.get("redirect", url)
        self.page, self.filled = self.pages.get(final, {"text": "", "fields": []}), {}
        return final

    def text(self) -> str:
        return self.page["text"]

    def fields(self) -> list[dict]:
        return self.page["fields"]

    def fill(self, name: str, value: str) -> None:
        self.log.append(("fill", name))
        self.filled[name] = value

    def submit(self) -> str:
        self.log.append(("submit", ""))
        return self.page.get("submit_to", "https://allowed.example")

    def reset(self) -> None:
        self.log.append(("reset", ""))
        self.page, self.filled = None, {}
