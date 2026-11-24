"""Render README.md from docs/README.template.md and the data on disk.

Every sentence with a number is computed here from the data files, so the
README cannot drift from the data. Wording is deliberately plain and neutral.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from html import escape

from .charts import THEMES, FONT
from .config import DATA_ROOT, MEDIA_ROOT, ROOT, District

STATUS = {"pass": "✅ Pass", "fail": "❌ Fail", "warn": "⚠️ Review", "skip": "⏭ Not run"}


def _load(d: District, name: str) -> dict | None:
    p = DATA_ROOT / d.id / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _data(obj):
    return obj.get("data", obj) if obj else None


def money(n, short=False):
    if isinstance(n, str):
        try:
            n = float(n)
        except ValueError:
            return n
    if n is None:
        return "n/a"
    if abs(n) >= 1e9:
        return f"${n / 1e9:,.2f} billion" if not short else f"${n / 1e9:,.1f}B"
    if abs(n) >= 1e6:
        return f"${n / 1e6:,.1f} million" if not short else f"${n / 1e6:,.1f}M"
    return f"${n:,.0f}"


def pct(n, d=1):
    return "n/a" if n is None else f"{n:.{d}f}%"


def central(iso: str | None) -> datetime | None:
    """Timestamps are stored in UTC; show dates as they fall in Wisconsin (Central time)."""
    if not iso:
        return None
    from zoneinfo import ZoneInfo

    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(ZoneInfo("America/Chicago"))


def long_date(iso: str | None) -> str:
    if not iso:
        return "n/a"
    dt = central(iso) if "T" in iso else datetime.fromisoformat(iso[:10])
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"


def button(label: str, theme: str, primary: bool) -> str:
    t = THEMES[theme]
    w = 28 + int(len(label) * 9.2) + 28
    bg = t["accent"] if primary else ("#ffffff" if theme == "light" else "#1c1c1e")
    fg = "#ffffff" if primary else t["accent"]
    border = "" if primary else f' stroke="{t["accent"]}" stroke-width="1.5"'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="52" viewBox="0 0 {w} 52" role="img" '
            f'aria-label="{escape(label)}"><rect x="1" y="1" width="{w - 2}" height="50" rx="25" fill="{bg}"{border}/>'
            f'<text x="{w / 2}" y="32" text-anchor="middle" font-family="{FONT}" font-size="17" font-weight="600" '
            f'fill="{fg}">{escape(label)}</text></svg>\n')


def write_buttons() -> None:
    out = MEDIA_ROOT / "buttons"
    out.mkdir(parents=True, exist_ok=True)
    for theme in ("light", "dark"):
        (out / f"open-{theme}.svg").write_text(button("Open the atlas  →", theme, True))
        (out / f"checks-{theme}.svg").write_text(button("How it's checked", theme, False))
        (out / f"data-{theme}.svg").write_text(button("Download the data", theme, False))


def glance_table(summary: dict) -> str:
    cells = summary.get("headline", [])[:8]
    if not cells:
        return ""
    rows = [cells[:4], cells[4:8]]
    html = ["<table>"]
    for row in rows:
        if not row:
            continue
        html.append("<tr>")
        for c in row:
            html.append(f'<td align="center" width="25%"><h2>{escape(c["display"])}</h2>{escape(c["label"])}</td>')
        html.append("</tr>")
    html.append("</table>")
    return "\n".join(html)


def badges(d: District, summary: dict, n_sources: int) -> str:
    repo = d.repo
    integ = summary.get("integrity", {})
    passing, total = integ.get("pass", 0), integ.get("total", 0)
    color = "2e7d32" if integ.get("fail", 0) == 0 and integ.get("warn", 0) == 0 else ("b26a00" if integ.get("fail", 0) == 0 else "c62828")
    c = central(summary.get("built_at"))
    built = c.date().isoformat() if c else ""
    return "\n".join([
        f"[![Tests](https://github.com/{repo}/actions/workflows/tests.yml/badge.svg)](https://github.com/{repo}/actions/workflows/tests.yml)",
        f"[![Data refresh](https://github.com/{repo}/actions/workflows/data.yml/badge.svg)](https://github.com/{repo}/actions/workflows/data.yml)",
        f"[![Deploy to Pages](https://github.com/{repo}/actions/workflows/pages.yml/badge.svg)](https://github.com/{repo}/actions/workflows/pages.yml)",
        f"[![Cross-checks](https://img.shields.io/badge/cross--checks-{passing}_of_{total}_passing-{color})](#-how-every-number-is-checked)",
        f"[![Sources](https://img.shields.io/badge/primary_sources-{n_sources}-0071e3)](#-sources)",
        f"[![Data as of](https://img.shields.io/badge/data_as_of-{built.replace('-', '--')}-555)](data/{d.id}/manifest.json)",
        "![Nonpartisan](https://img.shields.io/badge/nonpartisan-follows_the_seat-555)",
        "[![License: MIT](https://img.shields.io/badge/code-MIT-1f4e9c)](LICENSE)",
    ])


def map_text(summary: dict, geo: dict | None, acs: dict | None) -> str:
    rows = [c for c in summary.get("counties", []) if c.get("pop_change_pct") is not None]
    if not rows:
        return ""
    grew = [c for c in rows if c["pop_change_pct"] > 0]
    fell = [c for c in rows if c["pop_change_pct"] < 0]
    top = max(rows, key=lambda c: c["pop_change_pct"])
    low = min(rows, key=lambda c: c["pop_change_pct"])
    year = rows[0].get("pop_latest_year")
    parts = [f"Since the 2020 Census, **{len(grew)} of the district's {len(rows)} counties have gained people and "
             f"{len(fell)} have lost people** (whole-county estimates to July {year}). "
             f"The largest gain is in **{top['short_name']} County ({top['pop_change_pct']:+.1f}%)** and the largest "
             f"decline in **{low['short_name']} County ({low['pop_change_pct']:+.1f}%)**."]
    nat = [c for c in rows if c.get("natural_change") is not None and c.get("net_migration") is not None]
    if nat:
        n_dec = sum(1 for c in nat if c["natural_change"] < 0)
        n_mig = sum(1 for c in nat if c["net_migration"] > 0)
        parts.append(f"In {n_dec} counties deaths have outnumbered births since 2020, and {n_mig} counties have "
                     f"gained people through migration.")
    b = (geo or {}).get("boundary") or {}
    if b.get("land_rank_in_state") == 1 and b.get("share_of_state_land"):
        parts.append(f"It is the largest of Wisconsin's {b['districts_in_state']} districts by land area, covering "
                     f"{b['share_of_state_land'] * 100:.0f}% of the state's land.")
    if geo:
        parts.append(f"The district had **{geo['pop_2020']:,} residents in the 2020 Census**"
                     + (f" and an estimated **{acs['district']['metrics']['population']:,.0f} in {acs['vintage']['acs1']}**."
                        if acs and acs.get("district") else "."))
    return " ".join(parts)


def people_text(acs: dict | None) -> str:
    if not acs or not acs.get("district"):
        return ""
    m, s, u = acs["district"]["metrics"], acs["state"]["metrics"], acs["us"]["metrics"]
    y = acs["vintage"]["acs1"]
    moe = acs["district"].get("moe", {})
    age_moe = f" (±{moe['median_age']:.1f})" if moe.get("median_age") else ""
    lines = [
        f"| | District | Wisconsin | United States |",
        f"|---|---:|---:|---:|",
        f"| Median age | **{m['median_age']:.1f}**{age_moe} | {s['median_age']:.1f} | {u['median_age']:.1f} |",
        f"| Age 65 and older | **{pct(m['age_65_plus_pct'])}** | {pct(s['age_65_plus_pct'])} | {pct(u['age_65_plus_pct'])} |",
        f"| Veterans (adults) | **{pct(m['veterans_pct'])}** | {pct(s['veterans_pct'])} | {pct(u['veterans_pct'])} |",
        f"| Homes held for seasonal use | **{pct(m['seasonal_homes_pct'])}** | {pct(s['seasonal_homes_pct'])} | {pct(u['seasonal_homes_pct'])} |",
        f"| Households with broadband | **{pct(m['broadband_pct'])}** | {pct(s['broadband_pct'])} | {pct(u['broadband_pct'])} |",
    ]
    aian = next((r for r in acs["district"]["race"] if r["id"] == "aian"), None)
    tribal = (f" American Indian and Alaska Native residents make up {pct(aian['pct'])} of the district "
              f"(not Hispanic, one race alone), compared with {pct(next(r for r in acs['us']['race'] if r['id'] == 'aian')['pct'])} nationally."
              if aian and aian.get("pct") is not None else "")
    return (f"American Community Survey {y} 1-year estimates. Margins of error appear on the website.{tribal}\n\n"
            + "\n".join(lines))


def work_text(acs: dict | None, summary: dict) -> str:
    out = []
    if acs and acs.get("district"):
        ind = [r for r in acs["district"]["industry"] if r["pct"] is not None]
        state = {r["id"]: r["pct"] for r in acs["state"]["industry"]}
        top = ind[0] if ind else None
        mf = next((r for r in ind if r["id"] == "manufacturing"), None)
        if top:
            out.append(f"The most common line of work for district residents is **{top['label'].lower()} ({pct(top['pct'])} of workers)**.")
        if mf:
            out.append(f"Manufacturing employs **{pct(mf['pct'])}** of working residents, compared with "
                       f"{pct(state.get('manufacturing'))} statewide.")
    u = summary.get("unemployment") or {}
    if u.get("month"):
        out.append(f"In {u['month_label']}, county unemployment rates ranged from **{u['county_min']:.1f}% to "
                   f"{u['county_max']:.1f}%**, against {u['state']:.1f}% for Wisconsin and {u['us']:.1f}% nationally "
                   f"(not seasonally adjusted; the latest month is preliminary).")
    return " ".join(out)


def taxes_text(irs: dict | None, state_name: str = "State") -> str:
    d = (irs or {}).get("district") or {}
    if not d.get("total_tax_liability"):
        return ""
    y = irs["tax_year"]
    rows = [("The district", d), (state_name, irs.get("state")), ("United States", irs.get("us"))]
    table = "\n".join(f"| {n} | {money(r['agi_per_return'])} | {money(r['tax_per_return'])} | {r['tax_share_of_agi_pct']:.1f}% |"
                      for n, r in rows if r)
    return (f"### What residents pay in federal income tax\n\n"
            f"On {d['returns']:,.0f} individual returns for tax year {y}, people living in the district reported a total "
            f"federal tax liability of **{money(d['total_tax_liability'])}**, or {d['tax_share_of_agi_pct']:.1f}% of their "
            f"adjusted gross income.\n\n| Per return, tax year {y} | Adjusted gross income | Federal income tax | Tax as a share of income |\n"
            f"|---|---:|---:|---:|\n{table}\n\n"
            f"<sub>Source: IRS Statistics of Income, congressional district data. Individual income tax returns only. "
            f"Employer payroll taxes, corporate income tax, excise taxes, and estate taxes are not published by congressional "
            f"district, so this is not the district's total federal tax, and it is not a balance against the awards above.</sub>")


def federal_text(usa: dict | None) -> tuple[str, str]:
    if not usa or not usa.get("years"):
        return "", ""
    fy = usa["last_complete_fy"]
    last = next((y for y in usa["years"] if y["fy"] == fy), None)
    text = ""
    if last:
        kinds = [(k["label"], last.get(k["id"])) for k in usa.get("award_types", []) if last.get(k["id"])]
        kinds = sorted([k for k in kinds if k[1] and k[1] > 0], key=lambda k: -k[1])
        lead = f" The largest category was {kinds[0][0].lower()} ({money(kinds[0][1])})." if kinds else ""
        text = (f"In fiscal year {fy}, federal agencies obligated **{money(last['total'])}** in contracts, grants, loans, "
                f"and other awards for work performed in the district.{lead} Obligations are commitments to spend, and "
                f"agencies revise them over time. Payments that agencies report only at the county or state level, "
                f"such as many benefits paid to individuals, are not included.")
    rows = usa.get("top_agencies", [])[:6]
    table = ""
    if rows:
        table = (f"<details><summary><b>Top awarding agencies, FY{fy}</b></summary>\n\n| Agency | Obligations |\n|---|---:|\n"
                 + "\n".join(f"| {r['name']} | {money(r['amount'])} |" for r in rows) + "\n\n</details>")
    return text, table


def representation_text(leg: dict | None, summary: dict) -> str:
    if not leg or not leg.get("current"):
        return ""
    c = leg["current"]
    members = leg.get("members", [])
    first = members[0]["start"][:4] if members else "n/a"
    return (f"The seat is held by **{c['name']} ({c['party']})**, whose current term runs from "
            f"{long_date(c['start'])} to {long_date(c['end'])}. {len(members)} people have represented the 7th District "
            f"since {first}, under boundaries redrawn after each census.")


def notes_block(notes: list[dict]) -> str:
    out = []
    for n in notes:
        if n.get("section") != "representation":
            continue
        tag = {"unofficial": "🟡 Unofficial", "scheduled": "🗓 Scheduled", "verified": "✅ Verified"}.get(n["status"], n["status"])
        srcs = " · ".join(f"[{s.get('label', s['id'])}]({s['url']})" for s in n.get("sources", []))
        out.append(f"> **{n['title']}** — {tag}, verified {long_date(n['verified_on'])}\n>\n> {n['text'].strip()}\n>\n> <sub>Sources: {srcs}</sub>")
    return "\n\n".join(out)


def votes_block(votes: dict | None) -> str:
    if not votes or not votes.get("yes_no_votes_while_held"):
        return ""
    d = votes.get("definitions", {})
    return "\n".join([
        f"<details open><summary><b>How the seat voted in the {votes['congress']}th Congress</b> "
        f"({votes['yes_no_votes_while_held']:,} yes-or-no roll calls)</summary>\n",
        "| Measure | The seat | Plain definition |",
        "|---|---:|---|",
        f"| Votes missed | **{pct(votes.get('missed_pct'))}** | {d.get('missed_pct', '')} House-wide: {pct(votes.get('house_missed_pct'))}. |",
        f"| Voted with own party's majority | **{pct(votes.get('with_party_majority_pct'))}** | {d.get('with_party_majority_pct', '')} |",
        f"| Voted on the winning side | **{pct(votes.get('on_winning_side_pct'))}** | {d.get('on_winning_side_pct', '')} |",
        "\nSource: Office of the Clerk, U.S. House of Representatives, roll call votes. The website lists the 25 most recent votes with links.\n",
        "</details>",
    ]) + attendance_block(votes)


def attendance_block(votes: dict) -> str:
    years = [y for y in votes.get("by_year") or [] if y.get("house_yes_no_roll_calls")]
    if len(years) < 2:
        return ""
    p = votes["period"]
    held = sum(y["yes_no_votes_while_held"] for y in years)
    missed = sum(y["missed"] for y in years)
    vacant = sum(y["while_seat_vacant"] for y in years)
    rows = "\n".join(
        f"| {y['year']} | {', '.join(y['members']) or 'Vacant'} | {y['yes_no_votes_while_held']:,} | {y['missed']:,} | "
        f"{pct(y['missed_pct'])} | {pct(y['house_missed_pct'])} | {y['while_seat_vacant'] or '—'} |" for y in years)
    return (f"\n\n<details open><summary><b>Attendance, {p['from_year']} to {p['to_year']}</b> "
            f"({missed:,} missed of {held:,} roll calls, {pct(100 * missed / held if held else None)})</summary>\n\n"
            f"| Year | Held by | Roll calls while held | Missed | Missed | Whole House | While vacant |\n|---|---|---:|---:|---:|---:|---:|\n{rows}\n\n"
            f"{votes['definitions'].get('not_voting', '')} "
            + (f"{vacant:,} roll calls were taken while the seat was vacant and are not counted as missed. " if vacant else "")
            + f"The website lists every missed vote with a link to the official record.\n\n</details>")


def fec_block(fec: dict | None) -> str:
    if not fec or not fec.get("cycles"):
        return ""
    cycle = max(fec["cycles"], key=int)
    rows = fec["cycles"][cycle]
    if not rows:
        return ""
    lines = [f"<details><summary><b>Campaign money, {cycle} cycle</b> (Federal Election Commission)</summary>\n",
             "| Candidate | Party | Raised | Spent | Cash on hand | Through |", "|---|---|---:|---:|---:|---|"]
    for c in rows[:10]:
        name = (c.get('name') or '').title()
        cell = f"[{name}]({c['url']})" if c.get('url') else name
        lines.append(f"| {cell} | {c.get('party') or ''} | {money(c.get('receipts'))} | "
                     f"{money(c.get('disbursements'))} | {money(c.get('cash_on_hand'))} | {(c.get('coverage_end') or '')[:10]} |")
    lines.append("\nTotals for each candidate's principal campaign committee over the two-year cycle, through its latest report. Sorted by amount raised.\n\n</details>")
    return "\n".join(lines)


def county_table(summary: dict) -> str:
    rows = summary.get("counties", [])
    if not rows:
        return ""
    y = next((c.get("pop_latest_year") for c in rows if c.get("pop_latest_year")), "")
    head = (f"<details open><summary><b>All {len(rows)} counties</b></summary>\n\n"
            f"| County | In district | Population {y} | Since 2020 | Median household income | Median age | Unemployment | Jobs (QCEW) |\n"
            "|---|---|---:|---:|---:|---:|---:|---:|")
    body = []
    for c in rows:
        a = c.get("acs") or {}
        share = "Whole" if c["whole"] else f"Part ({c['pop_share_in_district'] * 100:.0f}% of people)" if c.get("pop_share_in_district") else "Part"
        u = c.get("unemployment")
        body.append(
            f"| {c['short_name']} | {share} | {c.get('pop_latest', 0):,} | {c.get('pop_change_pct', 0):+.1f}% | "
            f"{money(a.get('median_household_income'))} | {a.get('median_age') or 0:.1f} | "
            f"{(str(u['rate']) + '%') if u else 'n/a'} | {c.get('jobs') or 0:,} |")
    foot = ("\nWhole-county figures. Population: Census Bureau estimates. Income and age: American Community Survey "
            "5-year estimates. Unemployment: BLS, latest month, not seasonally adjusted. Jobs: BLS QCEW annual average, "
            "counted where people work.\n\n</details>")
    return "\n".join([head, *body, foot])


def integrity_table(integ: dict | None) -> str:
    if not integ:
        return ""
    s = integ["summary"]
    lines = [f"**Latest build: {s.get('pass', 0)} of {s['total']} checks passing**"
             + (f", {s.get('warn', 0)} for review" if s.get("warn") else "")
             + (f", {s.get('fail', 0)} failing" if s.get("fail") else "")
             + (f", {s.get('skip', 0)} not run" if s.get("skip") else "") + ".\n",
             "| | Check | What was compared |", "|---|---|---|"]
    for c in integ["checks"]:
        lines.append(f"| {STATUS.get(c['status'], c['status'])} | {c['title']} | {c['detail']} |")
    return "\n".join(lines)


def sources_list(summary: dict) -> str:
    items = sorted({s.get("apa", "") for s in summary.get("sources", []) if s.get("apa")})
    return "\n".join(f"- {escape(i, quote=False)}" for i in items)


def receipt_example(acs_raw: dict | None) -> str:
    if not acs_raw:
        return "{}"
    src = dict(acs_raw["sources"][0])
    src.pop("notes", None)
    ex = {"generated_at": acs_raw.get("generated_at"), "sources": [src], "data": {"...": "numbers"}}
    return json.dumps(ex, indent=2)


def render(d: District) -> str:
    raw = {n: _load(d, n) for n in ("summary", "acs", "geography", "usaspending", "legislators", "elections",
                                     "fec", "votes", "integrity", "notes")}
    summary = raw["summary"] or {}
    acs, geo, usa = _data(raw["acs"]), _data(raw["geography"]), _data(raw["usaspending"])
    leg, fec, votes = _data(raw["legislators"]), _data(raw["fec"]), _data(raw["votes"])
    integ, notes = raw["integrity"], (raw["notes"] or {}).get("notes", [])
    write_buttons()
    fed_text, agencies = federal_text(usa)
    media = MEDIA_ROOT
    hero = "docs/media/hero.webp" if (media / "hero.webp").exists() else "docs/media/charts/map-light.svg"
    video = ""
    if (media / "tour.webp").exists() or (media / "tour.gif").exists():
        src = "docs/media/tour.webp" if (media / "tour.webp").exists() else "docs/media/tour.gif"
        video = (f'<p align="center"><a href="{d.site_url}media/tour.mp4"><img src="{src}" alt="A tour of the WI-7 Atlas '
                 f'website: the district map draws itself, then the people, work, federal dollars, and representation '
                 f'sections scroll past" width="100%" /></a></p>\n<p align="center"><sub>A 40-second tour of the website. '
                 f'Click for the full-quality video.</sub></p>')
    gallery = ""
    screens = media / "screens"
    picks = [("land", "The scroll-driven map: each step recolors the counties"), ("people", "How the district compares with Wisconsin and the nation"),
             ("seat", "The seat: members, notes, votes, and elections"), ("trust", "Every cross-check, in public")]
    if all((screens / f"{n}-light.png").exists() for n, _ in picks):
        cells = []
        for n, cap in picks:
            cells.append(f'<td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/media/screens/{n}-dark.png" />'
                         f'<img src="docs/media/screens/{n}-light.png" alt="{escape(cap)}" width="100%" /></picture><br/><sub>{escape(cap)}</sub></td>')
        gallery = ("## 🖼 Gallery\n\n<table>\n<tr>" + "".join(cells[:2]) + "</tr>\n<tr>" + "".join(cells[2:]) + "</tr>\n</table>")
    a = acs or {}
    values = {
        "gallery": gallery,
        "site_url": d.site_url,
        "tagline": d.tagline,
        "hero": hero,
        "hero_alt": f"Animated map of {d.name}: the district outline draws itself and its 26 counties light up",
        "district_id": d.id,
        "badges": badges(d, summary, len({s.get('publisher') for s in summary.get('sources', []) if s.get('publisher')})),
        "glance": glance_table(summary),
        "glance_note": (f"People, income, age, and homes: American Community Survey {a.get('vintage', {}).get('acs1')} 1-year estimates. "
                        f"Land and counties: U.S. Census Bureau, 119th Congress boundaries. Federal awards: USAspending.gov."),
        "check_count": str(len((integ or {}).get("checks", []))),
        "video_block": video,
        "map_alt": f"Map of {d.name} with counties shaded by population change since 2020",
        "map_text": map_text(summary, geo, acs),
        "people_text": people_text(acs),
        "work_text": work_text(acs, summary),
        "federal_text": fed_text,
        "taxes_text": taxes_text(_data(_load(d, "irs")), d.state_name),
        "agencies_table": agencies,
        "representation_text": representation_text(leg, summary),
        "notes_block": notes_block(notes),
        "votes_block": votes_block(votes),
        "fec_block": fec_block(fec),
        "county_table": county_table(summary),
        "integrity_table": integrity_table(integ),
        "receipt_example": receipt_example(raw["acs"]),
        "sources_list": sources_list(summary),
        "publisher": d.publisher,
        "repo": d.repo,
        "repo_name": d.repo.split("/")[-1],
        "built_date": long_date(summary.get("built_at")),
    }
    template = (ROOT / "docs" / "README.template.md").read_text(encoding="utf-8")
    text = re.sub(r"\{\{(\w+)\}\}", lambda m: values.get(m.group(1), ""), template)
    text = re.sub(r"\n{3,}", "\n\n", text)
    out = ROOT / "README.md" if DATA_ROOT == ROOT / "data" else MEDIA_ROOT / "README.preview.md"
    out.write_text(text, encoding="utf-8")
    print(f"  readme: {out}")
    return text
