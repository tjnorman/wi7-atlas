"""U.S. House general election results for the seat (MIT Election Data and Science Lab)."""

from __future__ import annotations

import csv
import io
from collections import defaultdict

from ..config import District
from ..http import Fetcher, FetchError
from ..provenance import Source

DOI = "doi:10.7910/DVN/IG0UN2"
META = "https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=" + DOI
FILE = "https://dataverse.harvard.edu/api/access/datafile/{id}?format=original"

# Elections in which new district lines took effect in Wisconsin.
REDISTRICTING_YEARS = [1982, 1992, 2002, 2012, 2022]


def _truthy(v: str) -> bool:
    return str(v).strip().upper() in {"TRUE", "T", "1", "YES"}


def parse(text: str, state_po: str, district: int, start: int) -> list[dict]:
    sample = text[:4096]
    delim = "\t" if sample.count("\t") > sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    races: dict[int, dict] = {}
    votes: dict[int, dict] = defaultdict(lambda: defaultdict(lambda: {"votes": 0, "party": None, "writein": False}))
    for r in reader:
        if r.get("state_po") != state_po or r.get("stage", "").upper() != "GEN":
            continue
        try:
            if int(float(r.get("district") or -1)) != district:
                continue
            year = int(r["year"])
        except ValueError:
            continue
        if year < start or _truthy(r.get("special", "FALSE")) or _truthy(r.get("runoff", "FALSE")):
            continue
        name = (r.get("candidate") or "").strip() or "Other"
        rec = votes[year][name]
        rec["votes"] += int(float(r.get("candidatevotes") or 0))
        party = (r.get("party") or "").strip()
        rec["party"] = rec["party"] or (party.title() if party else None)
        rec["writein"] = rec["writein"] or _truthy(r.get("writein", "FALSE"))
        total = int(float(r.get("totalvotes") or 0))
        race = races.setdefault(year, {"total": total})
        race["total"] = max(race["total"], total)
    out = []
    for year in sorted(votes):
        total = races[year]["total"] or sum(v["votes"] for v in votes[year].values())
        cands = sorted(
            ({"name": n.title() if n.isupper() else n, "party": v["party"], "votes": v["votes"],
              "pct": 100 * v["votes"] / total if total else None, "writein": v["writein"]}
             for n, v in votes[year].items() if v["votes"] > 0),
            key=lambda c: -c["votes"],
        )
        out.append({"year": year, "total_votes": total, "candidates": cands,
                    "new_lines": year in REDISTRICTING_YEARS})
    return out


def fetch(fetcher: Fetcher, d: District) -> tuple[dict, list[Source], list[dict]]:
    meta = fetcher.json(META)
    version = meta["data"]["latestVersion"]
    files = version.get("files", [])
    target = None
    for f in files:
        name = f.get("dataFile", {}).get("filename", "") or f.get("label", "")
        if "house" in name.lower() and name.lower().endswith((".tab", ".csv")):
            target = f["dataFile"]
            break
    if not target:
        raise FetchError("House results file not found in the Dataverse dataset")
    raw = fetcher.fetch(FILE.format(id=target["id"]))
    text = raw.decode("utf-8", errors="replace")
    start = int(d.trends.get("house_results_from", 1976))
    results = parse(text, d.state_abbr, d.district_number, start)
    v = f"{version.get('versionNumber')}.{version.get('versionMinorNumber')}"
    payload = {"results": results, "redistricting_years": REDISTRICTING_YEARS,
               "dataset_version": v, "file": target.get("filename")}
    src = Source(
        id="medsl-house",
        publisher="MIT Election Data and Science Lab",
        title=f"U.S. House 1976-{results[-1]['year'] if results else ''} (Version {v})",
        url="https://doi.org/10.7910/DVN/IG0UN2",
        year=str(version.get("releaseTime", "")[:4] or "2025"),
        kind="Data set",
        query=FILE.format(id=target["id"]),
        notes="Compiled from official state results. General elections only; special elections excluded.",
    )
    return payload, [src], []
