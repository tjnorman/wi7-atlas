"""Cities, villages, and towns in the district's counties, and which side of the line each is on.

Source: the Census Bureau's 2020 relationship file between congressional districts and
county subdivisions. It reports, for every municipality, how much of its land lies in each
district. It does not report population by part, so "split" describes land, not residents.
"""

from __future__ import annotations

import csv
import io

from ..config import District
from ..http import Fetcher
from ..provenance import Source

REL = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/cd-sld/tab20_cd{c}20_cousub20_st{s}.txt"
SQ_M_PER_SQ_MI = 2_589_988.110336
SLIVER = 0.001  # under 0.1% of a municipality's land is treated as a boundary sliver


def classify(parts: dict[str, int], total: int, district: str) -> tuple[str, float]:
    """(status, share of land inside) for one municipality. parts: district code -> land area."""
    inside = parts.get(district, 0)
    share = inside / total if total else (1.0 if district in parts else 0.0)
    others = [k for k, a in parts.items() if k != district and a > 0]
    if district not in parts or (share <= SLIVER and others):
        return "outside", share
    if not others or share >= 1 - SLIVER:
        return "inside", share
    return "split", share


def fetch(fetcher: Fetcher, d: District, county_names: dict[str, str], split_counties: set[str]) -> tuple[dict, list[Source], list[dict]]:
    url = REL.format(c=d.congress, s=d.state_fips)
    rows = list(csv.DictReader(io.StringIO(fetcher.text(url, encoding="utf-8-sig")), delimiter="|"))
    cd_col = f"GEOID_CD{d.congress}_20"
    found: dict[str, dict] = {}
    for r in rows:
        geoid = r["GEOID_COUSUB_20"]
        county = geoid[2:5]
        if county not in county_names or r["CLASSFP_COUSUB_20"] == "Z9":  # Z9: water or undefined
            continue
        m = found.setdefault(geoid, {"name": r["NAMELSAD_COUSUB_20"], "county": county,
                                     "total": int(r["AREALAND_COUSUB_20"] or 0), "parts": {}})
        m["parts"][r[cd_col][2:]] = int(r["AREALAND_PART"] or 0)
    out = []
    for geoid, m in found.items():
        status, share = classify(m["parts"], m["total"], d.district)
        base, _, kind = m["name"].rpartition(" ")
        out.append({
            "geoid": geoid, "name": base, "type": kind, "county_fips": m["county"], "county": county_names[m["county"]],
            "split_county": m["county"] in split_counties, "status": status,
            "land_sq_mi": round(m["total"] / SQ_M_PER_SQ_MI, 2), "land_share_in_district": round(share, 4),
            "other_districts": sorted(k for k, a in m["parts"].items() if k != d.district and a > 0),
        })
    out.sort(key=lambda m: (m["county"], m["name"], m["type"]))
    here = [m for m in out if m["status"] != "outside"]
    counts = {k: sum(1 for m in here if m["type"] == k) for k in ("city", "village", "town")}
    covered = {m["county_fips"] for m in here}
    checks = [{
        "id": "municipalities-cover", "title": "Every county in the district has municipalities in the district",
        "status": "pass" if covered == set(county_names) else "fail", "sources": ["census-cousub-rel", "census-rel"],
        "values": {"counties": len(covered), "in_district": len(here)},
        "detail": f"{len(here)} municipalities are in the district or split by its line ({counts['city']} cities, "
                  f"{counts['village']} villages, {counts['town']} towns), across {len(covered)} of {len(county_names)} counties.",
    }]
    payload = {"count_in_district": len(here), "by_type": counts, "split_municipalities": [m for m in out if m["status"] == "split"],
               "municipalities": out,
               "note": ("A municipality that crosses a county line is listed once in each county. Status is by share of land "
                        "area as of the 2020 Census; the file has no population by part.")}
    src = Source(
        id="census-cousub-rel", publisher="U.S. Census Bureau",
        title=f"{d.congress}th Congressional District to 2020 county subdivision relationship file ({d.state_name})",
        url="https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.2020.html",
        year="2024", query=url)
    return payload, [src], checks
