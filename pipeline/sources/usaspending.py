"""USAspending.gov: federal award obligations in the district."""

from __future__ import annotations

from datetime import datetime, timezone

from ..config import District
from ..http import Fetcher
from ..provenance import Source

API = "https://api.usaspending.gov/api/v2"
AWARD_TYPES = [
    ("Contract_Obligations", "contracts", "Contracts"),
    ("Grant_Obligations", "grants", "Grants"),
    ("Direct_Obligations", "direct", "Direct payments"),
    ("Loan_Obligations", "loans", "Loans"),
    ("Idv_Obligations", "idv", "Indefinite delivery vehicles"),
    ("Other_Obligations", "other", "Other assistance"),
]


def fy_dates(fy: int) -> dict:
    return {"start_date": f"{fy - 1}-10-01", "end_date": f"{fy}-09-30"}


def last_complete_fy(now: datetime) -> int:
    return now.year if now.month >= 10 else now.year - 1


def fetch(fetcher: Fetcher, d: District, county_fips: list[str]) -> tuple[dict, list[Source], list[dict]]:
    now = datetime.now(timezone.utc)
    last_fy = last_complete_fy(now)
    first_fy = int(d.trends.get("usaspending_start_fy", 2018))
    location = {"country": "USA", "state": d.state_abbr, "district_current": d.district}

    over_time = fetcher.json(f"{API}/search/spending_over_time/", method="POST", json_body={
        "group": "fiscal_year",
        "filters": {
            "time_period": [{"start_date": f"{first_fy - 1}-10-01", "end_date": f"{last_fy}-09-30"}],
            "place_of_performance_locations": [location],
        },
    })
    years = []
    for r in over_time.get("results", []):
        fy = int(r["time_period"]["fiscal_year"])
        if fy < first_fy or fy > last_fy:
            continue
        rec = {"fy": fy, "total": r.get("aggregated_amount")}
        for key, short, _ in AWARD_TYPES:
            if key in r:
                rec[short] = r[key]
        years.append(rec)
    years.sort(key=lambda r: r["fy"])

    def by_category(category: str, fy: int, limit: int = 10) -> list[dict]:
        res = fetcher.json(f"{API}/search/spending_by_category/{category}/", method="POST", json_body={
            "filters": {"time_period": [fy_dates(fy)], "place_of_performance_locations": [location]},
            "limit": limit, "page": 1,
        })
        return [{"name": x.get("name"), "code": x.get("code"), "amount": x.get("amount")} for x in res.get("results", [])]

    agencies = by_category("awarding_agency", last_fy)
    programs = by_category("cfda", last_fy)

    geo = fetcher.json(f"{API}/search/spending_by_geography/", method="POST", json_body={
        "scope": "place_of_performance",
        "geo_layer": "county",
        "geo_layer_filters": [f"{d.state_fips}{c}" for c in county_fips],
        "filters": {"time_period": [fy_dates(last_fy)]},
    })
    counties = {
        r["shape_code"][-3:]: {"name": r.get("display_name"), "amount": r.get("aggregated_amount"),
                               "per_capita": r.get("per_capita"), "population": r.get("population")}
        for r in geo.get("results", []) if r.get("shape_code")
    }
    district_geo = fetcher.json(f"{API}/search/spending_by_geography/", method="POST", json_body={
        "scope": "place_of_performance",
        "geo_layer": "district",
        "geo_layer_filters": [d.geoid],
        "filters": {"time_period": [fy_dates(last_fy)]},
    })
    district_total = next((r.get("aggregated_amount") for r in district_geo.get("results", [])
                           if r.get("shape_code") == d.geoid), None)

    payload = {
        "last_complete_fy": last_fy,
        "award_types": [{"id": s, "label": lab} for _, s, lab in AWARD_TYPES],
        "years": years,
        "top_agencies": agencies,
        "top_programs": programs,
        "counties_whole": counties,
        "district_total_by_geography": district_total,
        "as_of": now.date().isoformat(),
    }
    src = Source(
        id="usaspending",
        publisher="U.S. Department of the Treasury, Bureau of the Fiscal Service",
        title="USAspending.gov award obligations by place of performance",
        url="https://www.usaspending.gov/search",
        year=str(now.year),
        query=f"{API}/search/spending_over_time/ (place of performance {d.state_abbr}-{d.district}, current district lines)",
        notes=("Obligations are commitments to spend, reported by agencies and revised over time. "
               "Awards are placed by where the work happens. Some payments to individuals are reported only "
               "at county or state level and are not included in district totals."),
    )
    return payload, [src], []
