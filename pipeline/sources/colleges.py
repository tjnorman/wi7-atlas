"""Colleges and universities in the district, from the federal directory of institutions.

Source: National Center for Education Statistics, IPEDS, Institutional Characteristics
directory file (HD). It lists every institution that takes part in federal student aid,
with its location, website, sector, and size class.

IPEDS lists an institution once, at its main address. Branch campuses and outreach centers
(for example, a technical college's other campuses, or a University of Wisconsin branch
campus) are not separate rows, so they do not appear here unless they report on their own.

Each variable is confirmed against the IPEDS data dictionary before use, and code values
(control, level, size) are read from the dictionary rather than written into this file.
"""

from __future__ import annotations

import csv
import io
import pathlib
import re
import zipfile
from datetime import datetime, timezone

from ..config import District
from ..geo import DistrictShape
from ..http import Fetcher, FetchError
from ..provenance import Source

DATA_URL = "https://nces.ed.gov/ipeds/datacenter/data/HD{y}.zip"
DICT_URL = "https://nces.ed.gov/ipeds/datacenter/data/HD{y}_Dict.zip"
# variable -> words its dictionary title must contain
EXPECT = {
    "INSTNM": ("name",), "CITY": ("city",), "STABBR": ("state",), "WEBADDR": ("web",),
    "LONGITUD": ("longitude",), "LATITUDE": ("latitude",), "CNGDSTCD": ("congressional district",),
    "CONTROL": ("control",), "ICLEVEL": ("level",), "INSTSIZE": ("size",), "CYACTIVE": ("active",),
    "COUNTYNM": ("county",), "CLOSEDAT": ("closed",),
}
REQUIRED = ("INSTNM", "STABBR", "LONGITUD", "LATITUDE", "CYACTIVE")
CODED = ("CONTROL", "ICLEVEL", "INSTSIZE")


def read_dictionary(raw: bytes) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """(variable -> title, variable -> {code -> label}) from the IPEDS dictionary workbook."""
    import openpyxl

    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".xlsx"))
        wb = openpyxl.load_workbook(io.BytesIO(z.read(name)), read_only=True, data_only=True)
    titles: dict[str, str] = {}
    codes: dict[str, dict[str, str]] = {}
    for ws in wb.worksheets:
        rows = ws.iter_rows(values_only=True)
        header = [str(c or "").strip().lower() for c in next(rows, [])]
        if "varname" not in header:
            continue
        iv = header.index("varname")
        if "vartitle" in header:
            it = header.index("vartitle")
            for r in rows:
                if r and r[iv] and r[it]:
                    titles.setdefault(str(r[iv]).strip().upper(), str(r[it]).strip())
        elif "codevalue" in header and "valuelabel" in header:
            ic, il = header.index("codevalue"), header.index("valuelabel")
            for r in rows:
                if r and r[iv] is not None and r[ic] is not None and r[il]:
                    codes.setdefault(str(r[iv]).strip().upper(), {})[str(r[ic]).strip()] = str(r[il]).strip()
    return titles, codes


def verify(titles: dict[str, str]) -> tuple[set[str], list[str]]:
    good, bad = set(), []
    for var, words in EXPECT.items():
        title = titles.get(var)
        if title and all(w in title.lower() for w in words):
            good.add(var)
        else:
            bad.append(f"{var}: expected {' + '.join(words)!r}, dictionary says {title!r}")
    return good, bad


