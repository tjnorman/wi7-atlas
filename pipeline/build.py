"""Run every source, keep what worked, check it, and write the outputs."""

from __future__ import annotations

import json
import pathlib
import traceback
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Callable

import yaml

from . import checks as checks_mod
from .config import DATA_ROOT, ROOT, District
from .http import Fetcher
from .provenance import dataset
from .sources import acs, elections, fec, geography, laus, legislators, pep, qcew, usaspending, votes

ORDER = ["geography", "legislators", "acs", "pep", "laus", "qcew", "usaspending", "elections", "fec", "votes"]


def data_dir(d: District) -> pathlib.Path:
    return DATA_ROOT / d.id


def load_json(path: pathlib.Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_json(path: pathlib.Path, obj: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":")) if compact else json.dumps(obj, ensure_ascii=False, indent=1)
    path.write_text(text + "\n", encoding="utf-8")


def load_notes() -> list[dict]:
    path = ROOT / "data" / "curated" / "notes.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    notes = raw.get("notes", [])
    for n in notes:
        for k in ("verified_on", "review_by"):
            if k in n:
                n[k] = str(n[k])
    return notes


def run(d: District, only: list[str] | None = None) -> dict:
    out = data_dir(d)
    out.mkdir(parents=True, exist_ok=True)
    f = Fetcher()
    manifest_path = out / "manifest.json"
    manifest = load_json(manifest_path) or {"sources": {}}
    data: dict[str, dict | None] = {name: load_json(out / f"{name}.json") for name in ORDER}
    extra_checks: list[dict] = []

    def counties_fips() -> list[str]:
        g = data.get("geography")
        if not g:
            raise RuntimeError("County list unavailable: geography has never succeeded")
        return [c["county_fips"] for c in g["data"]["counties"]]

    steps: dict[str, Callable[[], tuple]] = {
        "geography": lambda: geography.fetch(f, d, out / "geo"),
        "legislators": lambda: legislators.fetch(f, d),
        "acs": lambda: acs.fetch(f, d),
        "pep": lambda: pep.fetch(f, d),
        "laus": lambda: laus.fetch(f, d, counties_fips()),
        "qcew": lambda: qcew.fetch(f, d, counties_fips()),
        "usaspending": lambda: usaspending.fetch(f, d, counties_fips()),
        "elections": lambda: elections.fetch(f, d),
        "fec": lambda: fec.fetch(f, d),
        "votes": lambda: votes.fetch(f, d, (data.get("legislators") or {}).get("data", {}).get("terms", [])),
    }

    for name in ORDER:
        if only and name not in only:
            continue
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            payload, sources, src_checks = steps[name]()
            data[name] = dataset(payload, sources, district=d.id, source_module=name)
            write_json(out / f"{name}.json", data[name], compact=name in {"votes"})
            extra_checks += src_checks
            manifest["sources"][name] = {"status": "ok", "updated": started, "error": None,
                                         "sources": [s.id for s in sources]}
            print(f"  ok      {name}")
        except Exception as exc:  # keep the last good file; record why this run failed
            prev = manifest["sources"].get(name, {})
            manifest["sources"][name] = {
                "status": "stale" if data.get(name) else "missing",
                "updated": prev.get("updated"),
                "error": f"{type(exc).__name__}: {exc}"[:500],
                "sources": prev.get("sources", []),
                "attempted": started,
            }
            print(f"  FAILED  {name}: {exc}")
            traceback.print_exc()

    notes = load_notes()
    results = checks_mod.run(d, data, notes, extra_checks)
    # Keep checks contributed by sources that were not re-run in this build.
    previous = load_json(out / "integrity.json") or {}
    run_ids = {c["id"] for c in results}
    for c in previous.get("checks", []):
        if c["id"] not in run_ids and c["id"] == "acs-labels" and only and "acs" not in only:
            results.insert(0, c)
    integrity = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "summary": checks_mod.summarize(results), "checks": results}
    write_json(out / "integrity.json", integrity)
    write_json(out / "notes.json", {"notes": notes})

    manifest.update({
        "district": d.id,
        "name": d.name,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "requests": len(f.log),
        "requests_from_cache": sum(1 for r in f.log if r.from_cache),
    })
    write_json(manifest_path, manifest)
    write_json(out / "fetch-log.json", [asdict(r) for r in f.log], compact=True)

    from . import summary
    summ = summary.build(d, data, integrity, notes, manifest)
    write_json(out / "summary.json", summ)
    print(f"  checks: {integrity['summary']}")
    return {"manifest": manifest, "integrity": integrity, "summary": summ}
