"""Public road cameras inside the district.

Camera locations come from Open Eagle Eye, a public registry of still-image cameras
(https://github.com/stuchapin909/Open-Eagle-Eye, MIT licence, (c) 2026 stuchapin909).
The atlas stores only each camera's name, position, and address. Images load from the
agency that runs the camera and remain that agency's.

The acceptance rules below are adapted from tools/cameras/eagle-eye.mjs in
Normansrule/global-intelligence-atlas, reused here with the author's permission (NOTICE.md).
"""

from __future__ import annotations

import pathlib
import re
import urllib.parse

from ..config import District
from ..geo import DistrictShape
from ..http import Fetcher
from ..provenance import Source

REGISTRY = "https://raw.githubusercontent.com/stuchapin909/Open-Eagle-Eye/master/cameras.json"
BARE_IP = re.compile(r"^(\d+\.){3}\d+$|^\[?[0-9a-f:]+\]?$", re.I)
SECRET = re.compile(r"[?&](pass(word)?|pwd|passwd|token|auth|sig|signature|key)=", re.I)
OPERATORS = {"511wi.gov": "Wisconsin Department of Transportation (511 Wisconsin)",
             "public.carsprogram.org": "State transportation department (CARS program)"}


def needs_sign_in(cam: dict) -> bool:
    auth = cam.get("auth")
    return bool(auth.get("required")) if isinstance(auth, dict) else bool(auth)


def reject_reason(cam: dict) -> str:
    """Why a registry record cannot be used, or '' when it can."""
    try:
        lat, lon = float(cam["coordinates"]["lat"]), float(cam["coordinates"]["lng"])
    except (KeyError, TypeError, ValueError):
        return "no position"
    if abs(lat) > 90 or abs(lon) > 180 or (lat == 0 and lon == 0):
        return "no position"
    if needs_sign_in(cam):
        return "needs a sign-in"
    if cam.get("verified") is False:
        return "not verified by the registry"
    u = urllib.parse.urlsplit(str(cam.get("url") or ""))
    if u.scheme != "https" or not u.hostname:
        return "not HTTPS"
    if BARE_IP.match(u.hostname):
        return "bare IP address"
    if u.username or u.password or SECRET.search("?" + u.query):
        return "address carries credentials"
    return ""


def fetch(fetcher: Fetcher, d: District, shape_path: pathlib.Path, county_names: dict[str, str]) -> tuple[dict, list[Source], list[dict]]:
    shape = DistrictShape(shape_path)
    registry = fetcher.json(REGISTRY)
    cams, rejected = [], {}
    for cam in registry:
        coords = cam.get("coordinates") if isinstance(cam, dict) else None
        if not isinstance(coords, dict):
            continue
        try:
            lat, lon = float(coords["lat"]), float(coords["lng"])
        except (KeyError, TypeError, ValueError):
            continue
        if not shape.inside(lon, lat):
            continue
        why = reject_reason(cam)
        if why:
            rejected[why] = rejected.get(why, 0) + 1
            continue
        host = urllib.parse.urlsplit(cam["url"]).hostname
        part = shape.county(lon, lat) or {}
        cams.append({
            "id": str(cam.get("id")), "name": str(cam.get("name") or "Road camera"), "lat": round(lat, 5), "lon": round(lon, 5),
            "image_url": cam["url"], "kind": cam.get("category") or "highway",
            "county_fips": part.get("county_fips"), "county": county_names.get(part.get("county_fips") or ""),
            "host": host, "operator": OPERATORS.get(host, host),
        })
    cams.sort(key=lambda c: (c["county"] or "", c["name"]))
    payload = {"count": len(cams), "registry_total": len(registry), "rejected_inside_district": rejected, "cameras": cams,
               "boundary_note": "Cameras are placed with the simplified district outline, so one that sits on the line may be counted on either side."}
    src = Source(
        id="open-eagle-eye",
        publisher="Open Eagle Eye (stuchapin909)",
        title="Public camera registry",
        url="https://github.com/stuchapin909/Open-Eagle-Eye",
        year="2026",
        query=REGISTRY,
        notes=("A volunteer-maintained list of public still-image cameras, published under the MIT licence. The atlas keeps "
               "name, position, and address only. Images belong to the agency that runs each camera and load from that "
               "agency. The registry does not list every camera an agency operates."),
    )
    return payload, [src], []