def read_directory(raw: bytes) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        name = next((n for n in names if "_rv" in n.lower()), names[0])  # a revised file replaces the first release
        text = z.read(name).decode("utf-8-sig", "replace")
    return [{(k or "").strip().upper(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(io.StringIO(text))]


def file_year(raw: bytes) -> str | None:
    """Year the data file inside the download was last written, from the archive's own record."""
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        years = [i.date_time[0] for i in z.infolist() if i.filename.lower().endswith(".csv")]
    return str(max(years)) if years else None


def website(addr: str) -> str | None:
    addr = addr.strip()
    if not addr or " " in addr or "." not in addr:
        return None
    addr = re.sub(r"^https?://", "", addr, flags=re.I)
    return f"https://{addr}"


def fetch(fetcher: Fetcher, d: District, shape_path: pathlib.Path) -> tuple[dict, list[Source], list[dict]]:
    now = datetime.now(timezone.utc)
    raw = year = None
    for y in range(now.year, now.year - 5, -1):
        try:
            raw = fetcher.fetch(DATA_URL.format(y=y), retries=1)
            zipfile.ZipFile(io.BytesIO(raw)).namelist()
            year = y
            break
        except (FetchError, zipfile.BadZipFile):
            continue
    if year is None:
        raise FetchError("No IPEDS directory file found for the last five years")
    titles, codes = read_dictionary(fetcher.fetch(DICT_URL.format(y=year)))
    good, bad = verify(titles)
    missing = [v for v in REQUIRED if v not in good]
    if missing:
        raise ValueError("IPEDS dictionary does not confirm required variables. " + " | ".join(bad))

    shape = DistrictShape(shape_path)
    label = lambda var, code: codes.get(var, {}).get(str(code)) if var in good else None
    rows, disagree = [], []
    for r in read_directory(raw):
        if r.get("STABBR") != d.state_abbr:
            continue
        try:
            lat, lon = float(r["LATITUDE"]), float(r["LONGITUD"])
        except (KeyError, ValueError):
            continue
        inside = shape.inside(lon, lat)
        coded = (r.get("CNGDSTCD") or "").lstrip("0") == d.geoid.lstrip("0") if "CNGDSTCD" in good else None
        if coded is not None and coded != inside:
            disagree.append(f"{r['INSTNM']} ({r.get('CITY', '')}): IPEDS district code {r.get('CNGDSTCD')}, "
                            f"{'inside' if inside else 'outside'} the outline")
        if not inside:
            continue
        active = r.get("CYACTIVE") == "1"
        closed = r.get("CLOSEDAT", "") if "CLOSEDAT" in good else ""
        part = shape.county(lon, lat) or {}
        rows.append({
            "unitid": r.get("UNITID"), "name": r["INSTNM"], "city": r.get("CITY") if "CITY" in good else None,
            "county_fips": part.get("county_fips"),
            "county": re.sub(r"\s+County$", "", r.get("COUNTYNM", "")) if "COUNTYNM" in good else None,
            "lat": round(lat, 5), "lon": round(lon, 5),
            "website": website(r.get("WEBADDR", "")) if "WEBADDR" in good else None,
            "control": label("CONTROL", r.get("CONTROL")), "level": label("ICLEVEL", r.get("ICLEVEL")),
            "size": label("INSTSIZE", r.get("INSTSIZE")),
            "active": active, "closed": closed if closed and closed not in ("-2", "-1") else None,
        })
    rows.sort(key=lambda c: (not c["active"], c["name"]))
    checks = [
        {"id": "ipeds-labels", "title": "College directory variables match the IPEDS dictionary",
         "status": "pass" if not bad else "warn", "sources": ["nces-ipeds-hd"], "values": {},
         "detail": f"{len(good)} of {len(EXPECT)} variables confirmed against the {year} dictionary."
                   + (" Not used: " + "; ".join(bad) if bad else "")},
        {"id": "ipeds-district", "title": "IPEDS district codes agree with the district outline",
         "status": "pass" if not disagree else "warn", "sources": ["nces-ipeds-hd", "census-cb"],
         "values": {"listed": len(rows), "disagree": len(disagree)},
         "detail": (f"All {len(rows)} institutions inside the outline carry this district's code in IPEDS, and no other "
                    f"{d.state_name} institution does." if not disagree else
                    f"{len(disagree)} differ; the atlas lists by location. " + "; ".join(disagree[:6]))},
    ]
    payload = {
        "directory_year": year, "count": len(rows), "active_count": sum(1 for c in rows if c["active"]),
        "institutions": rows,
        "coverage_note": ("IPEDS lists each institution once, at its main address. Branch campuses and outreach centers "
                          "inside the district that report under a parent institution are not listed."),
    }
    src = Source(
        id="nces-ipeds-hd",
        publisher="National Center for Education Statistics",
        title=f"Integrated Postsecondary Education Data System (IPEDS): Institutional Characteristics directory file, HD{year}",
        url="https://nces.ed.gov/ipeds/use-the-data",
        year=file_year(raw) or "n.d.",
        vintage=f"HD{year}",
        query=DATA_URL.format(y=year),
        notes=("The directory of institutions that take part in federal student aid programs. An institution appears "
               "once, at its main address; branch campuses that do not report separately are not listed."),
    )
    return payload, [src], checks
