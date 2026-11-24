"""IRS Statistics of Income: individual income tax returns by congressional district.

What this is: totals from Form 1040 returns filed by people whose address is in the
district. What it is not: all federal taxes. Employer-side payroll taxes, corporate
income tax, excise taxes, and estate and gift taxes are not in this file, and the IRS
does not publish them by congressional district.

The CSV has no labels, so each variable is checked against the description in the IRS
documentation guide for the same tax year before it is used. A variable whose
description does not match is not published.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from datetime import datetime, timezone
from xml.etree import ElementTree

from ..config import District
from ..http import Fetcher, FetchError
from ..provenance import Source

CSV_URL = "https://www.irs.gov/pub/irs-soi/{yy}incd.csv"
DOC_URL = "https://www.irs.gov/pub/irs-soi/{yy}incddocguide.docx"
PAGE_URL = "https://www.irs.gov/statistics/soi-tax-stats-data-by-congressional-district-{year}"

# variable -> (our name, words its IRS description must contain, is a dollar amount)
VARS: dict[str, tuple[str, tuple[str, ...], bool]] = {
    "N1": ("returns", ("number of returns",), False),
    "A00100": ("agi", ("gross income",), True),
    "A10300": ("total_tax_liability", ("total tax liability",), True),
    "A06500": ("income_tax_after_credits", ("income tax after credits",), True),
    "A11902": ("refunds", ("overpayments refunded",), True),
    "A11901": ("tax_due_at_filing", ("tax due at time of filing",), True),
}
REQUIRED = ("N1", "A00100", "A10300")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_year(raw: bytes) -> str | None:
    """Year the document was last modified, from its own properties."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            core = z.read("docProps/core.xml").decode("utf-8", "replace")
    except (KeyError, zipfile.BadZipFile):
        return None
    m = re.search(r"<dcterms:modified[^>]*>(\d{4})-", core) or re.search(r"<dcterms:created[^>]*>(\d{4})-", core)
    return m.group(1) if m else None


def docx_rows(raw: bytes) -> tuple[list[list[str]], str]:
    """Table rows (as lists of cell text) and the full text of a .docx file."""
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        root = ElementTree.fromstring(z.read("word/document.xml"))

    def text(el) -> str:
        return re.sub(r"\s+", " ", "".join(t.text or "" for t in el.iter(f"{W}t"))).strip()

    rows = [[text(tc) for tc in tr.iter(f"{W}tc")] for tr in root.iter(f"{W}tr")]
    paragraphs = [text(p) for p in root.iter(f"{W}p")]
    return rows, "\n".join(p for p in paragraphs if p)


def describe(rows: list[list[str]]) -> dict[str, str]:
    """Variable name -> its description, from the documentation's variable table."""
    out: dict[str, str] = {}
    for cells in rows:
        for i, cell in enumerate(cells):
            name = cell.strip().upper()
            if name in VARS and name not in out:
                out[name] = " ".join(c for j, c in enumerate(cells) if j != i and c)
    return out


