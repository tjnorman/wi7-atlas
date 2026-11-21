"""End-to-end test of the boundary step on tiny synthetic shapefiles shaped like the Census files."""

from __future__ import annotations

import io
import json
import pathlib
import shutil
import zipfile

import pytest

from conftest import FakeFetcher

ROOT = pathlib.Path(__file__).resolve().parent.parent
HAS_MAPSHAPER = shutil.which("mapshaper") or (ROOT / "node_modules" / ".bin" / "mapshaper").exists()


def square(x0, y0, size):
    return [[x0, y0], [x0, y0 + size], [x0 + size, y0 + size], [x0 + size, y0], [x0, y0]]


def shp_zip(fields: list[tuple], records: list[tuple[list, list]]) -> bytes:
    import shapefile

    shp, shx, dbf = io.BytesIO(), io.BytesIO(), io.BytesIO()
    w = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, shapeType=shapefile.POLYGON)
    for f in fields:
        w.field(*f)
    for ring, rec in records:
        w.poly([ring])
        w.record(*rec)
    w.close()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for ext, b in (("shp", shp), ("shx", shx), ("dbf", dbf)):
            z.writestr(f"layer.{ext}", b.getvalue())
    return buf.getvalue()


@pytest.mark.skipif(not HAS_MAPSHAPER, reason="mapshaper not installed (npm ci)")
def test_boundaries_writes_topojson_and_computes_area(district, tmp_path, monkeypatch):
    from pipeline.sources import geography

    monkeypatch.chdir(ROOT)
    cd_fields = [("STATEFP", "C", 2), ("CD119FP", "C", 2), ("GEOID", "C", 4), ("NAMELSAD", "C", 40), ("ALAND", "N", 14), ("AWATER", "N", 14)]
    cd = shp_zip(cd_fields, [
        (square(-91, 45, 1), ["55", "07", "5507", "Congressional District 7", 9_000_000_000, 100]),
        (square(-89, 43, 0.5), ["55", "02", "5502", "Congressional District 2", 2_000_000_000, 100]),
        (square(-95, 45, 1), ["27", "07", "2707", "Congressional District 7", 9_999_999_999, 100]),
    ])
    parts = shp_zip(
        [("STATEFP", "C", 2), ("CD119FP", "C", 2), ("COUNTYFP", "C", 3), ("NAMELSAD", "C", 40), ("ALAND", "N", 14), ("AWATER", "N", 14)],
        [(square(-91, 45, 0.5), ["55", "07", "003", "Ashland County", 1, 0]),
         (square(-90.5, 45, 0.5), ["55", "07", "017", "Chippewa County", 1, 0])])
    counties = shp_zip([("STATEFP", "C", 2), ("COUNTYFP", "C", 3), ("NAME", "C", 40), ("ALAND", "N", 14)],
                       [(square(-91, 45, 0.5), ["55", "003", "Ashland", 1]), (square(-90.5, 45, 0.6), ["55", "017", "Chippewa", 1])])
    state = shp_zip([("STATEFP", "C", 2), ("NAME", "C", 40), ("ALAND", "N", 14)],
                    [(square(-93, 42, 6), ["55", "Wisconsin", 36_000_000_000])])

    def route(url, _):
        for key, body in (("_cd119_", cd), ("county_within_cd119", parts), ("_us_county_", counties), ("_us_state_", state)):
            if key in url:
                return body
        from pipeline.http import FetchError
        return FetchError("404")

    f = FakeFetcher([(r"county_within_cd119", parts), (r"cb_\d+_us_cd119_", cd), (r"_us_county_500k", counties),
                     (r"_us_state_500k", state)])
    info, year = geography.boundaries(f, district, tmp_path)
    topo = json.loads((tmp_path / "district.topo.json").read_text())
    assert set(topo["objects"]) >= {"district", "parts", "counties", "state"}
    assert len(topo["objects"]["parts"]["geometries"]) == 2
    assert len(topo["objects"]["district"]["geometries"]) == 1  # Minnesota's 7th is filtered out
    assert info["land_rank_in_state"] == 1 and info["districts_in_state"] == 2
    assert info["share_of_state_land"] == pytest.approx(0.25)
    simple = json.loads((tmp_path / "district.simple.geojson.json").read_text())
    assert simple["parts"]["features"][0]["properties"]["county_fips"] in {"003", "017"}
