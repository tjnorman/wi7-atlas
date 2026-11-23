"""Bureau of Labor Statistics: monthly county unemployment (LAUS)."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from ..config import District
from ..http import Fetcher, FetchError
from ..provenance import Source

V1 = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
V2 = "https://api.bls.gov/publicAPI/v2/timeseries/data/"


def county_series(state_fips: str, county_fips: str, measure: str = "03") -> str:
    return f"LAUCN{state_fips}{county_fips}0000000{measure}"


def state_series(state_fips: str, measure: str = "03") -> str:
    return f"LAUST{state_fips}0000000000{measure}"


US_SERIES = "LNU04000000"  # national unemployment rate, not seasonally adjusted (to match county data)


def _request(fetcher: Fetcher, series: list[str], start: int, end: int) -> list[dict]:
    key = os.environ.get("BLS_API_KEY")
    body = {"seriesid": series, "startyear": str(start), "endyear": str(end)}
    url = V1
    if key:
        body["registrationkey"] = key
        url = V2
    data = fetcher.json(url, method="POST", json_body=body)
    if data.get("status") != "REQUEST_SUCCEEDED":
        raise FetchError(f"BLS: {data.get('status')} {data.get('message')}")
    return data["Results"]["series"]


def fetch(fetcher: Fetcher, d: District, county_fips: list[str]) -> tuple[dict, list[Source], list[dict]]:
    now = datetime.now(timezone.utc)
    start_year = int(d.trends.get("laus_start_year", 2016))
    key = bool(os.environ.get("BLS_API_KEY"))
    span = 20 if key else 10
    per_req = 50 if key else 25
    ids = {county_series(d.state_fips, c): c for c in county_fips}
    ids[state_series(d.state_fips)] = "state"
    ids[US_SERIES] = "us"
    all_ids = list(ids)
    series_out: dict[str, list] = {}
    y = start_year
    while y <= now.year:
        end = min(y + span - 1, now.year)
        for i in range(0, len(all_ids), per_req):
            for s in _request(fetcher, all_ids[i : i + per_req], y, end):
                pts = series_out.setdefault(ids[s["seriesID"]], [])
                for p in s.get("data", []):
                    if not p["period"].startswith("M") or p["period"] == "M13":
                        continue
                    try:
                        value = float(p["value"])
                    except ValueError:
                        continue
                    pts.append({
                        "date": f"{p['year']}-{p['period'][1:]}",
                        "rate": value,
                        "preliminary": any(f.get("code") == "P" for f in p.get("footnotes", []) if f),
                    })
        y = end + 1
    for k in series_out:
        series_out[k] = sorted({p["date"]: p for p in series_out[k]}.values(), key=lambda p: p["date"])
    county_last = [series_out[c][-1]["date"] for c in county_fips if series_out.get(c)]
    latest = min(county_last) if county_last else None   # the newest month every county has
    payload = {"series": series_out, "latest_month": latest, "seasonally_adjusted": False,
               "national_latest_month": (series_out.get("us") or [{}])[-1].get("date"),
               "series_ids": {v: k for k, v in ids.items()}}
    src = Source(
        id="bls-laus",
        publisher="U.S. Bureau of Labor Statistics",
        title="Local Area Unemployment Statistics: county, state, and national unemployment rates, not seasonally adjusted",
        url="https://www.bls.gov/lau/",
        year=str(now.year),
        query=f"{V1} (series {', '.join(all_ids[:3])}, ...)",
        notes="The most recent month is preliminary and is revised the following month.",
    )
    return payload, [src], []
