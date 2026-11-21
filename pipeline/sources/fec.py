"""Federal Election Commission: money raised and spent by candidates for the seat."""

from __future__ import annotations

import os
from datetime import date

from ..config import District
from ..http import Fetcher
from ..provenance import Source

API = "https://api.open.fec.gov/v1/candidates/totals/"


def fetch(fetcher: Fetcher, d: District) -> tuple[dict, list[Source], list[dict]]:
    key = os.environ.get("FEC_API_KEY") or "DEMO_KEY"
    cycles = [int(c) for c in d.trends.get("fec_cycles", [2024, 2026])]
    out = {}
    for cycle in cycles:
        res = fetcher.json(API, params={
            "api_key": key, "election_year": cycle, "office": "H", "state": d.state_abbr,
            "district": d.district, "per_page": 100, "sort": "-receipts", "election_full": "true",
        })
        cands = []
        for c in res.get("results", []):
            receipts = c.get("receipts") or 0
            if receipts <= 0 and not c.get("disbursements"):
                continue
            cands.append({
                "candidate_id": c.get("candidate_id"),
                "name": c.get("name"),
                "party": c.get("party_full"),
                "status": c.get("incumbent_challenge_full"),
                "receipts": receipts,
                "disbursements": c.get("disbursements") or 0,
                "cash_on_hand": c.get("last_cash_on_hand_end_period") if c.get("last_cash_on_hand_end_period") is not None else c.get("cash_on_hand_end_period"),
                "coverage_end": c.get("coverage_end_date"),
                "url": f"https://www.fec.gov/data/candidate/{c.get('candidate_id')}/?cycle={cycle}",
            })
        out[str(cycle)] = sorted(cands, key=lambda c: -c["receipts"])
    payload = {"cycles": out, "as_of": date.today().isoformat()}
    src = Source(
        id="fec",
        publisher="Federal Election Commission",
        title="Candidate financial totals, U.S. House",
        url=f"https://www.fec.gov/data/elections/house/{d.state_abbr}/{d.district}/{cycles[-1]}/",
        year=str(date.today().year),
        query=f"{API}?election_year=...&office=H&state={d.state_abbr}&district={d.district}",
        notes="Totals cover each candidate's principal campaign committee for the two-year cycle, through its latest report.",
    )
    return payload, [src], []
