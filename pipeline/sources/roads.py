"""Planned highway construction in the district, from the Wisconsin Department of Transportation.

Source: WisDOT's public map service for its improvement program, layer "Construction Projects
(6 Year)": every project the department intends to build on state and local highways in the
current fiscal year and the five after it. WisDOT tags each project with the congressional
districts it touches and gives its construction cost as a range, not a figure.

The layer's own field list is checked before any field is used. Projects are kept when WisDOT's
district tag includes this district. Because costs are ranges, totals are given as a low and a
high sum, never as one number. The program is a plan: WisDOT revises it as revenue and
legislation change.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from ..config import District
from ..http import Fetcher
from ..provenance import Source

LAYER = "https://dotmaps.wi.gov/arcgis/rest/services/agohub/HIGHWAY_PROGRAM_2_4_6_YEAR/MapServer/1"
FIELDS = ["PROJECT_ID", "CONSTRUCTION_YEAR", "COUNTY", "ROUTE", "TITLE", "LIMITS", "MILES", "WORK_CONCEPT",
          "CONGRESSIONAL_DISTRICT_NUMBERS", "CONSTRUCTION_COST_RANGE_WD", "LAST_REFRESH_DATE"]
EXPECT_NAME = "construction projects (6 year)"
PAGE = 1000


def cost_range(text: str | None) -> tuple[int, int] | None:
    """'$1,000,000 - $1,999,999' -> (1000000, 1999999). Anything else -> None."""
    nums = re.findall(r"\$([\d,]+)", text or "")
    if len(nums) != 2:
        return None
    lo, hi = (int(n.replace(",", "")) for n in nums)
    return (lo, hi) if lo <= hi else None


def districts(text: str | None) -> list[int]:
    return [int(x) for x in re.findall(r"\d+", text or "")]


def fetch(fetcher: Fetcher, d: District, county_names: dict[str, str]) -> tuple[dict, list[Source], list[dict]]:
    meta = fetcher.json(LAYER, params={"f": "json"})
    have = {f["name"] for f in meta.get("fields", [])}
    missing = [f for f in FIELDS if f not in have]
    name = " ".join(str(meta.get("name", "")).lower().split())
    if missing or name != EXPECT_NAME:
        raise ValueError(f"WisDOT layer is not the one expected: name {meta.get('name')!r}, missing fields {missing}")

    rows, offset = [], 0
    while True:
        page = fetcher.json(LAYER + "/query", params={
            "f": "json", "where": f"CONGRESSIONAL_DISTRICT_NUMBERS LIKE '%{d.district_number}%'", "outFields": ",".join(FIELDS),
            "returnGeometry": "false", "orderByFields": "OBJECTID", "resultOffset": offset, "resultRecordCount": PAGE})
        if "features" not in page:
            raise ValueError(f"WisDOT query returned no features: {str(page)[:200]}")
        rows += [f["attributes"] for f in page["features"]]
        if not page.get("exceededTransferLimit") or not page["features"]:
            break
        offset += len(page["features"])

    ours = {n.upper() for n in county_names.values()}
    projects: dict[str, dict] = {}
    refreshed, unpriced, outside = None, 0, set()
    for r in rows:
        tags = districts(r.get("CONGRESSIONAL_DISTRICT_NUMBERS"))
        if d.district_number not in tags:
            continue
        pid = str(r.get("PROJECT_ID") or "").strip()
        county = " ".join(str(r.get("COUNTY") or "").split()).title()
        rng = cost_range(r.get("CONSTRUCTION_COST_RANGE_WD"))
        if r.get("LAST_REFRESH_DATE"):
            refreshed = max(refreshed or 0, int(r["LAST_REFRESH_DATE"]))
        p = projects.setdefault(pid, {
            "id": pid, "year": " ".join(str(r.get("CONSTRUCTION_YEAR") or "").split()), "counties": [],
            "route": " ".join(str(r.get("ROUTE") or "").split()), "title": " ".join(str(r.get("TITLE") or "").split()).title(),
            "limits": " ".join(str(r.get("LIMITS") or "").split()).title(), "miles": 0.0,
            "work": " ".join(str(r.get("WORK_CONCEPT") or "").split()).capitalize(),
            "cost_low": rng[0] if rng else None, "cost_high": rng[1] if rng else None,
            "cost_text": " ".join(str(r.get("CONSTRUCTION_COST_RANGE_WD") or "").split()) or None,
            "shared_with_districts": sorted(t for t in tags if t != d.district_number)})
        if county and county not in p["counties"]:
            p["counties"].append(county)
        p["miles"] = round(max(p["miles"], float(r.get("MILES") or 0)), 2)
    plist = sorted(projects.values(), key=lambda p: (p["year"], p["counties"], p["route"], p["id"]))
    unpriced = sum(1 for p in plist if p["cost_low"] is None)
    # A project tagged to the district but listed under another county is either region-wide or a
    # boundary project shared with a neighboring district. One tagged to this district alone is odd.
    region = [p for p in plist if any("region wide" in c.lower() for c in p["counties"])]
    neighbor = [p for p in plist if p not in region and not any(c.upper() in ours for c in p["counties"])]
    for p in region:
        p["scope"] = "region-wide"
    for p in neighbor:
        p["scope"] = "neighboring county"
    odd = [p for p in neighbor if not p["shared_with_districts"]]
    outside = {c for p in odd for c in p["counties"]}
    if not plist:
        raise ValueError("WisDOT returned no projects tagged with this district")

    def total(items):
        priced = [p for p in items if p["cost_low"] is not None]
        return {"projects": len(items), "cost_low": sum(p["cost_low"] for p in priced), "cost_high": sum(p["cost_high"] for p in priced)}

    years = sorted({p["year"] for p in plist})
    counties = sorted({c for p in plist for c in p["counties"]})
    as_of = datetime.fromtimestamp(refreshed / 1000, tz=timezone.utc).date().isoformat() if refreshed else None
    payload = {
        "as_of": as_of, "total": total(plist), "unpriced": unpriced,
        "by_year": [{"year": y, **total([p for p in plist if p["year"] == y])} for y in years],
        "by_county": [{"county": c, **total([p for p in plist if c in p["counties"]])} for c in counties],
        "shared": sum(1 for p in plist if p["shared_with_districts"]),
        "region_wide": len(region), "neighboring_county": len(neighbor),
        "projects": plist,
        "note": ("WisDOT gives each project's construction cost as a range, so totals are a low and a high sum. A project "
                 "that crosses a district line is counted in full here. The program is a plan and changes."),
    }
    checks = [{
        "id": "wisdot-program", "title": "WisDOT projects tagged to the district are in its counties, shared, or region-wide",
        "status": "pass" if not outside else "warn", "sources": ["wisdot-six-year"],
        "values": {"rows": len(rows), "projects": len(plist), "unpriced": unpriced},
        "detail": f"{len(plist)} projects from {len(rows)} rows carry WisDOT's tag for district {d.district_number}; "
                  f"{unpriced} have no readable cost range."
                  + f" {len(region)} are region-wide and {len(neighbor)} are in a neighboring county."
                  + (f" Tagged to this district alone but listed under another county: {', '.join(sorted(outside))}." if outside
                     else " Every project listed under a neighboring county is shared with another district."),
    }]
    src = Source(
        id="wisdot-six-year", publisher="Wisconsin Department of Transportation",
        title="Construction Projects (6 Year), highway improvement program map service",
        url="https://data-wisdot.opendata.arcgis.com/", year=(as_of or str(datetime.now(timezone.utc).year))[:4],
        query=LAYER + "/query?where=CONGRESSIONAL_DISTRICT_NUMBERS LIKE '%" + str(d.district_number) + "%'",
        vintage=f"Refreshed {as_of}" if as_of else None,
        notes="District tags and cost ranges are WisDOT's. Project counts are by WisDOT project ID.")
    return payload, [src], checks
