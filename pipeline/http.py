"""Polite, cached HTTP for public data sources.

Every request is logged (URL with any API key removed, status, size,
SHA-256, time) so the manifest can show exactly what was read.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

USER_AGENT = (
    "wi7-atlas/1.0 (+https://github.com/Normansrule/wi7-atlas; "
    "nonpartisan public-data pipeline)"
)
SECRET_PARAMS = re.compile(r"(api_key|key|registrationkey|registration_key)=[^&]+", re.I)


def redact(url: str) -> str:
    return SECRET_PARAMS.sub(lambda m: f"{m.group(1)}=REDACTED", url)


@dataclass
class FetchRecord:
    url: str
    status: int
    bytes: int
    sha256: str
    fetched_at: str
    from_cache: bool


class FetchError(RuntimeError):
    pass


class Fetcher:
    def __init__(self, cache_dir: str | os.PathLike | None = None, *, delay: float = 0.25):
        self.cache_dir = pathlib.Path(cache_dir or os.environ.get("ATLAS_CACHE", ".cache/http"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
        self.log: list[FetchRecord] = []
        self.use_cache = os.environ.get("ATLAS_USE_CACHE", "1") != "0"

    def _key(self, method: str, url: str, body: Any) -> pathlib.Path:
        raw = method + " " + url + " " + (json.dumps(body, sort_keys=True) if body is not None else "")
        return self.cache_dir / hashlib.sha256(raw.encode()).hexdigest()

    def fetch(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        method: str = "GET",
        json_body: Any = None,
        headers: dict[str, str] | None = None,
        retries: int = 4,
        timeout: int = 90,
        ok_statuses: tuple[int, ...] = (200,),
    ) -> bytes:
        req = requests.Request(method, url, params=params, json=json_body, headers=headers)
        prepared = self.session.prepare_request(req)
        full_url = prepared.url or url
        cache_path = self._key(method, full_url, json_body)
        if self.use_cache and cache_path.exists():
            content = cache_path.read_bytes()
            self._record(full_url, 200, content, from_cache=True)
            return content
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                resp = self.session.send(prepared, timeout=timeout)
                if resp.status_code in ok_statuses:
                    content = resp.content
                    cache_path.write_bytes(content)
                    self._record(full_url, resp.status_code, content, from_cache=False)
                    time.sleep(self.delay)
                    return content
                if resp.status_code in (429, 500, 502, 503, 504):
                    wait = float(resp.headers.get("Retry-After", 2 ** attempt * 2))
                    time.sleep(min(wait, 60))
                    last_error = FetchError(f"HTTP {resp.status_code} for {redact(full_url)}")
                    continue
                raise FetchError(f"HTTP {resp.status_code} for {redact(full_url)}: {resp.text[:200]}")
            except requests.RequestException as exc:  # network errors: retry
                last_error = exc
                time.sleep(2 ** attempt)
        raise FetchError(f"Gave up on {redact(full_url)}: {last_error}")

    def json(self, url: str, **kwargs: Any) -> Any:
        return json.loads(self.fetch(url, **kwargs).decode("utf-8"))

    def text(self, url: str, encoding: str = "utf-8", **kwargs: Any) -> str:
        return self.fetch(url, **kwargs).decode(encoding)

    def _record(self, url: str, status: int, content: bytes, *, from_cache: bool) -> None:
        self.log.append(
            FetchRecord(
                url=redact(url),
                status=status,
                bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                from_cache=from_cache,
            )
        )
