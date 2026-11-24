"""Write a snapshot of aircraft currently over the district.

Web pages cannot ask flight trackers directly (the trackers send no CORS headers), so a
scheduled job runs this script and publishes the result on the `live` branch, where the
website reads it. The approach, and the order of the community sources, follow
tools/fetch-live.mjs in Normansrule/global-intelligence-atlas, reused with the author's
permission (NOTICE.md).

Positions come from volunteer ADS-B receivers. Coverage is thinner over the Northwoods than
over cities, so an empty sky here can mean no receivers heard anything.

Usage: python tools/live_snapshot.py --district wi-07 --out live
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
from datetime import datetime, timezone

import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import config  # noqa: E402
from pipeline.geo import DistrictShape  # noqa: E402

SOURCES = [
    ("adsb.lol", "https://api.adsb.lol/v2/lat/{lat}/lon/{lon}/dist/{nm}", "Open Database License 1.0", "https://www.adsb.lol/"),
    ("adsb.fi", "https://opendata.adsb.fi/api/v2/lat/{lat}/lon/{lon}/dist/{nm}", "adsb.fi open data terms", "https://adsb.fi/"),
    ("airplanes.live", "https://api.airplanes.live/v2/point/{lat}/{lon}/{nm}", "airplanes.live terms, non-commercial use", "https://airplanes.live/"),
]
USER_AGENT = "wi7-atlas live snapshot (+https://github.com/tjnorman/wi7-atlas)"


def circle(bbox: tuple[float, float, float, float]) -> tuple[float, float, int]:
    """Centre and radius (nautical miles, at most 250) of a circle that covers the bounding box."""
    w, s, e, n = bbox
    lat, lon = (s + n) / 2, (w + e) / 2
    dy = (n - s) / 2 * 60
    dx = (e - w) / 2 * 60 * math.cos(math.radians(lat))
    return round(lat, 4), round(lon, 4), min(250, math.ceil(math.hypot(dx, dy)) + 5)


def row(a: dict) -> dict | None:
    """One aircraft in the fields the site shows, or None when it has no usable position."""
    lat, lon = a.get("lat"), a.get("lon")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    alt = a.get("alt_baro")
    on_ground = alt == "ground"
    return {
        "hex": str(a.get("hex") or "").strip().lower(),
        "callsign": (a.get("flight") or "").strip() or None,
        "lat": round(lat, 4), "lon": round(lon, 4),
        "altitude_ft": None if on_ground or not isinstance(alt, (int, float)) else int(alt),
        "on_ground": on_ground,
        "speed_kt": round(a["gs"]) if isinstance(a.get("gs"), (int, float)) else None,
        "track": round(a.get("track", a.get("true_heading", 0)) or 0),
        "type": a.get("t") or None,
        "category": a.get("category") or None,
    }


def snapshot(shape: DistrictShape, get=None) -> dict:
    get = get or (lambda url: requests.get(url, timeout=25, headers={"User-Agent": USER_AGENT}).json())
    lat, lon, nm = circle(shape.bbox)
    errors = []
    for name, template, licence, home in SOURCES:
        try:
            data = get(template.format(lat=lat, lon=lon, nm=nm))
            heard = [r for r in (row(a) for a in data.get("ac") or []) if r and r["hex"]]
        except Exception as exc:  # try the next source
            errors.append(f"{name}: {type(exc).__name__}")
            continue
        over = sorted((r for r in heard if shape.inside(r["lon"], r["lat"])), key=lambda r: r["hex"])
        return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "ok": True,
                "source": name, "source_url": home, "licence": licence,
                "heard_in_circle": len(heard), "count": len(over), "aircraft": over, "errors": errors,
                "note": "Positions reported by volunteer ADS-B receivers at the time shown. Not every aircraft is heard."}
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "ok": False, "source": None,
            "count": None, "aircraft": [], "errors": errors, "note": "No flight source answered this time."}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--district", default="wi-07")
    ap.add_argument("--out", default="live")
    args = ap.parse_args()
    d = config.load(args.district)
    shape = DistrictShape(ROOT / "data" / d.id / "geo" / "district.simple.geojson.json")
    snap = snapshot(shape)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "aircraft.json").write_text(json.dumps(snap, separators=(",", ":")), encoding="utf-8")
    (out / "README.md").write_text(
        f"# {d.name}: live snapshot\n\nMachine-written by `tools/live_snapshot.py` on a schedule. "
        f"Read by {d.site_url}. Do not edit by hand.\n", encoding="utf-8")
    print(f"{snap['source']}: {snap['count']} aircraft over the district; errors: {snap['errors']}")
    return 0 if snap["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
