"""Source records and APA 7 citations.

Every dataset the pipeline writes carries a list of Source records, so any
number on the site can be traced to the publisher, the exact query, the
data vintage, and the day it was retrieved.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone

from .http import redact


def today() -> date:
    return datetime.now(timezone.utc).date()


def long_date(d: date) -> str:
    return f"{d.strftime('%B')} {d.day}, {d.year}"


@dataclass
class Source:
    id: str
    publisher: str
    title: str
    url: str                       # landing page or API endpoint a reader can open
    year: str                      # publication year or vintage used in the citation
    kind: str = "Data set"         # APA bracketed description
    query: str | None = None       # exact request, API keys removed
    vintage: str | None = None     # e.g. "ACS 2025 1-year", "Vintage 2025"
    accessed: str = field(default_factory=lambda: today().isoformat())
    notes: str | None = None

    def __post_init__(self) -> None:
        self.url = redact(self.url)
        if self.query:
            self.query = redact(self.query)

    @property
    def apa(self) -> str:
        accessed = date.fromisoformat(self.accessed)
        return (
            f"{self.publisher}. ({self.year}). {self.title} [{self.kind}]. "
            f"Retrieved {long_date(accessed)}, from {self.url}"
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["apa"] = self.apa
        return d


def dataset(payload: dict, sources: list[Source], **meta) -> dict:
    """Wrap a payload with provenance metadata."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": [s.to_dict() for s in sources],
        **meta,
        "data": payload,
    }
