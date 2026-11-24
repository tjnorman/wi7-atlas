"""Radio and television stations that transmit from inside the district.

Source: the Federal Communications Commission's AM, FM, and TV query tools, which return
the licensing record for each station: call sign, frequency or channel, community of
licence, licensee, and transmitter coordinates.

What "in the district" means here: the station's transmitter stands inside the district
outline. A second, shorter list holds stations licensed to a community in the district whose
transmitter stands outside it. Stations from Duluth, Eau Claire, Green Bay, Wausau's
neighbors, and the Twin Cities that are received in parts of the district but neither
transmit from it nor are licensed to it are not listed: reception depends on terrain and
power, and the atlas does not model it.

The query output has no column names, so every row is checked for the expected shape
(hemisphere letters and plausible coordinates in fixed positions) before it is used.
"""

from __future__ import annotations

import pathlib
import re
from datetime import datetime, timezone

from ..config import District
from ..geo import DistrictShape
from ..http import Fetcher
from ..provenance import Source

BASE = "https://transition.fcc.gov/fcc-bin/{tool}"
QUERIES = [  # (tool, extra parameters, band)
    ("amq", {}, "AM"),
    ("fmq", {"serv": "FM"}, "FM"),
    ("fmq", {"serv": "FL"}, "FM"),
    ("tvq", {}, "TV"),
]
# FCC service codes kept, and the plain words used for them.
KINDS = {"AM": "AM radio", "FM": "FM radio", "FL": "Low-power FM radio",
         "DTV": "Full-power television", "DCA": "Class A television", "LPD": "Low-power television"}
CALL = re.compile(r"^[KW][A-Z]{2,3}(-(FM|TV|LP|LD|CD|DT|CA))?$")


def parse_row(line: str) -> dict | None:
    """One station record, or None when the line does not have the expected shape."""
    c = [x.strip() for x in line.split("|")]
    if len(c) < 28 or c[19] not in ("N", "S") or c[23] not in ("E", "W"):
        return None
    try:
        lat = (float(c[20]) + float(c[21]) / 60 + float(c[22]) / 3600) * (1 if c[19] == "N" else -1)
        lon = (float(c[24]) + float(c[25]) / 60 + float(c[26]) / 3600) * (-1 if c[23] == "W" else 1)
    except ValueError:
        return None
    return {"call": c[1], "frequency": re.sub(r"\s+", " ", c[2]) if c[2] not in ("", "-") else None,
            "service": c[3], "channel": c[4] or None, "status": c[9], "city": c[10].title(), "state": c[11],
            "facility_id": c[18], "lat": round(lat, 5), "lon": round(lon, 5),
            "licensee": c[27].title() if c[27] not in ("", "-") else None}


def near(shape: DistrictShape, lon: float, lat: float, deg: float = 0.6) -> bool:
    w, s, e, n = shape.bbox
    return w - deg <= lon <= e + deg and s - deg <= lat <= n + deg


def fetch(fetcher: Fetcher, d: District, shape_path: pathlib.Path, county_names: dict[str, str],
          communities: set[str]) -> tuple[dict, list[Source], list[dict]]:
    """communities: upper-case names of cities and villages in the district (for the community-of-licence list)."""
    shape = DistrictShape(shape_path)
    inside: dict[str, dict] = {}
    licensed_here: dict[str, dict] = {}
    lines = shaped = 0
    odd_calls: list[str] = []
    for tool, extra, band in QUERIES:
        text = fetcher.text(BASE.format(tool=tool), params={"state": d.state_abbr, "status": "L", "list": "4", **extra},
                            encoding="latin-1")
        for line in text.splitlines():
            if line.count("|") < 20:
                continue
            lines += 1
            r = parse_row(line)
            if not r or not (30 <= r["lat"] <= 50 and -100 <= r["lon"] <= -80):
                continue
            shaped += 1
            if r["status"] != "LIC" or r["service"] not in KINDS or r["state"] != d.state_abbr:
                continue
            if not CALL.match(r["call"]):
                odd_calls.append(r["call"])
                continue
            key = f"{r['service']}-{r['facility_id']}"
            rec = {**{k: r[k] for k in ("call", "frequency", "channel", "city", "licensee", "facility_id", "lat", "lon")},
                   "band": band, "kind": KINDS[r["service"]]}
            if band == "TV":
                rec["frequency"] = None
            else:
                rec["channel"] = None
            if shape.inside(r["lon"], r["lat"]):
                part = shape.county(r["lon"], r["lat"]) or {}
                rec["transmitter_county"] = county_names.get(part.get("county_fips") or "")
                inside.setdefault(key, rec)
            elif r["city"].upper() in communities and near(shape, r["lon"], r["lat"]):
                licensed_here.setdefault(key, rec)
    if not lines or shaped / lines < 0.95:
        raise ValueError(f"FCC query output does not have the expected layout: {shaped} of {lines} rows could be read")
    order = lambda s: (["AM", "FM", "TV"].index(s["band"]), s["city"], s["call"])
    stations = sorted(inside.values(), key=order)
    outside = sorted(licensed_here.values(), key=order)
    by_band = {b: sum(1 for s in stations if s["band"] == b) for b in ("AM", "FM", "TV")}
    checks = [{
        "id": "fcc-layout", "title": "FCC station records have the expected layout",
        "status": "pass" if not odd_calls else "warn", "sources": ["fcc-queries"],
        "values": {"rows": lines, "readable": shaped},
        "detail": f"{shaped:,} of {lines:,} rows had hemisphere letters and plausible coordinates in the expected positions."
                  + (f" Skipped {len(odd_calls)} licensed records without a standard call sign: {', '.join(odd_calls[:6])}." if odd_calls else ""),
    }]
    payload = {
        "count": len(stations), "by_band": by_band, "stations": stations,
        "licensed_to_district_community_transmitter_outside": outside,
        "kinds": KINDS,
        "rule": ("Listed: licensed stations whose transmitter stands inside the district outline. Translators and boosters "
                 "are left out. Stations that are received in the district from transmitters outside it are not listed."),
        "as_of": datetime.now(timezone.utc).date().isoformat(),
    }
    src = Source(
        id="fcc-queries",
        publisher="Federal Communications Commission, Media Bureau",
        title="AM Query, FM Query, and TV Query: licensed broadcast stations",
        url="https://www.fcc.gov/media/radio/am-query",
        year=str(datetime.now(timezone.utc).year),
        query=BASE.format(tool="fmq") + f"?state={d.state_abbr}&serv=FM&status=L&list=4 (and amq, tvq)",
        notes=("Licensing records as of the retrieval date; the FCC updates them continuously. The output has no column "
               "names, so each row's layout is checked before use. Coordinates are transmitter sites."),
    )
    return payload, [src], checks
