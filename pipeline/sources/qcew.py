"""Bureau of Labor Statistics: jobs and pay by county (QCEW)."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from ..config import District
from ..http import Fetcher, FetchError
from ..provenance import Source

URL = "https://data.bls.gov/cew/data/api/{y}/a/area/{fips}.csv"
SUPERSECTORS = {
    "1011": "Natural resources and mining",
    "1012": "Construction",
    "1013": "Manufacturing",
    "1021": "Trade, transportation, and utilities",
    "1022": "Information",
    "1023": "Financial activities",
    "1024": "Professional and business services",
    "1025": "Education and health services",
    "1026": "Leisure and hospitality",
    "1027": "Other services",
}


def _rows(fetcher: Fetcher, year: int, fips: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(fetcher.text(URL.format(y=year, fips=fips)))))


def fetch(fetcher: Fetcher, d: District, county_fips: list[str]) -> tuple[dict, list[Source], list[dict]]:
    now = datetime.now(timezone.utc)
    year = None
    for y in (now.year - 1, now.year - 2, now.year - 3):
        try:
            _rows(fetcher, y, f"{d.state_fips}{county_fips[0]}")
            year = y
            break
        except FetchError:
            continue
    if year is None:
        raise FetchError("No QCEW annual file available")
    counties = {}
    for cf in county_fips:
        rows = _rows(fetcher, year, f"{d.state_fips}{cf}")
        total = next((r for r in rows if r["own_code"] == "0" and r["industry_code"] == "10"), None)
        sectors = []
        for r in rows:
            if r["own_code"] == "5" and r["industry_code"] in SUPERSECTORS and r.get("disclosure_code", "") != "N":
                emp = int(float(r["annual_avg_emplvl"] or 0))
                if emp > 0:
                    sectors.append({"code": r["industry_code"], "label": SUPERSECTORS[r["industry_code"]],
                                    "jobs": emp, "avg_annual_pay": int(float(r["avg_annual_pay"] or 0))})
        sectors.sort(key=lambda s: -s["jobs"])
        counties[cf] = {
            "jobs": int(float(total["annual_avg_emplvl"])) if total else None,
            "establishments": int(float(total["annual_avg_estabs"])) if total else None,
            "avg_annual_pay": int(float(total["avg_annual_pay"])) if total else None,
            "private_sectors": sectors,
        }
    state_rows = _rows(fetcher, year, f"{d.state_fips}000")
    st = next((r for r in state_rows if r["own_code"] == "0" and r["industry_code"] == "10"), None)
    payload = {"year": year, "counties": counties,
               "state": {"jobs": int(float(st["annual_avg_emplvl"])), "avg_annual_pay": int(float(st["avg_annual_pay"]))} if st else None}
    src = Source(
        id="bls-qcew",
        publisher="U.S. Bureau of Labor Statistics",
        title=f"Quarterly Census of Employment and Wages: {year} annual averages by county",
        url="https://www.bls.gov/cew/",
        year=str(year + 1),
        vintage=f"{year} annual averages",
        query=URL.format(y=year, fips=f"{d.state_fips}XXX"),
        notes="Covers jobs insured under unemployment insurance; counts jobs by where people work, not where they live.",
    )
    return payload, [src], []
