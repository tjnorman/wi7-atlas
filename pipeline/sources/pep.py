"""Census Bureau Population Estimates Program: county populations since 2020."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from ..config import District
from ..http import Fetcher, FetchError
from ..provenance import Source

URL = "https://www2.census.gov/programs-surveys/popest/datasets/2020-{v}/counties/totals/co-est{v}-alldata.csv"
COMPONENTS = ["BIRTHS", "DEATHS", "NATURALCHG", "DOMESTICMIG", "INTERNATIONALMIG", "NETMIG"]


def fetch(fetcher: Fetcher, d: District) -> tuple[dict, list[Source], list[dict]]:
    year_now = datetime.now(timezone.utc).year
    text, vintage = None, None
    for v in (year_now, year_now - 1, year_now - 2):
        try:
            text = fetcher.text(URL.format(v=v), encoding="latin-1")
            vintage = v
            break
        except FetchError:
            continue
    if text is None:
        raise FetchError("No county population estimates file found")
    rows = list(csv.DictReader(io.StringIO(text)))
    years = list(range(2020, vintage + 1))
    counties, state = {}, None
    for r in rows:
        if r["STATE"] != d.state_fips:
            continue
        rec = {
            "name": r["CTYNAME"],
            "base_2020": int(r["ESTIMATESBASE2020"]),
            "estimates": {str(y): int(r[f"POPESTIMATE{y}"]) for y in years},
            "components_since_2020": {c.lower(): sum(int(r.get(f"{c}{y}", 0) or 0) for y in years) for c in COMPONENTS},
        }
        if r["SUMLEV"] == "040":
            state = rec
        elif r["SUMLEV"] == "050":
            counties[r["COUNTY"]] = rec
    payload = {"vintage": vintage, "years": years, "counties": counties, "state": state,
               "reference_date": f"July 1, {vintage}"}
    src = Source(
        id="pep",
        publisher="U.S. Census Bureau",
        title=f"County population totals and components of change: April 1, 2020 to July 1, {vintage} (Vintage {vintage})",
        url="https://www.census.gov/programs-surveys/popest/data/tables.html",
        year=str(vintage + 1),
        vintage=f"Vintage {vintage}",
        query=URL.format(v=vintage),
    )
    return payload, [src], []
