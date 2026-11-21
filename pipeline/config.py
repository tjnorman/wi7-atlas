"""Load and validate a district configuration file."""

from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass, field
from typing import Any

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config" / "districts"
# Data and media locations can be redirected (tests and local previews use this).
DATA_ROOT = pathlib.Path(os.environ.get("ATLAS_DATA_ROOT", ROOT / "data"))
MEDIA_ROOT = pathlib.Path(os.environ.get("ATLAS_MEDIA_ROOT", ROOT / "docs" / "media"))


@dataclass
class District:
    id: str
    name: str
    short_name: str
    tagline: str
    state_name: str
    state_abbr: str
    state_fips: str
    district: str
    district_number: int
    congress: int
    comparable_acs1_years_from: int
    publisher: str
    repo: str
    site_url: str
    expectations: dict[str, Any] = field(default_factory=dict)
    trends: dict[str, Any] = field(default_factory=dict)
    companion_sites: list[dict[str, str]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def geoid(self) -> str:
        """Census GEOID for the district, e.g. '5507'."""
        return f"{self.state_fips}{self.district}"

    @property
    def fec_district(self) -> str:
        return self.district


def load(district_id: str = "wi-07") -> District:
    path = CONFIG_DIR / f"{district_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No district config at {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    state = data["state"]
    district = str(data["district"]).zfill(2)
    if not (state["fips"].isdigit() and len(state["fips"]) == 2):
        raise ValueError("state.fips must be a two-digit string")
    if int(district) != int(data["district_number"]):
        raise ValueError("district and district_number disagree")
    return District(
        id=data["id"],
        name=data["name"],
        short_name=data["short_name"],
        tagline=data.get("tagline", data["name"]),
        state_name=state["name"],
        state_abbr=state["abbr"],
        state_fips=state["fips"],
        district=district,
        district_number=int(data["district_number"]),
        congress=int(data["congress"]),
        comparable_acs1_years_from=int(data.get("comparable_acs1_years_from", 2022)),
        publisher=data["publisher"],
        repo=data["repo"],
        site_url=data["site_url"],
        expectations=data.get("expectations", {}),
        trends=data.get("trends", {}),
        companion_sites=data.get("companion_sites", []),
        raw=data,
    )