def verify(descriptions: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Variables whose description matches what we expect, and messages for those that do not."""
    good, bad = {}, []
    for var, (_, words, _) in VARS.items():
        desc = descriptions.get(var)
        if desc and all(w in desc.lower() for w in words):
            good[var] = desc
        else:
            bad.append(f"{var}: expected {' + '.join(words)!r}, documentation says {desc!r}")
    return good, bad


def congresses(doc_text: str) -> list[int]:
    return sorted({int(n) for n in re.findall(r"\b(1\d\d)(?:th|st|nd|rd) Congress", doc_text)})


def _num(v) -> float:
    try:
        return float(str(v).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def parse(text: str, variables: list[str]) -> dict[tuple[int, int], dict[int, dict[str, float]]]:
    """(state fips, district) -> AGI class -> variable -> value, as published (dollars in thousands)."""
    out: dict[tuple[int, int], dict[int, dict[str, float]]] = {}
    reader = csv.DictReader(io.StringIO(text))
    for raw in reader:
        row = {(k or "").strip().upper(): v for k, v in raw.items()}
        try:
            key = (int(_num(row["STATEFIPS"])), int(_num(row["CONG_DISTRICT"])))
            stub = int(_num(row.get("AGI_STUB", 0)))
        except KeyError as exc:
            raise ValueError(f"IRS file is missing column {exc}; columns are {sorted(row)[:12]}") from exc
        out.setdefault(key, {})[stub] = {v: _num(row.get(v)) for v in variables}
    return out


def totals(classes: dict[int, dict[str, float]] | None, variables: list[str]) -> tuple[dict | None, dict | None]:
    """(published total row or None, sum of the AGI classes or None)."""
    if not classes:
        return None, None
    published = classes.get(0)
    parts = [v for k, v in classes.items() if k != 0]
    summed = {v: sum(p[v] for p in parts) for v in variables} if parts else None
    return published, summed


def shape(tot: dict[str, float], variables: list[str]) -> dict:
    """Convert a totals row to dollars and add the ratios people ask about."""
    out: dict[str, float | None] = {}
    for var in variables:
        name, _, is_amount = VARS[var]
        out[name] = tot[var] * 1000 if is_amount else tot[var]
    n, agi, tax = out.get("returns"), out.get("agi"), out.get("total_tax_liability")
    out["agi_per_return"] = agi / n if n and agi is not None else None
    out["tax_per_return"] = tax / n if n and tax is not None else None
    out["tax_share_of_agi_pct"] = 100 * tax / agi if agi and tax is not None else None
    return out


def fetch(fetcher: Fetcher, d: District) -> tuple[dict, list[Source], list[dict]]:
    now = datetime.now(timezone.utc)
    text = year = None
    for y in range(now.year - 1, now.year - 7, -1):
        try:
            text = fetcher.text(CSV_URL.format(yy=str(y)[2:]), encoding="latin-1")
        except FetchError:
            continue
        if "CONG_DISTRICT" in text[:4000].upper():
            year = y
            break
    if year is None:
        raise FetchError("No IRS congressional district file found for the last six tax years")
    yy = str(year)[2:]

    doc_raw = fetcher.fetch(DOC_URL.format(yy=yy))
    rows, doc_text = docx_rows(doc_raw)
    good, bad = verify(describe(rows))
    missing = [v for v in REQUIRED if v not in good]
    if missing:
        raise ValueError("IRS documentation does not confirm required variables. " + " | ".join(bad))
    if "thousands of dollars" not in doc_text.lower():
        raise ValueError("IRS documentation does not state that amounts are in thousands of dollars")
    variables = list(good)

    table = parse(text, variables)
    state, dist = int(d.state_fips), d.district_number
    if (state, dist) not in table:
        raise ValueError(f"District {d.state_abbr}-{d.district} is not in the IRS tax year {year} file")

    # A value can carry the right label and still be wrong in the file. Any amount larger than
    # half of the district's adjusted gross income is not believable for a tax, refund, or
    # balance due, so it is withheld and reported instead of published.
    probe = totals(table[(state, dist)], variables)
    probe = probe[0] or probe[1]
    implausible = [v for v in variables if v not in ("N1", "A00100") and probe[v] > 0.5 * probe["A00100"]]
    if any(v in REQUIRED for v in implausible):
        raise ValueError(f"IRS value fails the plausibility test: {implausible}")
    for v in implausible:
        bad.append(f"{v}: value {probe[v] * 1000:,.0f} is more than half of adjusted gross income; withheld")
        variables.remove(v)
        good.pop(v)

    def best(classes):
        published, summed = totals(classes, variables)
        return published or summed, published, summed

    d_tot, d_pub, d_sum = best(table[(state, dist)])
    state_districts = [k for k in table if k[0] == state and k[1] != 0]
    s_pub_tot, _, _ = best(table.get((state, 0)))
    s_sum = {v: sum(best(table[k])[0][v] for k in state_districts) for v in variables} if state_districts else None
    s_tot = s_pub_tot or s_sum
    us = {v: 0.0 for v in variables}
    for st in sorted({k[0] for k in table if 1 <= k[0] <= 56}):
        st_tot = best(table.get((st, 0)))[0]
        if st_tot is None:
            parts = [best(table[k])[0] for k in table if k[0] == st and k[1] != 0]
            st_tot = {v: sum(p[v] for p in parts) for v in variables}
        for v in variables:
            us[v] += st_tot[v]

    checks: list[dict] = []

    def check(id_, title, status, detail, values=None):
        checks.append({"id": id_, "title": title, "status": status, "detail": detail,
                       "sources": ["irs-soi-cd"], "values": values or {}})

    check("irs-labels", "IRS variables match their published descriptions",
          "pass" if not bad else "warn",
          f"{len(good)} of {len(VARS)} variables confirmed against the tax year {year} documentation guide "
          f"and within plausible range."
          + (" Not published: " + "; ".join(bad) if bad else ""))

    def close(a, b, tol):
        return a is not None and b is not None and (abs(a - b) <= tol * max(abs(a), abs(b), 1))

    if d_pub and d_sum:
        ok = all(close(d_pub[v], d_sum[v], 0.01) for v in ("N1", "A00100", "A10300"))
        check("irs-classes-sum", "IRS income classes add up to the district total", "pass" if ok else "fail",
              f"Total tax liability: published total ${d_pub['A10300'] * 1000:,.0f}; sum of income classes "
              f"${d_sum['A10300'] * 1000:,.0f} (tolerance 1%; the IRS rounds and suppresses small cells).",
              {"published": d_pub["A10300"] * 1000, "summed": d_sum["A10300"] * 1000})
    if s_pub_tot and s_sum:
        ok = close(s_pub_tot["N1"], s_sum["N1"], 0.02) and close(s_pub_tot["A10300"], s_sum["A10300"], 0.02)
        check("irs-state-sum", f"{d.state_name}'s districts add up to the state total in the IRS file",
              "pass" if ok else "warn",
              f"Returns: state row {s_pub_tot['N1']:,.0f}; sum of {len(state_districts)} districts {s_sum['N1']:,.0f} "
              f"(tolerance 2%; returns the IRS could not place in a district are counted only in the state row).",
              {"state_row": s_pub_tot["N1"], "district_sum": s_sum["N1"]})

    found = congresses(doc_text)
    same_since = d.expectations.get("lines_unchanged_since_congress")
    if not found:
        check("irs-district-lines", "IRS file uses the current district lines", "warn",
              "The documentation guide does not name the Congress whose district lines it uses.")
    else:
        newest = max(found)
        ok = newest >= d.congress or (same_since is not None and newest >= int(same_since))
        why = (f" {d.state_name}'s lines have not changed since the {same_since}th Congress."
               if same_since and newest < d.congress else "")
        check("irs-district-lines", "IRS file uses the current district lines", "pass" if ok else "warn",
              f"The tax year {year} documentation names the {newest}th Congress; this atlas uses the "
              f"{d.congress}th.{why}", {"irs_congress": newest, "atlas_congress": d.congress})

    payload = {
        "tax_year": year,
        "filed_in": year + 1,
        "congress_named_in_documentation": found,
        "variables": {VARS[v][0]: {"irs_variable": v, "description": good[v]} for v in variables},
        "not_published": bad,
        "district": shape(d_tot, variables),
        "state": shape(s_tot, variables) if s_tot else None,
        "us": shape(us, variables),
        "us_scope": "Sum of the 50 states and the District of Columbia",
        "excludes": ["Employer share of payroll taxes", "Corporate income tax", "Excise taxes",
                     "Estate and gift taxes", "Customs duties"],
        "as_of": now.date().isoformat(),
    }
    src = Source(
        id="irs-soi-cd",
        publisher="Internal Revenue Service, Statistics of Income Division",
        title=f"Individual income tax returns: Congressional district data, tax year {year}",
        url=PAGE_URL.format(year=year),
        year=docx_year(doc_raw) or "n.d.",
        vintage=f"Tax year {year}",
        query=CSV_URL.format(yy=yy),
        notes=("Totals from individual income tax returns (Form 1040) filed during the following calendar year. "
               "The IRS assigns returns to districts by the ZIP code on the return. Amounts are published in "
               "thousands of dollars. This is not all federal tax: employer payroll taxes, corporate, excise, "
               "and estate taxes are not published by congressional district."),
    )
    return payload, [src], checks
