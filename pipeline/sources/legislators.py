"""Who has held the seat: congress-legislators, cross-checked with the Clerk."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date

import yaml

from ..config import District
from ..http import Fetcher, FetchError
from ..provenance import Source

RAW = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/{f}"
CLERK = "https://clerk.house.gov/xml/lists/MemberData.xml"

try:  # the historical file is large; the C loader is much faster when available
    Loader = yaml.CSafeLoader
except AttributeError:  # pragma: no cover
    Loader = yaml.SafeLoader


def seat_terms(people: list[dict], state: str, district: int) -> list[dict]:
    out = []
    for p in people:
        for t in p.get("terms", []):
            if t.get("type") == "rep" and t.get("state") == state and t.get("district") == district:
                out.append({
                    "bioguide": p["id"].get("bioguide"),
                    "name": p["name"].get("official_full") or f"{p['name'].get('first')} {p['name'].get('last')}",
                    "last_name": p["name"].get("last"),
                    "party": t.get("party"),
                    "start": str(t["start"]),
                    "end": str(t["end"]),
                })
    return sorted(out, key=lambda t: t["start"])


def members_from_terms(terms: list[dict]) -> list[dict]:
    members: list[dict] = []
    for t in terms:
        if members and members[-1]["bioguide"] == t["bioguide"]:
            m = members[-1]
            m["end"] = max(m["end"], t["end"])
            m["terms"] += 1
            if t["party"] not in m["parties"]:
                m["parties"].append(t["party"])
        else:
            members.append({**{k: t[k] for k in ("bioguide", "name", "last_name", "start", "end")},
                            "parties": [t["party"]], "terms": 1})
    return members


def clerk_member(fetcher: Fetcher, state: str, district: int) -> dict | None:
    root = ET.fromstring(fetcher.fetch(CLERK))
    code = f"{state}{district:02d}"
    for m in root.iter("member"):
        sd = m.findtext("statedistrict")
        if sd == code:
            info = m.find("member-info")
            if info is None:
                return {"statedistrict": sd, "vacant": True}
            return {
                "statedistrict": sd,
                "bioguide": info.findtext("bioguideID"),
                "name": info.findtext("official-name") or info.findtext("namelist"),
                "party": info.findtext("party"),
                "vacant": not bool(info.findtext("bioguideID")),
            }
    return None


def fetch(fetcher: Fetcher, d: District) -> tuple[dict, list[Source], list[dict]]:
    current = yaml.load(fetcher.fetch(RAW.format(f="legislators-current.yaml")), Loader=Loader)
    historical = yaml.load(fetcher.fetch(RAW.format(f="legislators-historical.yaml")), Loader=Loader)
    terms = seat_terms(historical + current, d.state_abbr, d.district_number)
    members = members_from_terms(terms)
    today = date.today().isoformat()
    sitting = next((t for t in reversed(terms) if t["start"] <= today <= t["end"]), None)
    try:
        clerk = clerk_member(fetcher, d.state_abbr, d.district_number)
    except (FetchError, ET.ParseError) as exc:
        clerk = {"error": str(exc)}
    payload = {
        "current": sitting,
        "members": members,
        "terms": terms,
        "clerk": clerk,
        "first_term_start": terms[0]["start"] if terms else None,
    }
    sources = [
        Source(
            id="congress-legislators",
            publisher="The @unitedstates project",
            title="congress-legislators: Members of the United States Congress, 1789 to present",
            url="https://github.com/unitedstates/congress-legislators",
            year=str(date.today().year),
            kind="Data set",
            query=RAW.format(f="legislators-current.yaml"),
            notes="Public-domain data maintained by volunteers and cross-checked against the Clerk of the House.",
        ),
        Source(
            id="clerk-members",
            publisher="Office of the Clerk, U.S. House of Representatives",
            title="Member data (XML)",
            url=CLERK,
            year=str(date.today().year),
        ),
    ]
    return payload, sources, []
