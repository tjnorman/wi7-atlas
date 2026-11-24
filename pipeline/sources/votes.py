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
    if meta is None:
        meta = root.find(".//vote-metadata")
    if meta is None:
        raise ValueError(f"not a roll-call record: <{root.tag}> {xml_bytes[:160]!r}")
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


def congress_of(year: int) -> int:
    return (year - 1789) // 2 + 1


def read_year(fetcher: Fetcher, y: int) -> tuple[list[dict], list[tuple[int, int]], list[str]]:
    """Every roll call the Clerk has published for one calendar year."""
    parsed, gaps, diagnostics = [], [], []
    n, misses = 1, 0
    while misses < 3:
        try:
            parsed.append(parse_vote(fetcher.fetch(EVS.format(y=y, n=n), retries=2)))
            misses = 0
        except (FetchError, ET.ParseError, ValueError) as exc:
            misses += 1
            gaps.append((y, n))
            diagnostics.append(f"{y}/{n}: {str(exc)[:200]}")
        n += 1
    # trailing misses are simply the end of the year's votes
    return parsed, [g for g in gaps if g[1] < n - 3], diagnostics


class Tally:
    """Counts for one group of roll calls: a Congress, a year, or one member's time in the seat."""

    def __init__(self):
        self.house_roll_calls = 0   # yes-or-no roll calls taken by the House
        self.vacant = 0             # of those, taken while the seat was empty
        self.cast = self.missed = 0
        self.with_party = self.party_comparable = 0
        self.winning = self.winning_comparable = 0
        self.house_missed = self.house_slots = 0   # every member, on the roll calls the seat was eligible for

    def stats(self) -> dict:
        held = self.cast + self.missed
        share = lambda a, b: 100 * a / b if b else None
        return {
            "house_yes_no_roll_calls": self.house_roll_calls, "while_seat_vacant": self.vacant,
            "yes_no_votes_while_held": held, "votes_cast": self.cast, "missed": self.missed,
            "missed_pct": share(self.missed, held), "house_missed_pct": share(self.house_missed, self.house_slots),
            "with_party_majority_pct": share(self.with_party, self.party_comparable),
            "on_winning_side_pct": share(self.winning, self.winning_comparable),
        }


