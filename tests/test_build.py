"""The build keeps working when a source fails, and never throws away the last good data."""

from __future__ import annotations

import json

from pipeline.provenance import Source


def fake_geo(*a, **k):
    payload = {"counties": [{"fips": "55003", "county_fips": "003", "name": "Ashland County", "short_name": "Ashland",
                             "whole": True, "land_share": 1.0, "pop_2020_county": 10, "pop_2020_in_district": 10,
                             "pop_share_in_district": 1.0}],
               "county_count": 1, "whole_count": 1, "split": [], "pop_2020": 10, "pop_2020_sum_of_parts": 10,
               "land_sq_mi_relationship": 1.0, "boundary": None}
    return payload, [Source(id="census-rel", publisher="U.S. Census Bureau", title="t", url="https://x.gov", year="2024")], []


def boom(*a, **k):
    raise RuntimeError("network down")


def test_partial_failure_and_stale_data(district, tmp_path, monkeypatch):
    from pipeline import build
    from pipeline.sources import acs, cameras, elections, fec, geography, irs, laus, legislators, pep, qcew, usaspending, votes

    monkeypatch.setattr(build, "DATA_ROOT", tmp_path)
    for mod in (acs, cameras, elections, fec, irs, laus, legislators, pep, qcew, usaspending, votes):
        monkeypatch.setattr(mod, "fetch", boom)
    monkeypatch.setattr(geography, "fetch", fake_geo)

    build.run(district)
    out = tmp_path / district.id
    man = json.loads((out / "manifest.json").read_text())
    assert man["sources"]["geography"]["status"] == "ok"
    assert man["sources"]["acs"]["status"] == "missing"
    assert "network down" in man["sources"]["acs"]["error"]
    assert (out / "summary.json").exists() and (out / "integrity.json").exists()

    # Second run: geography now fails too, but its last good file must survive and be marked stale.
    monkeypatch.setattr(geography, "fetch", boom)
    build.run(district)
    man = json.loads((out / "manifest.json").read_text())
    assert man["sources"]["geography"]["status"] == "stale"
    assert json.loads((out / "geography.json").read_text())["data"]["county_count"] == 1
    summary = json.loads((out / "summary.json").read_text())
    assert summary["counties"][0]["short_name"] == "Ashland"
