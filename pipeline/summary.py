"""Headline numbers, a county table, and one list of every source used."""

from __future__ import annotations

from datetime import datetime, timezone

from .config import District


def _d(ds):
    return ds.get("data") if ds else None


def money(n: float | None, digits: int = 0) -> str | None:
    if n is None:
        return None
    if abs(n) >= 1e9:
        return f"${n / 1e9:,.2f} billion"
    if abs(n) >= 1e6:
        return f"${n / 1e6:,.1f} million"
    return f"${n:,.{digits}f}"


def pct(n: float | None, digits: int = 1) -> str | None:
    return None if n is None else f"{n:.{digits}f}%"


def month_name(ym: str | None) -> str | None:
    if not ym:
        return None
    y, m = ym.split("-")
    return datetime(int(y), int(m), 1).strftime("%B %Y")


def build(d: District, data: dict, integrity: dict, notes: list[dict], manifest: dict) -> dict:
    geo, acs, pep, laus = (_d(data.get(k)) for k in ("geography", "acs", "pep", "laus"))
    qcew, usa, leg, ele = (_d(data.get(k)) for k in ("qcew", "usaspending", "legislators", "elections"))
    fec, votes = _d(data.get("fec")), _d(data.get("votes"))
    irs = _d(data.get("irs"))

    headline = []

    def add(id_, label, value, display, source, note="", moe=None):
        if value is not None and display is not None:
            headline.append({"id": id_, "label": label, "value": value, "display": display,
                             "source": source, "note": note, "moe": moe})

    dm = (acs or {}).get("district", {}) or {}
    m = dm.get("metrics", {}) if dm else {}
    moe = dm.get("moe", {}) if dm else {}
    y1 = (acs or {}).get("vintage", {}).get("acs1")
    if acs:
        add("population", "People", m.get("population"), f"{m['population']:,.0f}" if m.get("population") else None,
            "acs1", f"ACS {y1} 1-year estimate", moe.get("population"))
    if geo and geo.get("boundary"):
        add("land", "Square miles of land", geo["boundary"]["land_sq_mi"], f"{geo['boundary']['land_sq_mi']:,.0f}",
            "census-cb", "Land area, 119th Congress lines")
    if geo:
        add("counties", "Counties", geo["county_count"], str(geo["county_count"]), "census-rel",
            f"{geo['whole_count']} whole, {geo['county_count'] - geo['whole_count']} split")
    if acs:
        add("income", "Median household income", m.get("median_household_income"),
            money(m.get("median_household_income")), "acs1", f"ACS {y1} 1-year estimate", moe.get("median_household_income"))
        add("age", "Median age", m.get("median_age"), f"{m['median_age']:.1f}" if m.get("median_age") else None,
            "acs1", f"ACS {y1} 1-year estimate", moe.get("median_age"))
        add("veterans", "Adults who are veterans", m.get("veterans_pct"), pct(m.get("veterans_pct")), "acs1")
        add("broadband", "Households with broadband", m.get("broadband_pct"), pct(m.get("broadband_pct")), "acs1")
        add("seasonal", "Homes held for seasonal use", m.get("seasonal_homes_pct"), pct(m.get("seasonal_homes_pct")), "acs1")
    if usa and usa.get("years"):
        last = next((y for y in usa["years"] if y["fy"] == usa["last_complete_fy"]), None)
        if last:
            add("federal", f"Federal awards, FY{last['fy']}", last["total"], money(last["total"]), "usaspending",
                "Obligations by place of performance")

    if irs and (irs.get("district") or {}).get("total_tax_liability"):
        add("income_tax", f"Federal individual income tax, {irs['tax_year']}", irs["district"]["total_tax_liability"],
            money(irs["district"]["total_tax_liability"]), "irs-soi-cd",
            "Total tax liability on individual returns; not all federal taxes")

    counties = []
    for c in (geo or {}).get("counties", []):
        cf = c["county_fips"]
        row = {k: c[k] for k in ("fips", "county_fips", "name", "short_name", "whole", "land_share",
                                 "pop_2020_county", "pop_2020_in_district", "pop_share_in_district")}
        p = (pep or {}).get("counties", {}).get(cf)
        if p:
            latest_year = str(pep["vintage"])
            row["pop_latest"] = p["estimates"][latest_year]
            row["pop_latest_year"] = int(latest_year)
            row["pop_change_pct"] = 100 * (p["estimates"][latest_year] - p["base_2020"]) / p["base_2020"]
            row["natural_change"] = p["components_since_2020"]["naturalchg"]
            row["net_migration"] = p["components_since_2020"]["netmig"]
            row["pop_series"] = p["estimates"]
        a = (acs or {}).get("counties", {}).get(cf)
        if a:
            row["acs"] = {k: a["metrics"].get(k) for k in (
                "median_household_income", "median_age", "age_65_plus_pct", "poverty_pct", "bachelors_plus_pct",
                "broadband_pct", "veterans_pct", "seasonal_homes_pct", "median_home_value", "uninsured_pct")}
        s = (laus or {}).get("series", {}).get(cf)
        if s:
            row["unemployment"] = s[-1]
        q = (qcew or {}).get("counties", {}).get(cf)
        if q:
            row["jobs"] = q["jobs"]
            row["avg_annual_pay"] = q["avg_annual_pay"]
            row["top_private_sector"] = q["private_sectors"][0]["label"] if q["private_sectors"] else None
        u = (usa or {}).get("counties_whole", {}).get(cf)
        if u:
            row["federal_awards"] = u["amount"]
        counties.append(row)

    sources: dict[str, dict] = {}
    for name, ds in data.items():
        for s in (ds or {}).get("sources", []):
            sources.setdefault(s["id"], s)
    for n in notes:
        for s in n.get("sources", []):
            sources.setdefault(s["id"], {"id": s["id"], "apa": s["apa"], "url": s["url"], "publisher": "",
                                         "title": "", "kind": "Reference"})

    month = (laus or {}).get("latest_month")
    for c in counties:  # compare every county in the same month
        s_ = (laus or {}).get("series", {}).get(c["county_fips"]) or []
        c["unemployment"] = next((p for p in reversed(s_) if p["date"] == month), None) if month else None
    rates = [c["unemployment"]["rate"] for c in counties if c.get("unemployment")]

    def rate_at(key):
        pts = (laus or {}).get("series", {}).get(key) or []
        return next((p["rate"] for p in pts if p["date"] == month), None)
    member = (leg or {}).get("current")
    return {
        "district": {"id": d.id, "name": d.name, "short_name": d.short_name, "tagline": d.tagline,
                     "state": d.state_name, "publisher": d.publisher, "site_url": d.site_url, "repo": d.repo,
                     "congress": d.congress},
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "headline": headline,
        "member": member,
        "members_count": len((leg or {}).get("members", [])),
        "unemployment": {"month": (laus or {}).get("latest_month"), "month_label": month_name((laus or {}).get("latest_month")),
                         "county_min": min(rates) if rates else None, "county_max": max(rates) if rates else None,
                         "state": rate_at("state"), "us": rate_at("us")},
        "latest_election": (ele or {}).get("results", [None])[-1] if ele and ele.get("results") else None,
        "votes": {k: (votes or {}).get(k) for k in ("missed_pct", "house_missed_pct", "with_party_majority_pct",
                                                    "on_winning_side_pct", "votes_cast", "yes_no_votes_while_held")} if votes else None,
        "counties": counties,
        "sources": sorted(sources.values(), key=lambda s: (s.get("publisher") or "", s.get("title") or "")),
        "integrity": integrity["summary"],
        "freshness": {k: v.get("updated") for k, v in manifest.get("sources", {}).items()},
        "status": {k: v.get("status") for k, v in manifest.get("sources", {}).items()},
    }
