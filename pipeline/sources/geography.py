"""Where the district is: boundaries, counties, and split counties.

Three Census products, each checked against the others:
  1. Cartographic boundary files (shapes for the map).
  2. The 119th Congressional District to county relationship file (which
     counties touch the district and how much land each part has).
  3. The 2020 Census 119th Congressional District Summary File (how many
     people live in each county part).
"""

from __future__ import annotations

import csv
import io
import json
import pathlib
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone

from .. import census
from ..config import District
from ..http import Fetcher, FetchError
from ..provenance import Source

SQ_M_PER_SQ_MI = 2_589_988.110336
GENZ = "https://www2.census.gov/geo/tiger/GENZ{y}/shp/cb_{y}_us_{layer}_500k.zip"
REL = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/cd-sld/tab20_cd{c}20_county20_st{s}.txt"


def _shapes(zip_bytes: bytes, keep) -> list[dict]:
    import shapefile  # pyshp

    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp) / "layer.zip"
        p.write_bytes(zip_bytes)
        reader = shapefile.Reader(str(p))
        fields = [f[0] for f in reader.fields[1:]]
        feats = []
        for sr in reader.iterShapeRecords():
            props = dict(zip(fields, sr.record))
            if keep(props):
                feats.append({"type": "Feature", "properties": props, "geometry": sr.shape.__geo_interface__})
        return feats


def _cd_field(props: dict, congress: int) -> str | None:
    for k in (f"CD{congress}FP", "CDFP", "CD119FP", "CD118FP"):
        if k in props:
            return str(props[k])
    return None


