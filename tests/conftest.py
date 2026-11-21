import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class FakeFetcher:
    """Answers requests from a table of (regex, response) pairs."""

    def __init__(self, routes):
        self.routes = [(re.compile(p), r) for p, r in routes]
        self.log = []
        self.calls = []

    def fetch(self, url, *, params=None, method="GET", json_body=None, **kw):
        import urllib.parse

        full = url + ("?" + urllib.parse.urlencode(params) if params else "")
        self.calls.append((method, full, json_body))
        for pat, resp in self.routes:
            if pat.search(full):
                body = resp(full, json_body) if callable(resp) else resp
                if isinstance(body, Exception):
                    raise body
                if isinstance(body, (dict, list)):
                    return json.dumps(body).encode()
                return body.encode() if isinstance(body, str) else body
        from pipeline.http import FetchError

        raise FetchError(f"no route for {full}")

    def json(self, url, **kw):
        return json.loads(self.fetch(url, **kw).decode())

    def text(self, url, encoding="utf-8", **kw):
        return self.fetch(url, **kw).decode(encoding)


@pytest.fixture
def district():
    from pipeline import config

    return config.load("wi-07")