def fetch(fetcher: Fetcher, d: District, terms: list[dict]) -> tuple[dict, list[Source], list[dict]]:
    """terms: the seat's terms from the legislators source (bioguide, start, end, party)."""
    congress = d.congress
    today = date.today()
    first_year = 1789 + 2 * (congress - 1)
    current_years = [first_year, first_year + 1]
    start_year = min(int(d.trends.get("votes_start_year", first_year)), first_year)
    years = [y for y in range(start_year, first_year + 2) if y <= today.year]
    parsed: list[dict] = []
    gaps: list[tuple[int, int]] = []
    diagnostics: list[str] = []
    for y in years:
        p, g, diag = read_year(fetcher, y)
        parsed += p
        gaps += g
        diagnostics += diag
    if not parsed:
        raise FetchError("No roll calls could be read. First responses: " + " | ".join(diagnostics[:3]))

    def holder(on: str) -> dict | None:
        return next((t for t in terms if t["start"] <= on <= t["end"]), None)

    now, by_year, by_member = Tally(), {}, {}
    holders_by_year: dict[int, list[str]] = {}
    member_span: dict[str, dict] = {}
    rows, missed_rows = [], []
    for v in parsed:
        sides = {side(x["vote"]) for x in v["votes"].values()}
        if not ({"yes", "no"} & sides):
            continue  # quorum calls and the election of the Speaker are not yes-or-no votes
        year = int(v["date"][:4])
        h = holder(v["date"])
        groups = [by_year.setdefault(year, Tally())]
        if year in current_years:
            groups.append(now)
        for t in groups:
            t.house_roll_calls += 1
        mv = v["votes"].get(h["bioguide"], {}).get("vote") if h else None
        if mv is None:
            for t in groups:
                t.vacant += 1
            continue
        groups.append(by_member.setdefault(h["bioguide"], Tally()))
        span = member_span.setdefault(h["bioguide"], {"name": h["name"], "party": h.get("party"), "first_vote": v["date"], "last_vote": v["date"]})
        span["first_vote"], span["last_vote"] = min(span["first_vote"], v["date"]), max(span["last_vote"], v["date"])
        if h["name"] not in holders_by_year.setdefault(year, []):
            holders_by_year[year].append(h["name"])
        not_voting = sum(1 for x in v["votes"].values() if x["vote"] == "Not Voting")
        rec = {k: v[k] for k in ("roll", "date", "legis", "question", "result", "desc", "session")}
        rec["member_vote"] = mv
        rec["member"] = h["name"]
        rec["clerk_url"] = f"https://clerk.house.gov/Votes/{v['date'][:4]}{v['roll']}"
        rec["bill_url"] = bill_url(v["legis"], v["congress"] or congress_of(year))
        if year in current_years:
            rows.append(rec)
        ms = side(mv)
        party_tally = v["by_party"].get(v["votes"][h["bioguide"]]["party"], {})
        py = sum(c for k, c in party_tally.items() if k in YES)
        pn = sum(c for k, c in party_tally.items() if k in NO)
        res = v["result"].lower()
        win = "yes" if any(w in res for w in ("passed", "agreed to", "adopted")) else \
              "no" if any(w in res for w in ("failed", "defeated", "rejected", "not agreed")) else None
        for t in groups:
            t.house_slots += len(v["votes"])
            t.house_missed += not_voting
            if mv == "Not Voting":
                t.missed += 1
                continue
            t.cast += 1
            if ms and py != pn:
                t.party_comparable += 1
                t.with_party += int(ms == ("yes" if py > pn else "no"))
            if ms and win:
                t.winning_comparable += 1
                t.winning += int(ms == win)
        if mv == "Not Voting":
            missed_rows.append({k: rec[k] for k in ("date", "roll", "legis", "question", "desc", "result", "member", "clerk_url", "bill_url")})

    payload = {
        "congress": congress,
        "years": current_years,
        "roll_calls_parsed": sum(1 for v in parsed if int(v["date"][:4]) in current_years),
        **{k: v for k, v in now.stats().items() if k not in ("house_yes_no_roll_calls", "while_seat_vacant")},
        "recent": sorted(rows, key=lambda r: (r["date"], r["roll"]), reverse=True)[:25],
        "period": {"from_year": years[0], "to_year": years[-1], "roll_calls_parsed": len(parsed),
                   "through": max(v["date"] for v in parsed)},
        "by_year": [{"year": y, "congress": congress_of(y), "members": holders_by_year.get(y, []), **by_year[y].stats()}
                    for y in sorted(by_year)],
        "by_member": sorted(({"bioguide": b, **member_span[b], **t.stats()} for b, t in by_member.items()),
                            key=lambda m: m["first_vote"]),
        "missed_votes": sorted(missed_rows, key=lambda r: (r["date"], r["roll"]), reverse=True),
        "gaps": gaps,
        "diagnostics": diagnostics[:12],
        "definitions": {
            "missed_pct": "Share of yes-or-no roll calls, while the member held the seat, recorded as Not Voting.",
            "house_missed_pct": "The same share for every House member on the same roll calls.",
            "with_party_majority_pct": ("Share of the member's yes-or-no votes that matched the position "
                                        "taken by most members of the member's own party. Ties are left out."),
            "on_winning_side_pct": "Share of the member's yes-or-no votes that matched the outcome.",
            "while_seat_vacant": "Yes-or-no roll calls taken while nobody held the seat. They are not counted as missed.",
            "not_voting": ("The Clerk records Not Voting for any absence, whatever the reason. The record does not say why "
                           "a vote was missed, and it does not show votes later explained in the Congressional Record."),
        },
    }
    span = f"{ordinal(congress_of(years[0]))} to {ordinal(congress)} Congresses" if years[0] < first_year else f"{ordinal(congress)} Congress"
    src = Source(
        id="clerk-votes",
        publisher="Office of the Clerk, U.S. House of Representatives",
        title=f"Roll call votes, {span} ({years[0]} to {years[-1]})" if years[0] < first_year else f"Roll call votes, {span}",
        url="https://clerk.house.gov/Votes",
        year=str(today.year),
        query=EVS.format(y=years[0], n=1).replace("001", "NNN"),
    )
    return payload, [src], []
