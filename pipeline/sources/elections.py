"""U.S. House general election results for the seat.

Two public sources, checked against each other where they overlap:
  * MIT Election Data and Science Lab, U.S. House 1976-2018 (GitHub release),
    compiled from official state results.
  * Federal Election Commission, "Federal Elections" biennial compilations of
    official, certified results (Excel), used from 2018 on.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import datetime, timezone

from ..config import District
from ..http import Fetcher, FetchError
from ..provenance import Source

MEDSL_URL = "https://raw.githubusercontent.com/MEDSL/constituency-returns/HEAD/1976-2018-house.csv"
FEC_URL = "https://www.fec.gov/resources/cms-content/documents/federalelections{y}.xlsx"

# Elections in which new district lines took effect in Wisconsin.
REDISTRICTING_YEARS = [1982, 1992, 2002, 2012, 2022]
FEC_PARTIES = {"R": "Republican", "D": "Democrat", "DEM": "Democrat", "REP": "Republican", "IND": "Independent",
               "LIB": "Libertarian", "GRE": "Green", "CON": "Constitution", "W": "Write-in", "WI": "Write-in"}


def surname(name: str) -> str:
    parts = [p for p in name.replace(".", "").split() if p.lower() not in {"jr", "sr", "ii", "iii", "iv"}]
    return parts[-1].lower() if parts else ""


def _truthy(v: str) -> bool:
    return str(v).strip().upper() in {"TRUE", "T", "1", "YES"}


def _finish(year: int, total: int, cands: dict) -> dict:
    total = total or sum(v["votes"] for v in cands.values())
    rows = sorted(
        ({"name": n.title() if n.isupper() else n, "party": v["party"], "votes": v["votes"],
          "pct": 100 * v["votes"] / total if total else None, "writein": v["writein"]}
         for n, v in cands.items() if v["votes"] > 0),
        key=lambda c: -c["votes"],
    )
    return {"year": year, "total_votes": total, "candidates": rows, "new_lines": year in REDISTRICTING_YEARS}


def parse(text: str, state_po: str, district: int, start: int) -> list[dict]:
    """Parse the MIT Election Lab CSV format."""
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
    return [_finish(y, races[y]["total"], votes[y]) for y in sorted(votes)]


def parse_fec_xlsx(content: bytes, year: int, state_po: str, district: int) -> dict | None:
    """Parse one FEC "Federal Elections" workbook's U.S. House results sheet."""
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheet = next((wb[n] for n in wb.sheetnames if "house" in n.lower() and "result" in n.lower()), None)
    if sheet is None:
        return None
    rows = sheet.iter_rows(values_only=True)
    header, idx = None, {}
    for row in rows:
        cells = [str(c).strip().upper() if c is not None else "" for c in row]
        if any("CANDIDATE NAME" == c for c in cells) and any(c.startswith("GENERAL VOTES") for c in cells):
            header = cells
            break
    if not header:
        return None

    def col(pred):
        return next((i for i, c in enumerate(header) if pred(c)), None)

    idx = {
        "state": col(lambda c: c == "STATE ABBREVIATION"),
        "district": col(lambda c: c in ("D", "DISTRICT")),
        "name": col(lambda c: c == "CANDIDATE NAME"),
        "party": col(lambda c: c == "PARTY"),
        "general": col(lambda c: c.startswith("GENERAL VOTES")),
    }
    if None in idx.values():
        return None
    cands: dict = defaultdict(lambda: {"votes": 0, "party": None, "writein": False})
    for row in rows:
        def get(k):
            return row[idx[k]] if idx[k] < len(row) else None
        if str(get("state") or "").strip() != state_po:
            continue
        d = str(get("district") or "").strip()
        if not d.isdigit() or int(d) != district:
            continue  # skips specials such as "07 - UNEXPIRED TERM" and subtotal rows
        name = str(get("name") or "").strip()
        v = get("general")
        if not name or any(w in name.lower() for w in ("total", "district votes", "party votes")):
            continue
        try:
            votes = int(float(v))
        except (TypeError, ValueError):
            continue
        code = str(get("party") or "").strip().upper()
        if "," in name:  # FEC lists "Last, First"; show "First Last" like the other source
            last, first = name.split(",", 1)
            name = f"{first.strip()} {last.strip()}".strip()
        if name.lower().startswith("scatter"):
            name, code = "Scattering (write-ins)", "W"
        rec = cands[name]
        rec["votes"] += votes
        rec["party"] = rec["party"] or FEC_PARTIES.get(code, code.title() or None)
        rec["writein"] = rec["writein"] or code in ("W", "WI")
    if not cands:
        return None
    return _finish(year, 0, cands)


def fetch(fetcher: Fetcher, d: District) -> tuple[dict, list[Source], list[dict]]:
    start = int(d.trends.get("house_results_from", 1976))
    medsl = parse(fetcher.fetch(MEDSL_URL).decode("utf-8", errors="replace"), d.state_abbr, d.district_number, start)
    now = datetime.now(timezone.utc).year
    fec_years, fec_results = [], {}
    for y in range(2018, now + 1, 2):
        try:
            res = parse_fec_xlsx(fetcher.fetch(FEC_URL.format(y=y)), y, d.state_abbr, d.district_number)
        except FetchError:
            continue
        if res:
            fec_results[y] = res
            fec_years.append(y)
    by_year = {r["year"]: dict(r, source="medsl-house") for r in medsl}
    for y, r in fec_results.items():
        if y not in by_year:
            by_year[y] = dict(r, source="fec-results")
    results = [by_year[y] for y in sorted(by_year)]

    checks = []
    overlap = sorted(set(fec_results) & {r["year"] for r in medsl})
    if overlap:
        y = overlap[-1]
        a = next(r for r in medsl if r["year"] == y)["candidates"][0]
        b = fec_results[y]["candidates"][0]
        same = surname(a["name"]) == surname(b["name"])
        close = abs(a["votes"] - b["votes"]) <= max(50, 0.002 * a["votes"])
        checks.append({
            "id": "election-sources-agree",
            "title": "Two election compilations agree on the same race",
            "status": "pass" if same and close else "fail",
            "detail": (f"{y} general election: MIT Election Lab has {a['name']} with {a['votes']:,} votes; "
                       f"the FEC compilation has {b['name']} with {b['votes']:,} votes (tolerance 0.2%)."),
            "sources": ["medsl-house", "fec-results"],
        })
    payload = {"results": results, "redistricting_years": REDISTRICTING_YEARS, "fec_years": fec_years,
               "latest_year": results[-1]["year"] if results else None}
    sources = [
        Source(
            id="medsl-house",
            publisher="MIT Election Data and Science Lab",
            title="U.S. House 1976-2018 (constituency returns)",
            url="https://github.com/MEDSL/constituency-returns",
            year="2019",
            query=MEDSL_URL,
            notes="Compiled from official state results. General elections only; special elections excluded.",
        ),
        Source(
            id="fec-results",
            publisher="Federal Election Commission",
            title=f"Federal Elections: Election results for the U.S. Senate and the U.S. House of Representatives "
                  f"({', '.join(map(str, fec_years)) or 'none found'})",
            url="https://www.fec.gov/introduction-campaign-finance/election-results-and-voting-information/",
            year=str(max(fec_years) + 1) if fec_years else str(now),
            query=FEC_URL.format(y="YYYY"),
            notes="Official, certified results as reported by state election offices.",
        ),
    ]
    return payload, sources, checks
