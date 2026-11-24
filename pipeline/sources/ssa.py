"""Social Security and SSI in the district, from the Social Security Administration.

Source: SSA's annual "Congressional Statistics" fact sheets, which give the number of people
receiving Social Security (OASDI) and Supplemental Security Income in each congressional
district in December, and the total paid that month.

These are benefit payments to people. They are not in the award totals from USAspending,
which leave out most payments to individuals at the district level.

The page's own table headings are checked before a column is used, and the districts are
added up and compared with the state row.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from html.parser import HTMLParser

import yaml

from ..config import ROOT, District
from ..http import Fetcher, FetchError
from ..provenance import Source

PAGE = "https://www.ssa.gov/policy/docs/factsheets/cong_stats/{y}/{st}.html"
INDEX = "https://www.ssa.gov/policy/docs/factsheets/cong_stats/"
OASDI_COLS = ["beneficiaries", "retired_workers", "disabled_workers", "widowers_and_parents", "spouses", "children",
              "monthly_benefits_thousands", "monthly_benefits_retired_thousands", "monthly_benefits_widowers_thousands",
              "age_65_or_older"]
SSI_COLS = ["recipients", "aged", "blind", "disabled", "under_18", "age_18_to_64", "age_65_or_older",
            "monthly_payments_thousands", "payments_aged_thousands", "payments_blind_thousands",
            "payments_disabled_thousands", "also_receiving_oasdi"]
OASDI_HEADINGS = ("number of beneficiaries", "total monthly benefits", "thousands of dollars", "retired", "65 or older")
SSI_HEADINGS = ("number of recipients", "total monthly payments", "thousands of dollars", "blind", "oasdi")


class Tables(HTMLParser):
    """Every table on a page as (heading text, list of body rows)."""

    def __init__(self):
        super().__init__()
        self.tables: list[dict] = []
        self._t = self._row = self._cell = None
        self._in_head = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._t = {"head": [], "rows": [], "caption": []}
        elif self._t is not None and tag in ("thead", "caption"):
            self._in_head = True
        elif self._t is not None and tag == "tr":
            self._row = []
        elif self._row is not None and tag in ("td", "th"):
            self._cell = []

    def handle_endtag(self, tag):
        if tag == "table" and self._t is not None:
            self.tables.append(self._t)
            self._t = None
        elif tag in ("thead", "caption"):
            self._in_head = False
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None and self._t is not None:
            (self._t["head"] if self._in_head else self._t["rows"]).append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)
        elif self._t is not None and self._in_head:
            self._t["caption"].append(data)


def _num(s: str) -> float | None:
    s = s.replace(",", "").strip()
    return float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else None


def pick(tables: list[dict], headings: tuple[str, ...], width: int) -> dict | None:
    for t in tables:
        text = " ".join(" ".join(r) for r in t["head"]).lower() + " " + " ".join(t["caption"]).lower()
        if all(h in text for h in headings) and any(len(r) == width + 1 for r in t["rows"]):
            return t
    return None


def rows_by_label(table: dict, cols: list[str]) -> dict[str, dict[str, float]]:
    out = {}
    for r in table["rows"]:
        if len(r) != len(cols) + 1:
            continue
        vals = [_num(x) for x in r[1:]]
        if all(v is not None for v in vals):
            out[re.sub(r"\s+[a-z]$", "", r[0]).strip()] = dict(zip(cols, vals))
    return out


def curated(d: District) -> dict | None:
    path = ROOT / "data" / "curated" / "ssa.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None


def fetch(fetcher: Fetcher, d: District) -> tuple[dict, list[Source], list[dict]]:
    now = datetime.now(timezone.utc)
    html = year = None
    errors: list[str] = []
    for y in range(now.year, now.year - 4, -1):
        try:
            html = fetcher.text(PAGE.format(y=y, st=d.state_abbr.lower()), retries=1)
            year = y
            break
        except FetchError as exc:
            errors.append(f"{y}: {str(exc)[:160]}")
            continue
    key = str(d.district_number)
    copied = None
    if year is None:
        # SSA's site refuses automated requests. Fall back to the tables copied from the public page.
        copied = curated(d)
        if copied is None:
            raise FetchError("No SSA Congressional Statistics page could be read. " + " | ".join(errors))
        year = int(copied["year"])
        oasdi = {str(k): dict(zip(OASDI_COLS, map(float, v))) for k, v in copied["oasdi"].items()}
        ssi = {str(k): dict(zip(SSI_COLS, map(float, v))) for k, v in (copied.get("ssi") or {}).items()}
        released_text = copied.get("released")
        named_congress = copied.get("district_lines_congress")
    else:
        parser = Tables()
        parser.feed(html)
        oasdi_t = pick(parser.tables, OASDI_HEADINGS, len(OASDI_COLS))
        if oasdi_t is None:
            heads = [" ".join(" ".join(r) for r in t["head"])[:160] for t in parser.tables]
            raise ValueError(f"SSA page for {year} has no table with the expected Social Security headings. Found: {heads}")
        oasdi = rows_by_label(oasdi_t, OASDI_COLS)
        ssi_t = pick(parser.tables, SSI_HEADINGS, len(SSI_COLS))
        ssi = rows_by_label(ssi_t, SSI_COLS) if ssi_t else {}
        lines_note = re.search(r"district definitions for the (\d+)(?:th|st|nd|rd) Congress", html)
        released_text = None
        try:
            index_text = fetcher.text(INDEX, retries=1)
            m = re.search(rf"Congressional Statistics, {year}\s*\(released ([A-Za-z]+ \d{{4}})\)", re.sub(r"<[^>]+>", " ", index_text))
            released_text = m.group(1) if m else None
            lines_note = lines_note or re.search(r"district definitions for the (\d+)(?:th|st|nd|rd) Congress", index_text)
        except FetchError:
            pass
        named_congress = int(lines_note.group(1)) if lines_note else None
    if key not in oasdi or d.state_name not in oasdi:
        raise ValueError(f"SSA table is missing district {key} or the {d.state_name} row; rows: {list(oasdi)[:14]}")

    def shape(o: dict, s: dict | None) -> dict:
        out = {
            "beneficiaries": o["beneficiaries"], "retired_workers": o["retired_workers"], "disabled_workers": o["disabled_workers"],
            "age_65_or_older": o["age_65_or_older"], "monthly_benefits": o["monthly_benefits_thousands"] * 1000,
            "average_monthly_benefit": o["monthly_benefits_thousands"] * 1000 / o["beneficiaries"] if o["beneficiaries"] else None,
        }
        if s:
            out["ssi_recipients"] = s["recipients"]
            out["ssi_monthly_payments"] = s["monthly_payments_thousands"] * 1000
        return out

    district_rows = {k: v for k, v in oasdi.items() if k.isdigit()}
    total_people = sum(v["beneficiaries"] for v in district_rows.values())
    total_money = sum(v["monthly_benefits_thousands"] for v in district_rows.values())
    st = oasdi[d.state_name]
    close = lambda a, b: abs(a - b) <= 0.01 * max(a, b, 1)
    ok = close(total_people, st["beneficiaries"]) and close(total_money, st["monthly_benefits_thousands"])
    checks = [{
        "id": "ssa-state-sum", "title": f"{d.state_name}'s districts add up to the state total in the SSA tables",
        "status": "pass" if ok else "fail", "sources": ["ssa-cong-stats"],
        "values": {"districts": total_people, "state_row": st["beneficiaries"]},
        "detail": f"Beneficiaries: {len(district_rows)} districts sum to {total_people:,.0f}; state row {st['beneficiaries']:,.0f}. "
                  f"Monthly benefits: ${total_money * 1000:,.0f} against ${st['monthly_benefits_thousands'] * 1000:,.0f} (tolerance 1%).",
    }]
    if ssi and d.state_name in ssi:
        ssi_people = sum(v["recipients"] for k, v in ssi.items() if k.isdigit())
        ssi_ok = close(ssi_people, ssi[d.state_name]["recipients"])
        checks.append({"id": "ssa-ssi-sum", "title": f"{d.state_name}'s districts add up to the state total for SSI",
                       "status": "pass" if ssi_ok else "fail", "sources": ["ssa-cong-stats"],
                       "values": {"districts": ssi_people, "state_row": ssi[d.state_name]["recipients"]},
                       "detail": f"SSI recipients: districts sum to {ssi_people:,.0f}; state row {ssi[d.state_name]['recipients']:,.0f}."})
        if not ssi_ok:
            ssi = {}
    if named_congress:
        named = int(named_congress)
        same = d.expectations.get("lines_unchanged_since_congress")
        good = named >= d.congress or (same is not None and named >= int(same))
        checks.append({"id": "ssa-district-lines", "title": "SSA tables use the current district lines",
                       "status": "pass" if good else "warn", "sources": ["ssa-cong-stats"],
                       "values": {"ssa_congress": named, "atlas_congress": d.congress},
                       "detail": f"SSA states that its {year} tables use district definitions for the {named}th Congress; "
                                 f"this atlas uses the {d.congress}th."})
    if not ok:
        raise ValueError(checks[0]["detail"])
    payload = {
        "year": year, "as_of": f"December {year}", "released": released_text,
        "retrieval": ({"method": "copied from the public page", "verified_on": str(copied.get("verified_on")),
                       "review_by": str(copied.get("review_by")),
                       "why": "SSA's website refuses automated requests, so the build cannot download the page."}
                      if copied else {"method": "downloaded by the build"}),
        "district": shape(oasdi[key], ssi.get(key)), "state": shape(st, ssi.get(d.state_name)),
        "note": ("Counts are people receiving a benefit in December, and dollars are the total paid for that one month. "
                 "The atlas does not multiply by twelve, because benefits change during the year."),
        "not_published": "Social Security payroll taxes paid are not published by congressional district.",
    }
    src = Source(
        id="ssa-cong-stats",
        publisher="Social Security Administration, Office of Retirement and Disability Policy",
        title=f"Congressional statistics, December {year}: {d.state_name}",
        url=PAGE.format(y=year, st=d.state_abbr.lower()),
        year=(released_text.split()[-1] if released_text else "n.d."),
        vintage=f"December {year}",
        query=PAGE.format(y=year, st=d.state_abbr.lower()),
        accessed=(str(copied["verified_on"]) if copied else datetime.now(timezone.utc).date().isoformat()),
        notes=(("Copied from the public page because SSA's website refuses automated requests; the build checks that the "
                "districts add up to the state row. " if copied else "")
               + "Beneficiaries in current-payment status and total monthly benefits, from SSA's Master Beneficiary Record "
               "and Supplemental Security Record, placed in districts with Postal Service geographic data."),
    )
    return payload, [src], checks
