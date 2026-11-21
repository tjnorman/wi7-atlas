"""Cross-reference checks: independent sources must agree before numbers ship.

Each check compares two sources (or a source and a recorded expectation)
and reports pass, fail, warn (needs a human look), or skip (data missing).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .config import District


def _data(ds: dict | None) -> dict | None:
    return ds.get("data") if ds else None


def check(id_: str, title: str, status: str, detail: str, sources: list[str], values: dict | None = None) -> dict:
    return {"id": id_, "title": title, "status": status, "detail": detail, "sources": sources, "values": values or {}}


def skip(id_: str, title: str, missing: str, sources: list[str]) -> dict:
    return check(id_, title, "skip", f"Not run: {missing} unavailable in this build.", sources)


def fmt(n: float | int | None) -> str:
    return "n/a" if n is None else f"{n:,.0f}"


def run(d: District, data: dict[str, dict | None], notes: list[dict], extra: list[dict]) -> list[dict]:
    exp = d.expectations
    out: list[dict] = []
    geo = _data(data.get("geography"))
    acs = _data(data.get("acs"))
    pep = _data(data.get("pep"))
    leg = _data(data.get("legislators"))
    ele = _data(data.get("elections"))
    usa = _data(data.get("usaspending"))
    fec = _data(data.get("fec"))
    votes = _data(data.get("votes"))
    laus = _data(data.get("laus"))

    # 1. Which counties are in the district
    t = "The district's counties match the recorded list (26 counties: 21 whole, 5 split)"
    if geo:
        split = sorted(geo["split"])
        ok = (geo["county_count"] == exp.get("county_count") and geo["whole_count"] == exp.get("whole_county_count")
              and split == sorted(exp.get("split_counties", [])))
        out.append(check("county-list", t, "pass" if ok else "fail",
                         f"Census relationship file: {geo['county_count']} counties with land in the district, "
                         f"{geo['whole_count']} whole; split: {', '.join(split)}. Recorded: "
                         f"{exp.get('county_count')} counties, {exp.get('whole_county_count')} whole; split: "
                         f"{', '.join(sorted(exp.get('split_counties', [])))}.",
                         ["census-rel"], {"counties": geo["county_count"], "whole": geo["whole_count"], "split": split}))
    else:
        out.append(skip("county-list", t, "geography", ["census-rel"]))

    # 2. 2020 population: district total vs sum of county parts vs recorded figure
    t = "2020 Census population agrees three ways (district total, sum of county parts, recorded figure)"
    if geo and geo.get("pop_2020"):
        a, b, c = geo["pop_2020"], geo["pop_2020_sum_of_parts"], exp.get("census_2020_population")
        out.append(check("pop-2020", t, "pass" if a == b == c else "fail",
                         f"District total {fmt(a)}; sum of county parts {fmt(b)}; recorded {fmt(c)}.",
                         ["census-cd119"], {"district": a, "sum_of_parts": b, "recorded": c}))
    else:
        out.append(skip("pop-2020", t, "2020 district population", ["census-cd119"]))

    # 3. Whole counties: CD119 file and redistricting file report the same people
    t = "For whole counties, two Census files report the same 2020 population"
    if geo:
        bad = [c["short_name"] for c in geo["counties"]
               if c["whole"] and c["pop_2020_in_district"] != c["pop_2020_county"]]
        n = sum(1 for c in geo["counties"] if c["whole"])
        out.append(check("whole-county-pop", t, "pass" if not bad else "fail",
                         f"{n - len(bad)} of {n} whole counties match between the 119th District Summary File and "
                         f"the 2020 redistricting file." + (f" Mismatch: {', '.join(bad)}." if bad else ""),
                         ["census-cd119", "census-pl"]))
    else:
        out.append(skip("whole-county-pop", t, "geography", ["census-cd119", "census-pl"]))

    # 4. Land area: boundary file vs relationship file vs recorded figure
    t = "Land area agrees between the boundary file, the relationship file, and the recorded figure"
    if geo and geo.get("boundary"):
        a = geo["boundary"]["land_sq_mi"]
        b = geo["land_sq_mi_relationship"]
        c = exp.get("land_area_sq_mi")
        ok = abs(a - b) / b < 0.005 and (c is None or abs(a - c) / c < 0.01)
        out.append(check("land-area", t, "pass" if ok else "fail",
                         f"Boundary file {a:,.0f} sq mi; relationship file {b:,.0f} sq mi; recorded {fmt(c)} sq mi "
                         f"(tolerance 0.5% between Census files, 1% against the recorded figure).",
                         ["census-cb", "census-rel"], {"boundary": a, "relationship": b, "recorded": c}))
    else:
        out.append(skip("land-area", t, "boundary", ["census-cb", "census-rel"]))

    # 5. ACS: district is about one-eighth of Wisconsin
    t = "The district holds about one-eighth of Wisconsin's people, as its eight equal districts should"
    if acs and acs.get("district") and acs.get("state"):
        share = acs["district"]["metrics"]["population"] / acs["state"]["metrics"]["population"]
        ok = 0.115 <= share <= 0.135
        out.append(check("acs-share", t, "pass" if ok else "fail",
                         f"ACS {acs['vintage']['acs1']} 1-year: district {share:.1%} of the state (expected 11.5% to 13.5%).",
                         ["acs1"], {"share": share}))
    else:
        out.append(skip("acs-share", t, "ACS", ["acs1"]))

    # 6. Population estimates base vs 2020 Census, county by county
    t = "County population estimates start from the 2020 Census counts"
    if pep and geo:
        diffs = []
        for c in geo["counties"]:
            p = pep["counties"].get(c["county_fips"])
            if p and c["pop_2020_county"]:
                diffs.append((c["short_name"], abs(p["base_2020"] - c["pop_2020_county"]) / c["pop_2020_county"]))
        worst = max(diffs, key=lambda x: x[1]) if diffs else ("", 0)
        out.append(check("pep-base", t, "pass" if worst[1] < 0.01 else "fail",
                         f"{len(diffs)} counties compared; largest gap between the estimates base and the census count "
                         f"is {worst[1]:.2%} ({worst[0]}). Tolerance 1%.",
                         ["pep", "census-pl"]))
    else:
        out.append(skip("pep-base", t, "population estimates or geography", ["pep", "census-pl"]))

    # 7. Seat holder: congress-legislators vs Clerk of the House
    t = "Two independent records name the same sitting member"
    if leg and leg.get("current") and leg.get("clerk") and not leg["clerk"].get("error"):
        a, b = leg["current"]["bioguide"], leg["clerk"].get("bioguide")
        out.append(check("seat-holder", t, "pass" if a == b else "fail",
                         f"congress-legislators: {leg['current']['name']} ({a}); Clerk of the House: "
                         f"{leg['clerk'].get('name')} ({b}).", ["congress-legislators", "clerk-members"]))
    else:
        out.append(skip("seat-holder", t, "member records", ["congress-legislators", "clerk-members"]))

    # 8. Latest certified election winner holds the seat
    t = "The most recent election winner in the results file is the member who took office after it"
    if ele and leg and ele.get("results"):
        last = ele["results"][-1]
        winner = last["candidates"][0]
        start = f"{last['year'] + 1}-01-03"
        term = next((x for x in leg["terms"] if x["start"] >= start[:7]), None)
        ok = bool(term) and term["last_name"].lower() in winner["name"].lower()
        out.append(check("election-winner", t, "pass" if ok else "fail",
                         f"MIT Election Lab: {winner['name']} won in {last['year']}. congress-legislators: term "
                         f"starting {term['start'] if term else 'n/a'} held by {term['name'] if term else 'n/a'}.",
                         ["medsl-house", "congress-legislators"]))
    else:
        out.append(skip("election-winner", t, "election results or member records", ["medsl-house", "congress-legislators"]))

    # 9. USAspending: two endpoints report the same district total
    t = "Two USAspending endpoints report the same district total for the last full fiscal year"
    if usa and usa.get("years") and usa.get("district_total_by_geography") is not None:
        fy = usa["last_complete_fy"]
        a = next((y["total"] for y in usa["years"] if y["fy"] == fy), None)
        b = usa["district_total_by_geography"]
        ok = a is not None and b and abs(a - b) / abs(b) < 0.01
        out.append(check("usaspending-total", t, "pass" if ok else "warn",
                         f"FY{fy}: spending over time ${fmt(a)}; spending by geography ${fmt(b)} (tolerance 1%).",
                         ["usaspending"]))
    else:
        out.append(skip("usaspending-total", t, "USAspending", ["usaspending"]))

    # 10. Roll calls complete
    t = "No House roll call is missing from the vote record"
    if votes:
        g = votes.get("gaps") or []
        out.append(check("roll-calls", t, "pass" if not g else "warn",
                         f"{votes.get('roll_calls_parsed', 0)} roll calls read for the {votes.get('congress')}th Congress"
                         + (f"; could not read {len(g)}: {g[:5]}" if g else "; none missing."),
                         ["clerk-votes"]))
    else:
        out.append(skip("roll-calls", t, "roll calls", ["clerk-votes"]))

    # 11. Unemployment data current for every county
    t = "Every county has unemployment data through the same latest month"
    if laus and geo:
        latest = laus["latest_month"]
        behind = [c["short_name"] for c in geo["counties"]
                  if not laus["series"].get(c["county_fips"]) or laus["series"][c["county_fips"]][-1]["date"] != latest]
        out.append(check("laus-current", t, "pass" if not behind else "warn",
                         f"Latest month {latest}." + (f" Behind: {', '.join(behind)}." if behind else " All counties current."),
                         ["bls-laus"]))
    else:
        out.append(skip("laus-current", t, "unemployment data", ["bls-laus"]))

    # 12. FEC: the sitting member's committee appears in the cycle they won
    t = "The sitting member's campaign appears in FEC records for the election they won"
    if fec and leg and leg.get("current") and ele and ele.get("results"):
        cyc = str(ele["results"][-1]["year"])
        names = [c["name"] or "" for c in fec["cycles"].get(cyc, [])]
        ln = leg["current"]["last_name"].upper()
        ok = any(ln in n.upper() for n in names)
        out.append(check("fec-member", t, "pass" if ok else "warn",
                         f"{len(names)} candidates with financial activity in the {cyc} cycle; "
                         f"{'found' if ok else 'did not find'} {leg['current']['last_name']}.", ["fec", "congress-legislators"]))
    else:
        out.append(skip("fec-member", t, "FEC or member records", ["fec"]))

    # 13. Hand-curated notes are reviewed on schedule
    today = date.today().isoformat()
    for n in notes:
        overdue = str(n.get("review_by", "9999")) < today
        out.append(check(f"note-{n['id']}", f"Curated note reviewed on schedule: {n['title']}",
                         "warn" if overdue else "pass",
                         f"Status {n.get('status')}; verified {n.get('verified_on')}; review by {n.get('review_by')}."
                         + (" Overdue for review." if overdue else ""), [s["id"] for s in n.get("sources", [])]))

    return extra + out


def summarize(checks: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for c in checks:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    return {"total": len(checks), **counts, "ok": counts.get("fail", 0) == 0}