def relationship(fetcher: Fetcher, d: District) -> tuple[list[dict], str]:
    url = REL.format(c=d.congress, s=d.state_fips)
    try:
        text = fetcher.text(url, encoding="utf-8-sig")
    except FetchError:  # fall back to the national file
        url = url.replace(f"_st{d.state_fips}.txt", "_natl.txt")
        text = fetcher.text(url, encoding="utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text), delimiter="|"))
    cd_col = f"GEOID_CD{d.congress}_20"
    parts = []
    for r in rows:
        if r.get(cd_col) != d.geoid:
            continue
        land_part = int(r["AREALAND_PART"] or 0)
        land_county = int(r["AREALAND_COUNTY_20"] or 0)
        parts.append({
            "fips": r["GEOID_COUNTY_20"],
            "county_fips": r["GEOID_COUNTY_20"][2:],
            "name": r["NAMELSAD_COUNTY_20"],
            "land_part_sq_m": land_part,
            "land_county_sq_m": land_county,
            "water_part_sq_m": int(r["AREAWATER_PART"] or 0),
            "land_share": (land_part / land_county) if land_county else 0.0,
        })
    return parts, url


def county_part_population(fetcher: Fetcher, d: District) -> tuple[dict[str, int], int | None, str]:
    """2020 Census population of each county part inside the district."""
    errors = []
    for ds in (f"2020/dec/cd{d.congress}", "2020/dec/cd118"):
        try:
            rows = census.query(
                fetcher, ds, ["P1_001N"], "county (or part):*",
                f"state:{d.state_fips} congressional district:{d.district}",
            )
            total = census.query(fetcher, ds, ["P1_001N"], f"congressional district:{d.district}",
                                 f"state:{d.state_fips}")
            parts = {r["county (or part)"]: int(r["P1_001N"]) for r in rows if r.get("P1_001N") is not None}
            return parts, int(total[0]["P1_001N"]) if total else None, ds
        except (FetchError, KeyError, IndexError) as exc:
            errors.append(f"{ds}: {exc}")
    raise FetchError("County-part populations unavailable: " + "; ".join(errors))


def county_population_2020(fetcher: Fetcher, d: District) -> dict[str, int]:
    rows = census.query(fetcher, "2020/dec/pl", ["P1_001N"], "county:*", f"state:{d.state_fips}")
    return {r["county"]: int(r["P1_001N"]) for r in rows}


def boundaries(fetcher: Fetcher, d: District, out_dir: pathlib.Path) -> tuple[dict, str]:
    """Download cartographic boundaries and write TopoJSON + GeoJSON."""
    year_now = datetime.now(timezone.utc).year
    last_error = None
    for y in (year_now - 1, year_now - 2, year_now - 3):
        try:
            cd_zip = fetcher.fetch(GENZ.format(y=y, layer=f"cd{d.congress}"))
            parts_zip = fetcher.fetch(GENZ.format(y=y, layer=f"county_within_cd{d.congress}"))
            county_zip = fetcher.fetch(GENZ.format(y=y, layer="county"))
            state_zip = fetcher.fetch(GENZ.format(y=y, layer="state"))
            break
        except FetchError as exc:
            last_error = exc
    else:
        raise FetchError(f"No cartographic boundary files found: {last_error}")

    st = d.state_fips
    all_districts = _shapes(cd_zip, lambda p: str(p.get("STATEFP")) == st)
    ranking = sorted(((_cd_field(f["properties"], d.congress), int(f["properties"].get("ALAND") or 0)) for f in all_districts),
                     key=lambda x: -x[1])
    district = [f for f in all_districts if _cd_field(f["properties"], d.congress) == d.district]
    parts = _shapes(parts_zip, lambda p: str(p.get("STATEFP")) == st and _cd_field(p, d.congress) == d.district)
    counties = _shapes(county_zip, lambda p: str(p.get("STATEFP")) == st)
    state = _shapes(state_zip, lambda p: str(p.get("STATEFP")) == st)
    if not district or not parts:
        raise FetchError("District or county-part shapes were empty after filtering")

    def slim(feats, keep):
        for f in feats:
            f["properties"] = {k: f["properties"].get(src) for k, src in keep.items()}
        return feats

    slim(district, {"geoid": "GEOID", "name": "NAMELSAD", "aland": "ALAND", "awater": "AWATER"})
    slim(parts, {"county_fips": "COUNTYFP", "name": "NAMELSAD", "aland": "ALAND", "awater": "AWATER"})
    slim(counties, {"county_fips": "COUNTYFP", "name": "NAME", "aland": "ALAND"})
    slim(state, {"name": "NAME"})

    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = pathlib.Path(tmp)
        for name, feats in (("district", district), ("parts", parts), ("counties", counties), ("state", state)):
            (tmpdir / f"{name}.json").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
        mapshaper = shutil.which("mapshaper") or str(pathlib.Path("node_modules/.bin/mapshaper").resolve())
        files = [str(tmpdir / f"{n}.json") for n in ("district", "parts", "counties", "state")]
        subprocess.run(
            [mapshaper, "-i", *files, "combine-files",
             "-simplify", "8%", "keep-shapes", "-o", "format=topojson", "quantization=100000",
             str(out_dir / "district.topo.json")],
            check=True, capture_output=True,
        )
        (tmpdir / "simple").mkdir()
        subprocess.run(
            [mapshaper, "-i", *files, "combine-files", "-simplify", "3%", "keep-shapes",
             "-o", "format=geojson", "precision=0.0001", str(tmpdir / "simple") + "/"],
            check=True, capture_output=True,
        )
        simple = {}
        for n in ("district", "parts", "counties", "state"):
            path = tmpdir / "simple" / f"{n}.json"
            if path.exists():
                simple[n] = json.loads(path.read_text())
        (out_dir / "district.simple.geojson.json").write_text(json.dumps(simple, separators=(",", ":")))

    aland = sum(int(f["properties"]["aland"] or 0) for f in district)
    awater = sum(int(f["properties"]["awater"] or 0) for f in district)
    state_aland = sum(int(f["properties"].get("ALAND") or 0) for f in _shapes(state_zip, lambda p: str(p.get("STATEFP")) == st))
    rank = next((i + 1 for i, (cd, _) in enumerate(ranking) if cd == d.district), None)
    return {"year": y, "aland_sq_m": aland, "awater_sq_m": awater,
            "land_sq_mi": aland / SQ_M_PER_SQ_MI, "water_sq_mi": awater / SQ_M_PER_SQ_MI,
            "state_land_sq_mi": state_aland / SQ_M_PER_SQ_MI if state_aland else None,
            "share_of_state_land": aland / state_aland if state_aland else None,
            "land_rank_in_state": rank, "districts_in_state": len(ranking)}, str(y)


def fetch(fetcher: Fetcher, d: District, geo_dir: pathlib.Path) -> tuple[dict, list[Source], list[dict]]:
    rel, rel_url = relationship(fetcher, d)
    checks: list[dict] = []
    try:
        part_pop, district_pop_2020, cd_dataset = county_part_population(fetcher, d)
        pop2020 = county_population_2020(fetcher, d)
    except FetchError as exc:  # keep the map and county list; population fields stay empty
        part_pop, district_pop_2020, cd_dataset, pop2020 = {}, None, f"2020/dec/cd{d.congress}", {}
        checks.append({"id": "census-api", "title": "The Census Data API answered", "status": "fail",
                       "detail": str(exc)[:300], "sources": ["census-cd119"]})
    shapes, shape_year = boundaries(fetcher, d, geo_dir)

    counties = []
    for p in sorted(rel, key=lambda r: r["name"]):
        if p["land_part_sq_m"] <= 0:
            continue  # water-only contact (for example, Lake Superior) does not make a county part of the district
        whole = p["land_share"] > 0.999
        cf = p["county_fips"]
        counties.append({
            "fips": p["fips"],
            "county_fips": cf,
            "name": p["name"],
            "short_name": p["name"].replace(" County", ""),
            "whole": whole,
            "land_share": round(p["land_share"], 6),
            "land_part_sq_mi": p["land_part_sq_m"] / SQ_M_PER_SQ_MI,
            "pop_2020_county": pop2020.get(cf),
            "pop_2020_in_district": part_pop.get(cf),
            "pop_share_in_district": (part_pop.get(cf, 0) / pop2020[cf]) if pop2020.get(cf) and cf in part_pop else None,
        })

    payload = {
        "district_geoid": d.geoid,
        "congress": d.congress,
        "counties": counties,
        "county_count": len(counties),
        "whole_count": sum(1 for c in counties if c["whole"]),
        "split": [c["short_name"] for c in counties if not c["whole"]],
        "pop_2020": district_pop_2020,
        "pop_2020_sum_of_parts": sum(c["pop_2020_in_district"] or 0 for c in counties) if part_pop else None,
        "land_sq_mi_relationship": sum(c["land_part_sq_mi"] for c in counties),
        "boundary": shapes,
        "cd_dataset": cd_dataset,
    }
    sources = [
        Source(
            id="census-cb",
            publisher="U.S. Census Bureau",
            title=f"{shape_year} cartographic boundary files, 1:500,000: {d.congress}th congressional districts, "
                  f"county within {d.congress}th congressional district, counties, and states",
            url=f"https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html",
            year=shape_year,
            vintage=f"GENZ{shape_year}",
            query=GENZ.format(y=shape_year, layer=f"county_within_cd{d.congress}"),
        ),
        Source(
            id="census-rel",
            publisher="U.S. Census Bureau",
            title=f"{d.congress}th Congressional District to 2020 county relationship file ({d.state_name})",
            url="https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.2020.html",
            year="2024",
            query=rel_url,
        ),
        Source(
            id="census-cd119",
            publisher="U.S. Census Bureau",
            title=f"2020 Census {d.congress}th Congressional District Summary File",
            url=f"https://api.census.gov/data/{cd_dataset}",
            year="2025",
            vintage="2020 Census",
            query=f"https://api.census.gov/data/{cd_dataset}?get=NAME,P1_001N&for=county%20(or%20part):*"
                  f"&in=state:{d.state_fips}%20congressional%20district:{d.district}",
        ),
        Source(
            id="census-pl",
            publisher="U.S. Census Bureau",
            title="2020 Census redistricting data (Public Law 94-171)",
            url="https://api.census.gov/data/2020/dec/pl",
            year="2021",
            vintage="2020 Census",
        ),
    ]
    return payload, sources, checks
