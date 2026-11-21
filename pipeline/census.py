"""Census Data API helpers."""

from __future__ import annotations

import os
from typing import Any, Iterable

from .http import Fetcher, FetchError

BASE = "https://api.census.gov/data"
MISSING = {"-666666666", "-999999999", "-888888888", "-555555555", "-333333333", "-222222222", "null", "None", ""}


def _num(value: Any) -> float | None:
    if value is None:
        return None
    s = str(value)
    if s in MISSING:
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    if f <= -222222222:
        return None
    return f


def query(
    fetcher: Fetcher,
    path: str,
    get: Iterable[str],
    for_: str,
    in_: str | None = None,
) -> list[dict[str, Any]]:
    """Run a Census API query, splitting into chunks of 48 variables.

    Returns one dict per geography with numeric values parsed and the
    geography columns kept as strings.
    """
    variables = [v for v in dict.fromkeys(get) if v != "NAME"]
    chunks = [variables[i : i + 48] for i in range(0, len(variables), 48)] or [[]]
    merged: dict[tuple, dict[str, Any]] = {}
    geo_cols: list[str] = []
    for chunk in chunks:
        params = {"get": ",".join(["NAME", *chunk]), "for": for_}
        if in_:
            params["in"] = in_
        key = os.environ.get("CENSUS_API_KEY")
        if key:
            params["key"] = key
        raw = fetcher.fetch(f"{BASE}/{path}", params=params, ok_statuses=(200, 204))
        if not raw.strip():
            return []
        import json

        rows = json.loads(raw.decode("utf-8"))
        header, body = rows[0], rows[1:]
        geo_cols = [h for h in header if h != "NAME" and h not in chunk]
        for row in body:
            rec = dict(zip(header, row))
            k = tuple(rec[c] for c in geo_cols)
            target = merged.setdefault(k, {c: rec[c] for c in geo_cols} | {"NAME": rec["NAME"]})
            for v in chunk:
                target[v] = _num(rec.get(v))
    return list(merged.values())


def group_labels(fetcher: Fetcher, path: str, group: str) -> dict[str, str]:
    data = fetcher.json(f"{BASE}/{path}/groups/{group}.json")
    return {k: v.get("label", "") for k, v in data.get("variables", {}).items()}


def normalize_label(label: str) -> str:
    parts = [p.replace(":", "").strip().lower() for p in label.split("!!")]
    return "!!".join(p for p in parts if p)


def label_matches(label: str, expected: str) -> bool:
    norm = normalize_label(label)
    exp = expected.lower()
    if exp.startswith("="):
        return norm == exp[1:]
    return exp in norm


def first_available(fetcher: Fetcher, candidates: list[int], probe) -> int:
    """Return the first year for which probe(year) succeeds."""
    errors = []
    for year in candidates:
        try:
            if probe(year):
                return year
        except FetchError as exc:
            errors.append(f"{year}: {exc}")
    raise FetchError("No available vintage. " + "; ".join(errors))
