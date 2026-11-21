"""House roll-call votes cast by the seat, from the Clerk of the House.

Follows the seat, not a person: each vote is attributed to whoever held the
seat on that date. Reports participation and agreement rates with plain
definitions, and the most recent votes with links to the official record.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime

from ..config import District
from ..http import Fetcher, FetchError
from ..provenance import Source

EVS = "https://clerk.house.gov/evs/{y}/roll{n:03d}.xml"
YES, NO = {"Yea", "Aye"}, {"Nay", "No"}
BILL_TYPES = {
    "H R": "house-bill", "H RES": "house-resolution", "H J RES": "house-joint-resolution",
    "H CON RES": "house-concurrent-resolution", "S": "senate-bill", "S J RES": "senate-joint-resolution",
    "S CON RES": "senate-concurrent-resolution", "S RES": "senate-resolution",
}


def ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def bill_url(legis: str, congress: int) -> str | None:
    m = re.match(r"^\s*([A-Z ]+?)\s+(\d+)\s*$", legis or "")
    if not m:
        return None
    t = BILL_TYPES.get(m.group(1).strip())
    return f"https://www.congress.gov/bill/{ordinal(congress)}-congress/{t}/{m.group(2)}" if t else None


def parse_vote(xml_bytes: bytes) -> dict:
    root = ET.fromstring(xml_bytes)
    meta = root.find("vote-metadata")
    get = lambda tag: (meta.findtext(tag) or "").strip()
    when = datetime.strptime(get("action-date"), "%d-%b-%Y").date()
    by_party: dict[str, Counter] = {}
    votes = {}
    for rv in root.iter("recorded-vote"):
        leg = rv.find("legislator")
        v = (rv.findtext("vote") or "").strip()
        party = leg.get("party")
        by_party.setdefault(party, Counter())[v] += 1
        votes[leg.get("name-id")] = {"vote": v, "party": party, "state": leg.get("state")}
    return {
        "congress": int(get("congress") or 0),
        "session": get("session"),
        "roll": int(get("rollcall-num")),
        "date": when.isoformat(),
        "legis": get("legis-num"),
        "question": get("vote-question"),
        "type": get("vote-type"),
        "result": get("vote-result"),
        "desc": get("vote-desc"),
        "by_party": {p: dict(c) for p, c in by_party.items()},
        "votes": votes,
    }


def side(v: str) -> str | None:
    return "yes" if v in YES else "no" if v in NO else None


def fetch(fetcher: Fetcher, d: District, terms: list[dict]) -> tuple[dict, list[Source], list[dict]]:
    """terms: the seat's terms from the legislators source (bioguide, start, end, party)."""
    congress = d.congress
    first_year = 1789 + 2 * (congress - 1)
    years = [first_year, first_year + 1]
    today = date.today()
    parsed: list[dict] = []
    gaps = []
    for y in years:
        if y > today.year:
            continue
        n, misses = 1, 0
        while misses < 3:
            try:
                parsed.append(parse_vote(fetcher.fetch(EVS.format(y=y, n=n), retries=2)))
                misses = 0
            except FetchError:
                misses += 1
                gaps.append((y, n))
            except ET.ParseError:
                gaps.append((y, n))
            n += 1
        # trailing misses are simply the end of the year's votes
        gaps = [g for g in gaps if not (g[0] == y and g[1] >= n - 3)]

    def holder(on: str) -> dict | None:
        return next((t for t in terms if t["start"] <= on <= t["end"]), None)

    rows, missed, cast, with_party, party_comparable, winning, winning_comparable = [], 0, 0, 0, 0, 0, 0
    house_missed, house_slots = 0, 0
    for v in parsed:
        h = holder(v["date"])
        sides = {side(x["vote"]) for x in v["votes"].values()}
        if not ({"yes", "no"} & sides):
            continue  # quorum calls and the election of the Speaker are not yes-or-no votes
        house_slots += len(v["votes"])
        house_missed += sum(1 for x in v["votes"].values() if x["vote"] == "Not Voting")
        if not h:
            continue
        mv = v["votes"].get(h["bioguide"], {}).get("vote")
        if mv is None:
            continue
        rec = {k: v[k] for k in ("roll", "date", "legis", "question", "result", "desc", "session")}
        rec["member_vote"] = mv
        rec["member"] = h["name"]
        rec["clerk_url"] = f"https://clerk.house.gov/Votes/{v['date'][:4]}{v['roll']}"
        rec["bill_url"] = bill_url(v["legis"], congress)
        rows.append(rec)
        if mv == "Not Voting":
            missed += 1
            continue
        cast += 1
        ms = side(mv)
        party_tally = v["by_party"].get(v["votes"][h["bioguide"]]["party"], {})
        py = sum(c for k, c in party_tally.items() if k in YES)
        pn = sum(c for k, c in party_tally.items() if k in NO)
        if ms and py != pn:
            party_comparable += 1
            with_party += int(ms == ("yes" if py > pn else "no"))
        res = v["result"].lower()
        win = "yes" if any(w in res for w in ("passed", "agreed to", "adopted")) else \
              "no" if any(w in res for w in ("failed", "defeated", "rejected", "not agreed")) else None
        if ms and win:
            winning_comparable += 1
            winning += int(ms == win)
    total = cast + missed
    payload = {
        "congress": congress,
        "years": years,
        "roll_calls_parsed": len(parsed),
        "yes_no_votes_while_held": total,
        "votes_cast": cast,
        "missed": missed,
        "missed_pct": 100 * missed / total if total else None,
        "house_missed_pct": 100 * house_missed / house_slots if house_slots else None,
        "with_party_majority_pct": 100 * with_party / party_comparable if party_comparable else None,
        "on_winning_side_pct": 100 * winning / winning_comparable if winning_comparable else None,
        "recent": sorted(rows, key=lambda r: (r["date"], r["roll"]), reverse=True)[:25],
        "gaps": gaps,
        "definitions": {
            "missed_pct": "Share of yes-or-no roll calls, while the member held the seat, recorded as Not Voting.",
            "house_missed_pct": "The same share for every House member on the same roll calls.",
            "with_party_majority_pct": ("Share of the member's yes-or-no votes that matched the position "
                                        "taken by most members of the member's own party. Ties are left out."),
            "on_winning_side_pct": "Share of the member's yes-or-no votes that matched the outcome.",
        },
    }
    src = Source(
        id="clerk-votes",
        publisher="Office of the Clerk, U.S. House of Representatives",
        title=f"Roll call votes, {ordinal(congress)} Congress",
        url="https://clerk.house.gov/Votes",
        year=str(today.year),
        query=EVS.format(y=years[0], n=1).replace("001", "NNN"),
    )
    return payload, [src], []
