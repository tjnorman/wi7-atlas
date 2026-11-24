"""Major public works in the district that involve federal money (data/curated/projects.yaml).

These are not pulled from a data file. Each fact was read from an official project page or
press release, and the page is named beside it. The build refuses a fact without a listed
source and warns once the review date has passed, since schedules move.
"""

from __future__ import annotations

from datetime import date

import yaml

from ..config import ROOT, District
from ..provenance import Source

PATH = ROOT / "data" / "curated" / "projects.yaml"


def fetch(fetcher, d: District, path=PATH, today: date | None = None) -> tuple[dict, list[Source], list[dict]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    today = today or date.today()
    projects, sources, missing = [], {}, []
    for p in raw.get("projects", []):
        ids = {s["id"] for s in p.get("sources", [])}
        for item in list(p.get("facts", [])) + list(p.get("timeline", [])):
            if item.get("source") not in ids:
                missing.append(f"{p['id']}: {item.get('label') or item.get('date')}")
        for s in p.get("sources", []):
            sources[s["id"]] = Source(id=s["id"], publisher=s["publisher"], title=s["title"], url=s["url"],
                                      year=str(s["year"]), kind=s.get("kind", "Web page"))
        projects.append({k: p.get(k) for k in ("id", "title", "place", "county", "summary", "links", "facts", "timeline")}
                        | {"sources": sorted(ids)})
    if missing:
        raise ValueError("Project facts without a listed source: " + "; ".join(missing))
    review_by = raw.get("review_by")
    overdue = bool(review_by) and today > date.fromisoformat(str(review_by))
    checks = [{
        "id": "projects-sourced", "title": "Every project fact names an official source",
        "status": "warn" if overdue else "pass", "sources": sorted(sources), "values": {"projects": len(projects)},
        "detail": (f"{sum(len(p['facts']) + len(p['timeline']) for p in projects)} facts across {len(projects)} project(s), "
                   f"each tied to a listed page. Read on {raw.get('verified_on')}; due for re-reading by {review_by}."
                   + (" The review date has passed." if overdue else "")),
    }]
    payload = {"projects": projects, "verified_on": str(raw.get("verified_on")), "review_by": str(review_by),
               "note": "Dates and costs are the agencies' published plans as of the date read, and can change."}
    return payload, list(sources.values()), checks
