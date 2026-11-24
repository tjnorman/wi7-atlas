"""Small geometry helpers: is a point inside the district, and in which county part."""

from __future__ import annotations

import json
import pathlib


def _polygons(geometry: dict) -> list:
    if not geometry:
        return []
    return [geometry["coordinates"]] if geometry["type"] == "Polygon" else list(geometry["coordinates"])


def _in_ring(lon: float, lat: float, ring: list) -> bool:
    inside = False
    for i in range(len(ring)):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[i - 1][0], ring[i - 1][1]
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def contains(geometry: dict, lon: float, lat: float) -> bool:
    return any(_in_ring(lon, lat, p[0]) and not any(_in_ring(lon, lat, h) for h in p[1:]) for p in _polygons(geometry))


class DistrictShape:
    """The district's simplified boundary and county parts, as written by the geography build."""

    def __init__(self, path: pathlib.Path):
        raw = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        self.district = [f["geometry"] for f in raw["district"]["features"]]
        self.parts = [(f["properties"], f["geometry"]) for f in raw.get("parts", {}).get("features", [])]
        xs = [pt[0] for g in self.district for p in _polygons(g) for pt in p[0]]
        ys = [pt[1] for g in self.district for p in _polygons(g) for pt in p[0]]
        self.bbox = (min(xs), min(ys), max(xs), max(ys))

    def inside(self, lon: float, lat: float) -> bool:
        w, s, e, n = self.bbox
        return w <= lon <= e and s <= lat <= n and any(contains(g, lon, lat) for g in self.district)

    def county(self, lon: float, lat: float) -> dict | None:
        for props, geom in self.parts:
            if contains(geom, lon, lat):
                return props
        return None
