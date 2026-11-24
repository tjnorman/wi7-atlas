"""Checks on the committed data files. Skipped until the first data build exists."""

from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "wi-07"
FILES = ["geography", "acs", "pep", "laus", "qcew", "usaspending", "irs", "ssa", "cameras", "colleges", "municipalities", "broadcast", "legislators", "elections", "fec", "votes"]

pytestmark = pytest.mark.skipif(not (DATA / "summary.json").exists(), reason="no data build yet")


def load(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))


def test_no_sample_data_anywhere():
    for path in DATA.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert '"sample": true' not in text and "SAMPLE" not in text, f"sample data in {path}"


@pytest.mark.parametrize("name", FILES)
def test_every_dataset_cites_its_sources(name):
    path = DATA / f"{name}.json"
    if not path.exists():
        pytest.skip(f"{name} has not built yet")
    ds = load(name)
    assert ds["sources"], name
    for s in ds["sources"]:
        assert s["apa"] and s["url"].startswith("https://"), s
        assert "REDACTED" not in s["url"]
        assert "api_key=" not in (s.get("query") or "").replace("api_key=REDACTED", "")


def test_no_api_keys_leaked():
    for path in [*DATA.rglob("*.json")]:
        text = path.read_text(encoding="utf-8")
        for marker in ("registrationkey", "api_key=", "&key="):
            for line in text.split(marker)[1:]:
                assert line.startswith("REDACTED") or line.startswith('"'), f"possible key in {path}"


def test_summary_headline_values_are_numbers():
    s = load("summary")
    assert s["headline"], "no headline numbers"
    for h in s["headline"]:
        assert isinstance(h["value"], (int, float)), h
        assert h["display"], h


def test_integrity_report_has_no_failures():
    integ = load("integrity")
    fails = [c for c in integ["checks"] if c["status"] == "fail"]
    assert not fails, "integrity failures: " + "; ".join(f"{c['id']}: {c['detail']}" for c in fails)


def test_counties_match_configuration():
    from pipeline import config

    d = config.load("wi-07")
    geo = load("geography")["data"]
    assert geo["county_count"] == d.expectations["county_count"]
    assert sorted(geo["split"]) == sorted(d.expectations["split_counties"])


def test_percentages_are_plausible():
    acs = load("acs")["data"]
    for geo in ("district", "state", "us"):
        for k, v in acs[geo]["metrics"].items():
            if k.endswith("_pct") and v is not None:
                assert 0 <= v <= 100, (geo, k, v)
