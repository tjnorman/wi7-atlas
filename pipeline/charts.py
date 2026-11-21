"""README charts: hand-built SVG in light and dark, drawn from the data on disk.

Design rules:
  * Party colors appear only on election charts. Everything else uses a
    neutral palette so no chart reads as partisan.
  * Every chart names its source and data vintage in its own footer.
  * Animations are subtle, CSS-only, and switched off for readers who ask
    for reduced motion.
"""

from __future__ import annotations

import json
import math
import pathlib
from datetime import datetime
from html import escape

from .config import DATA_ROOT, MEDIA_ROOT, ROOT, District

OUT = MEDIA_ROOT / "charts"
FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'SF Pro Text', 'Segoe UI', Inter, Helvetica, Arial, sans-serif"

THEMES = {
    "light": {
        "ink": "#1d1d1f", "muted": "#6e6e73", "faint": "#86868b", "grid": "#e8e8ed", "panel": "#f5f5f7",
        "accent": "#0071e3", "accent2": "#5ac8fa", "state": "#86868b", "us": "#c7c7cc", "land": "#f2f2f4",
        "edge": "#ffffff", "grow": "#0f9d8a", "shrink": "#d98a1f", "zero": "#e3e3e8",
        "rep": "#c9453b", "dem": "#2f66c9", "oth": "#a1a1a6", "band": "#0071e3",
    },
    "dark": {
        "ink": "#f5f5f7", "muted": "#a1a1a6", "faint": "#8e8e93", "grid": "#2c2c2e", "panel": "#1c1c1e",
        "accent": "#2997ff", "accent2": "#64d2ff", "state": "#98989d", "us": "#636366", "land": "#1c1c1e",
        "edge": "#0d1117", "grow": "#30c8b0", "shrink": "#f0a24a", "zero": "#3a3a3c",
        "rep": "#ef6a5e", "dem": "#5b8ef0", "oth": "#8e8e93", "band": "#2997ff",
    },
}

STYLE = """
<style>
  text {{ font-family: {font}; fill: {ink}; }}
  .muted {{ fill: {muted}; }}
  .faint {{ fill: {faint}; }}
  .title {{ font-size: 22px; font-weight: 700; letter-spacing: -0.02em; }}
  .sub {{ font-size: 14px; }}
  .label {{ font-size: 13px; }}
  .small {{ font-size: 11px; }}
  .value {{ font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; }}
  .grow {{ transform-box: fill-box; transform-origin: left center; animation: grow 1.1s cubic-bezier(.2,.8,.2,1) both; }}
  .rise {{ transform-box: fill-box; transform-origin: center bottom; animation: rise 1.1s cubic-bezier(.2,.8,.2,1) both; }}
  .fade {{ animation: fade .9s ease-out both; }}
  .draw {{ stroke-dasharray: 4000; stroke-dashoffset: 4000; animation: draw 2.4s cubic-bezier(.4,0,.2,1) .2s forwards; }}
  @keyframes grow {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
  @keyframes rise {{ from {{ transform: scaleY(0); }} to {{ transform: scaleY(1); }} }}
  @keyframes fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
  @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
  @media (prefers-reduced-motion: reduce) {{
    .grow, .rise, .fade {{ animation: none; }}
    .draw {{ animation: none; stroke-dashoffset: 0; }}
  }}
</style>
"""


class SVG:
    def __init__(self, w: int, h: int, theme: str, title: str, desc: str):
        self.w, self.h, self.t = w, h, THEMES[theme]
        self.parts: list[str] = []
        self.head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-labelledby="t d">'
            f"<title id=\"t\">{escape(title)}</title><desc id=\"d\">{escape(desc)}</desc>"
            + STYLE.format(font=FONT, **self.t)
        )

    def add(self, s: str) -> None:
        self.parts.append(s)

    def text(self, x, y, s, cls="label", anchor="start", fill=None, extra=""):
        f = f' style="fill:{fill}"' if fill else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{anchor}"{f} {extra}>{escape(str(s))}</text>')

    def rect(self, x, y, w, h, fill, rx=0, cls="", delay=0.0, opacity=1.0):
        style = f' style="animation-delay:{delay:.2f}s"' if delay else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" height="{max(h, 0):.1f}" rx="{rx}" '
                 f'fill="{fill}" fill-opacity="{opacity}" class="{cls}"{style}/>')

    def line(self, x1, y1, x2, y2, stroke, width=1.0, dash=None, opacity=1.0):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" '
                 f'stroke-width="{width}" stroke-opacity="{opacity}"{d}/>')

    def circle(self, x, y, r, fill, cls="", delay=0.0, stroke=None):
        style = f' style="animation-delay:{delay:.2f}s"' if delay else ""
        s = f' stroke="{stroke}" stroke-width="2"' if stroke else ""
        self.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" class="{cls}"{s}{style}/>')

    def footer(self, source: str):
        self.text(24, self.h - 16, source, cls="small faint")

    def render(self) -> str:
        return self.head + "".join(self.parts) + "</svg>\n"


def load(d: District, name: str) -> dict | None:
    p = DATA_ROOT / d.id / f"{name}.json"
    if not p.exists():
        return None
    obj = json.loads(p.read_text(encoding="utf-8"))
    return obj.get("data", obj)


def write(name: str, theme: str, svg: SVG) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}-{theme}.svg").write_text(svg.render(), encoding="utf-8")


def nice_max(v: float) -> float:
    if v <= 0:
        return 1
    e = 10 ** math.floor(math.log10(v))
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if v <= m * e:
            return m * e
    return 10 * e


def money_short(n: float) -> str:
    if abs(n) >= 1e9:
        return f"${n / 1e9:.1f}B"
    if abs(n) >= 1e6:
        return f"${n / 1e6:.0f}M"
    return f"${n:,.0f}"


def spread(items: list[list], gap: float) -> list[list]:
    """Nudge label y positions apart so none are closer than gap."""
    items = sorted(items, key=lambda it: it[0])
    for _ in range(50):
        moved = False
        for a, b in zip(items, items[1:]):
            if b[0] - a[0] < gap:
                push = (gap - (b[0] - a[0])) / 2
                a[0] -= push
                b[0] += push
                moved = True
        if not moved:
            break
    return items


# ---------------------------------------------------------------- map

class LCC:
    """Lambert conformal conic projection fitted to a bounding box."""

    def __init__(self, lat1=44.0, lat2=46.5, lat0=45.0, lon0=-90.5):
        r = math.radians
        self.lon0 = r(lon0)
        p1, p2, p0 = r(lat1), r(lat2), r(lat0)
        self.n = math.log(math.cos(p1) / math.cos(p2)) / math.log(math.tan(math.pi / 4 + p2 / 2) / math.tan(math.pi / 4 + p1 / 2))
        self.F = math.cos(p1) * math.tan(math.pi / 4 + p1 / 2) ** self.n / self.n
        self.rho0 = self.F / math.tan(math.pi / 4 + p0 / 2) ** self.n
        self.k, self.dx, self.dy = 1.0, 0.0, 0.0

    def raw(self, lon, lat):
        rho = self.F / math.tan(math.pi / 4 + math.radians(lat) / 2) ** self.n
        th = self.n * (math.radians(lon) - self.lon0)
        return rho * math.sin(th), -(self.rho0 - rho * math.cos(th))

    def fit(self, coords, x0, y0, x1, y1):
        pts = [self.raw(*c) for c in coords]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        self.k = min((x1 - x0) / (max(xs) - min(xs)), (y1 - y0) / (max(ys) - min(ys)))
        self.dx = x0 + ((x1 - x0) - self.k * (max(xs) - min(xs))) / 2 - self.k * min(xs)
        self.dy = y0 + ((y1 - y0) - self.k * (max(ys) - min(ys))) / 2 - self.k * min(ys)

    def __call__(self, lon, lat):
        x, y = self.raw(lon, lat)
        return self.dx + self.k * x, self.dy + self.k * y


def rings(geom):
    if not geom:
        return []
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def path(geom, proj) -> str:
    out = []
    for poly in rings(geom):
        for ring in poly:
            pts = [proj(*c[:2]) for c in ring]
            out.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
    return "".join(out)


def centroid(geom, proj):
    best, best_a = None, 0
    for poly in rings(geom):
        pts = [proj(*c[:2]) for c in poly[0]]
        a = cx = cy = 0.0
        for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
            cr = x0 * y1 - x1 * y0
            a += cr
            cx += (x0 + x1) * cr
            cy += (y0 + y1) * cr
        if a and abs(a) > best_a:
            best_a, best = abs(a), (cx / (3 * a), cy / (3 * a))
    return best


def chart_map(d: District, theme: str, geo: dict, summary: dict) -> SVG | None:
    gj = DATA_ROOT / d.id / "geo" / "district.simple.geojson.json"
    if not gj.exists():
        return None
    shapes = json.loads(gj.read_text())
    t = THEMES[theme]
    W, H = 960, 860
    svg = SVG(W, H, theme, f"Map of {d.name}",
              "The district's 26 counties shaded by population change since 2020; split counties show only "
              "the part inside the district and are hatched.")
    proj = LCC()
    coords = [c for f in shapes["district"]["features"] for poly in rings(f["geometry"]) for c in poly[0]]
    proj.fit(coords, 40, 120, W - 40, H - 120)
    change = {c["county_fips"]: c.get("pop_change_pct") for c in summary.get("counties", [])}
    whole = {c["county_fips"]: c["whole"] for c in summary.get("counties", [])}
    vals = [v for v in change.values() if v is not None]
    lim = max(abs(min(vals, default=0)), abs(max(vals, default=0)), 1)
    lim = nice_max(lim)

    def color(v):
        if v is None:
            return t["zero"]
        c = t["grow"] if v >= 0 else t["shrink"]
        return c, min(abs(v) / lim, 1) * 0.85 + 0.15

    svg.add(f'<defs><pattern id="hatch-{theme}" width="7" height="7" patternUnits="userSpaceOnUse" '
            f'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="7" stroke="{t["ink"]}" '
            f'stroke-opacity="0.35" stroke-width="1.6"/></pattern></defs>')
    for f in shapes.get("counties", {}).get("features", []):
        svg.add(f'<path d="{path(f["geometry"], proj)}" fill="{t["land"]}" stroke="{t["grid"]}" stroke-width="0.8"/>')
    labels = []
    for i, f in enumerate(shapes["parts"]["features"]):
        cf = f["properties"]["county_fips"]
        col = color(change.get(cf))
        fill, op = (col, 1.0) if isinstance(col, str) else col
        dpath = path(f["geometry"], proj)
        svg.add(f'<path d="{dpath}" fill="{fill}" fill-opacity="{op:.2f}" stroke="{t["edge"]}" stroke-width="1.2" '
                f'class="fade" style="animation-delay:{0.04 * i:.2f}s"/>')
        if not whole.get(cf, True):
            svg.add(f'<path d="{dpath}" fill="url(#hatch-{theme})" stroke="none"/>')
        c = centroid(f["geometry"], proj)
        if c:
            labels.append((c, (f["properties"]["name"] or "").replace(" County", "")))
    for f in shapes["district"]["features"]:
        svg.add(f'<path d="{path(f["geometry"], proj)}" fill="none" stroke="{t["ink"]}" stroke-width="2.2" '
                f'stroke-linejoin="round" class="draw"/>')
    for (x, y), name in labels:
        svg.text(x, y + 4, name, cls="small", anchor="middle", extra=f'style="paint-order:stroke;stroke:{t["edge"]};stroke-width:3px"')
    svg.text(24, 44, "Who lives where, and how it is changing", cls="title")
    year = next((c.get("pop_latest_year") for c in summary.get("counties", []) if c.get("pop_latest_year")), "")
    svg.text(24, 70, f"Population change by county, April 2020 to July {year}. Hatched counties are split; only the part in the district is drawn.", cls="sub muted")
    # legend
    lx, ly = W - 320, H - 92
    steps = 8
    for i in range(steps):
        v = -lim + 2 * lim * (i + 0.5) / steps
        col = color(v)
        svg.rect(lx + i * 34, ly, 34, 12, col[0], opacity=col[1])
    svg.text(lx, ly + 30, f"−{lim:g}%", cls="small muted")
    svg.text(lx + steps * 17, ly + 30, "0", cls="small muted", anchor="middle")
    svg.text(lx + steps * 34, ly + 30, f"+{lim:g}%", cls="small muted", anchor="end")
    svg.add(f'<rect x="{lx - 120}" y="{ly}" width="22" height="12" fill="url(#hatch-{theme})" stroke="{t["faint"]}"/>')
    svg.text(lx - 92, ly + 10, "Split county", cls="small muted")
    svg.footer(f"Sources: U.S. Census Bureau cartographic boundaries (119th Congress) and Population Estimates, Vintage {year}.")
    return svg


# ---------------------------------------------------------------- comparisons

COMPARE_ROWS = [
    ("median_age", "Median age", "years"),
    ("age_65_plus_pct", "Age 65 and older", "pct"),
    ("veterans_pct", "Veterans (adults)", "pct"),
    ("seasonal_homes_pct", "Homes held for seasonal use", "pct"),
    ("bachelors_plus_pct", "Bachelor's degree or more (25+)", "pct"),
    ("broadband_pct", "Households with broadband", "pct"),
    ("median_household_income", "Median household income", "usd"),
    ("median_home_value", "Median home value", "usd"),
    ("poverty_pct", "Below the poverty line", "pct"),
    ("uninsured_pct", "Without health insurance", "pct"),
]


def fmt_val(v, unit):
    if v is None:
        return "n/a"
    if unit == "usd":
        return f"${v / 1000:,.0f}k"
    if unit == "pct":
        return f"{v:.1f}%"
    return f"{v:.1f}"


def chart_compare(d: District, theme: str, acs: dict) -> SVG:
    t = THEMES[theme]
    rows = [r for r in COMPARE_ROWS if acs["district"]["metrics"].get(r[0]) is not None]
    W, top, rh = 980, 132, 56
    H = top + rh * len(rows) + 64
    y1 = acs["vintage"]["acs1"]
    svg = SVG(W, H, theme, "How the 7th compares with Wisconsin and the United States",
              f"Dot plot of {len(rows)} measures from the {y1} American Community Survey.")
    svg.text(24, 44, "How the 7th compares", cls="title")
    svg.text(24, 70, f"Each row has its own scale. American Community Survey {y1} 1-year estimates.", cls="sub muted")
    leg = [("District", t["accent"]), ("Wisconsin", t["state"]), ("United States", t["us"])]
    x = 24
    for name, col in leg:
        svg.circle(x + 6, 98, 6, col)
        svg.text(x + 18, 102, name, cls="label muted")
        x += 40 + 8 * len(name)
    x0, x1 = 330, W - 170
    for i, (key, label, unit) in enumerate(rows):
        y = top + i * rh + rh / 2
        vals = {g: (acs.get(g) or {}).get("metrics", {}).get(key) for g in ("district", "state", "us")}
        mx = nice_max(max(v for v in vals.values() if v is not None) * 1.08)
        svg.text(24, y + 5, label, cls="label")
        svg.line(x0, y, x1, y, t["grid"], 2)
        for g, col in (("us", t["us"]), ("state", t["state"]), ("district", t["accent"])):
            v = vals[g]
            if v is None:
                continue
            svg.circle(x0 + (x1 - x0) * v / mx, y, 8 if g == "district" else 6.5, col, cls="fade", delay=0.06 * i,
                       stroke=t["edge"] if g == "district" else None)
        svg.text(x1 + 16, y + 1, fmt_val(vals["district"], unit), cls="value", fill=t["accent"])
        svg.text(x1 + 16, y + 17, f"WI {fmt_val(vals['state'], unit)} · US {fmt_val(vals['us'], unit)}", cls="small muted")
    svg.footer(f"Source: U.S. Census Bureau, American Community Survey {y1} 1-year estimates (detailed tables B01001-B28002).")
    return svg


# ---------------------------------------------------------------- population change bars

def chart_population(d: District, theme: str, summary: dict) -> SVG | None:
    t = THEMES[theme]
    rows = [c for c in summary.get("counties", []) if c.get("pop_change_pct") is not None]
    if not rows:
        return None
    rows.sort(key=lambda c: -c["pop_change_pct"])
    W, top, rh = 960, 110, 24
    H = top + rh * len(rows) + 60
    year = rows[0].get("pop_latest_year")
    svg = SVG(W, H, theme, "Population change by county since 2020",
              "Bar chart of each county's percentage change in population from April 2020 to the latest estimate.")
    svg.text(24, 44, "Growing, holding, or shrinking", cls="title")
    svg.text(24, 70, f"Change in county population, April 1, 2020 to July 1, {year}. Whole-county figures.", cls="sub muted")
    lim = nice_max(max(abs(c["pop_change_pct"]) for c in rows))
    mid, half = 560, 300
    svg.line(mid, top - 8, mid, top + rh * len(rows), t["grid"], 1.5)
    for i, c in enumerate(rows):
        y = top + i * rh
        v = c["pop_change_pct"]
        w = half * abs(v) / lim
        col = t["grow"] if v >= 0 else t["shrink"]
        x = mid if v >= 0 else mid - w
        svg.add(f'<g class="grow" style="animation-delay:{0.025 * i:.2f}s;transform-origin:{"left" if v >= 0 else "right"} center">')
        svg.rect(x, y + 4, w, rh - 8, col, rx=3)
        svg.add("</g>")
        name = c["short_name"] + ("" if c["whole"] else " (split)")
        svg.text(24, y + rh / 2 + 4, name, cls="label")
        svg.text(x + w + 8 if v >= 0 else x - 8, y + rh / 2 + 4, f"{v:+.1f}%", cls="value",
                 anchor="start" if v >= 0 else "end")
    svg.footer(f"Source: U.S. Census Bureau, Population Estimates Program, Vintage {year}.")
    return svg


# ---------------------------------------------------------------- unemployment

def chart_unemployment(d: District, theme: str, laus: dict, summary: dict) -> SVG | None:
    t = THEMES[theme]
    fips = [c["county_fips"] for c in summary.get("counties", [])]
    series = laus.get("series", {})
    dates = sorted({p["date"] for k in fips for p in series.get(k, [])})
    if not dates:
        return None
    W, H = 960, 460
    x0, x1, y0, y1 = 70, W - 160, 110, H - 70
    svg = SVG(W, H, theme, "Monthly unemployment rate",
              "Line chart of Wisconsin and U.S. unemployment with the range across the district's counties.")
    svg.text(24, 44, "Jobs, month by month", cls="title")
    svg.text(24, 70, "Unemployment rate, not seasonally adjusted. The band spans the lowest and highest county each month.", cls="sub muted")
    by_date = {dt: [p["rate"] for k in fips for p in series.get(k, []) if p["date"] == dt] for dt in dates}
    ymax = nice_max(max(max(v) for v in by_date.values() if v))
    X = lambda i: x0 + (x1 - x0) * i / max(len(dates) - 1, 1)
    Y = lambda v: y1 - (y1 - y0) * v / ymax
    for k in range(0, int(ymax) + 1, max(1, int(ymax // 5))):
        svg.line(x0, Y(k), x1, Y(k), t["grid"])
        svg.text(x0 - 10, Y(k) + 4, f"{k}%", cls="small muted", anchor="end")
    top = [(X(i), Y(max(by_date[dt]))) for i, dt in enumerate(dates) if by_date[dt]]
    bot = [(X(i), Y(min(by_date[dt]))) for i, dt in enumerate(dates) if by_date[dt]]
    poly = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in top) + "L" + "L".join(f"{x:.1f},{y:.1f}" for x, y in reversed(bot)) + "Z"
    svg.add(f'<path d="{poly}" fill="{t["band"]}" fill-opacity="0.16" class="fade"/>')
    ends = []
    for key, col, name in (("us", t["us"], "United States"), ("state", t["state"], "Wisconsin")):
        pts = {p["date"]: p["rate"] for p in series.get(key, [])}
        coords = [(X(i), Y(pts[dt])) for i, dt in enumerate(dates) if dt in pts]
        if coords:
            svg.add(f'<path d="M{"L".join(f"{x:.1f},{y:.1f}" for x, y in coords)}" fill="none" stroke="{col}" '
                    f'stroke-width="2.4" stroke-linejoin="round" class="draw"/>')
            ends.append([coords[-1][1], name, col])
    ends.append([(top[-1][1] + bot[-1][1]) / 2, "District counties", t["accent"]])
    for y_, name, col in spread(ends, 17):
        svg.text(x1 + 12, y_ + 4, name, cls="label", fill=col)
    for i, dt in enumerate(dates):
        if dt.endswith("-01") and int(dt[:4]) % 2 == 0:
            svg.text(X(i), y1 + 22, dt[:4], cls="small muted", anchor="middle")
    svg.footer(f"Source: U.S. Bureau of Labor Statistics, Local Area Unemployment Statistics, through {summary['unemployment']['month_label']} (latest month preliminary).")
    return svg


# ---------------------------------------------------------------- industries

def chart_industry(d: District, theme: str, acs: dict) -> SVG:
    t = THEMES[theme]
    dist = [r for r in acs["district"]["industry"] if r["pct"] is not None][:9]
    state = {r["id"]: r["pct"] for r in acs["state"]["industry"]}
    W, top, rh = 960, 120, 46
    H = top + rh * len(dist) + 60
    y1 = acs["vintage"]["acs1"]
    svg = SVG(W, H, theme, "What people do for work", "Paired bar chart of the share of workers in each industry, district and Wisconsin.")
    svg.text(24, 44, "What people do for work", cls="title")
    svg.text(24, 70, f"Share of employed residents by industry. American Community Survey {y1} 1-year estimates.", cls="sub muted")
    svg.rect(24, 88, 12, 12, t["accent"], rx=2)
    svg.text(42, 99, "District", cls="small muted")
    svg.rect(110, 88, 12, 12, t["state"], rx=2, opacity=0.55)
    svg.text(128, 99, "Wisconsin", cls="small muted")
    mx = nice_max(max(max(r["pct"], state.get(r["id"]) or 0) for r in dist))
    x0, x1 = 300, W - 90
    for i, r in enumerate(dist):
        y = top + i * rh
        svg.text(24, y + 20, r.get("short") or r["label"], cls="label")
        w = (x1 - x0) * r["pct"] / mx
        svg.add(f'<g class="grow" style="animation-delay:{0.05 * i:.2f}s">')
        svg.rect(x0, y + 4, w, 16, t["accent"], rx=3)
        sw = (x1 - x0) * (state.get(r["id"]) or 0) / mx
        svg.rect(x0, y + 24, sw, 9, t["state"], rx=2, opacity=0.55)
        svg.add("</g>")
        svg.text(x0 + w + 8, y + 17, f"{r['pct']:.1f}%", cls="value")
    svg.footer(f"Source: U.S. Census Bureau, American Community Survey {y1} 1-year estimates, table C24050.")
    return svg


# ---------------------------------------------------------------- federal dollars

def chart_federal(d: District, theme: str, usa: dict) -> SVG | None:
    t = THEMES[theme]
    years = [y for y in usa.get("years", []) if y.get("total") is not None]
    if not years:
        return None
    W, H = 960, 420
    x0, x1, y0, y1 = 80, W - 40, 110, H - 70
    svg = SVG(W, H, theme, "Federal award obligations by fiscal year",
              "Column chart of federal contracts, grants, loans, and payments obligated in the district each fiscal year.")
    svg.text(24, 44, "Federal dollars at work in the district", cls="title")
    svg.text(24, 70, "Award obligations by place of performance, current district lines. Agencies revise these figures over time.", cls="sub muted")
    mx = nice_max(max(y["total"] for y in years))
    bw = (x1 - x0) / len(years)
    for k in range(5):
        v = mx * k / 4
        yy = y1 - (y1 - y0) * k / 4
        svg.line(x0, yy, x1, yy, t["grid"])
        svg.text(x0 - 10, yy + 4, money_short(v), cls="small muted", anchor="end")
    for i, y in enumerate(years):
        h = (y1 - y0) * max(y["total"], 0) / mx
        x = x0 + i * bw + bw * 0.18
        last = y["fy"] == usa["last_complete_fy"]
        svg.add(f'<g class="rise" style="animation-delay:{0.06 * i:.2f}s">')
        svg.rect(x, y1 - h, bw * 0.64, h, t["accent"] if last else t["accent2"], rx=4, opacity=1 if last else 0.75)
        svg.add("</g>")
        svg.text(x + bw * 0.32, y1 + 22, f"FY{str(y['fy'])[2:]}", cls="small muted", anchor="middle")
        svg.text(x + bw * 0.32, y1 - h - 8, money_short(y["total"]), cls="small", anchor="middle")
    svg.footer(f"Source: USAspending.gov (U.S. Department of the Treasury), retrieved {usa.get('as_of')}.")
    return svg


# ---------------------------------------------------------------- elections

def party_color(t, party):
    p = (party or "").lower()
    if p.startswith("republican"):
        return t["rep"]
    if p.startswith("democrat"):
        return t["dem"]
    return t["oth"]


def chart_elections(d: District, theme: str, ele: dict) -> SVG | None:
    t = THEMES[theme]
    res = ele.get("results", [])
    if not res:
        return None
    W, H = 960, 440
    x0, x1, y0, y1 = 70, W - 40, 120, H - 80
    svg = SVG(W, H, theme, "House general election results for the seat",
              "Stacked columns of each candidate's share of the vote in every general election for the seat.")
    svg.text(24, 44, "Every general election for the seat", cls="title")
    svg.text(24, 70, f"Share of the vote, {res[0]['year']} to {res[-1]['year']}. Dashed lines mark new district boundaries.", cls="sub muted")
    leg = [("Democratic", t["dem"]), ("Republican", t["rep"]), ("Other", t["oth"])]
    x = 24
    for name, col in leg:
        svg.rect(x, 88, 12, 12, col, rx=2)
        svg.text(x + 18, 99, name, cls="small muted")
        x += 30 + 7 * len(name)
    bw = (x1 - x0) / len(res)
    for k in (0, 25, 50, 75, 100):
        yy = y1 - (y1 - y0) * k / 100
        svg.line(x0, yy, x1, yy, t["grid"], 1.4 if k == 50 else 1, dash=None if k in (0, 100) else "3 4")
        svg.text(x0 - 10, yy + 4, f"{k}%", cls="small muted", anchor="end")
    order = lambda c: (0 if (c["party"] or "").lower().startswith("democrat") else 1 if (c["party"] or "").lower().startswith("republican") else 2)
    for i, r in enumerate(res):
        x = x0 + i * bw + bw * 0.12
        acc = y1
        svg.add(f'<g class="rise" style="animation-delay:{0.03 * i:.2f}s">')
        for c in sorted(r["candidates"], key=order):
            h = (y1 - y0) * (c["pct"] or 0) / 100
            acc -= h
            svg.rect(x, acc, bw * 0.76, h, party_color(t, c["party"]))
        svg.add("</g>")
        if r.get("new_lines"):
            svg.line(x - bw * 0.12, y0 - 6, x - bw * 0.12, y1, t["ink"], 1, dash="4 4", opacity=0.6)
        if i % 2 == 0 or i == len(res) - 1:
            svg.text(x + bw * 0.38, y1 + 20, str(r["year"]), cls="small muted", anchor="middle")
    svg.footer("Source: MIT Election Data and Science Lab, U.S. House 1976-2024 (Harvard Dataverse), from official state results.")
    return svg


# ---------------------------------------------------------------- seat timeline

def chart_seat(d: District, theme: str, leg: dict) -> SVG | None:
    t = THEMES[theme]
    members = [m for m in leg.get("members", []) if m["end"] >= "1963-01-01"]
    if not members:
        return None
    W, H = 960, 290
    x0, x1 = 40, W - 40
    start = datetime.fromisoformat(members[0]["start"]).year
    end = max(datetime.now().year + 1, datetime.fromisoformat(members[-1]["end"]).year)
    X = lambda s: x0 + (x1 - x0) * (datetime.fromisoformat(s).year + (datetime.fromisoformat(s).timetuple().tm_yday / 366) - start) / (end - start)
    svg = SVG(W, H, theme, "Who has held the seat", "Timeline of members who have represented the district.")
    svg.text(24, 44, "Who has held the seat", cls="title")
    svg.text(24, 70, f"Members since {start}. The seat follows the district, whose lines were redrawn after each census.", cls="sub muted")
    row_end = [-1e9, -1e9]
    for i, m in enumerate(members):
        a, b = X(m["start"]), X(m["end"])
        col = party_color(t, m["parties"][-1])
        svg.add(f'<g class="grow" style="animation-delay:{0.15 * i:.2f}s">')
        svg.rect(a, 110, max(b - a - 2, 2), 42, col, rx=6)
        svg.add("</g>")
        name = m["name"]
        sub = f"{m['start'][:4]}-{m['end'][:4]} · {m['parties'][-1]}"
        room = max(len(name) * 7.6, len(sub) * 6.4)
        if a + room > W - 24:
            tx, anchor, left, right = b - 2, "end", b - 2 - room, b - 2
        else:
            tx, anchor, left, right = a + 2, "start", a + 2, a + 2 + room
        row = 0 if left > row_end[0] + 12 else 1
        row_end[row] = right
        dy = 46 * row
        if row:
            svg.line(tx if anchor == "start" else tx, 154, tx, 160 + dy, t["faint"], 1)
        svg.text(tx, 176 + dy, name, cls="label", anchor=anchor)
        svg.text(tx, 194 + dy, sub, cls="small muted", anchor=anchor)
    for yr in range(start - start % 10 + 10, end, 10):
        xx = x0 + (x1 - x0) * (yr - start) / (end - start)
        svg.text(xx, 100, str(yr), cls="small faint", anchor="middle")
    svg.footer("Sources: congress-legislators (The @unitedstates project), cross-checked with the Clerk of the U.S. House.")
    return svg


# ---------------------------------------------------------------- age

def chart_age(d: District, theme: str, acs: dict) -> SVG:
    t = THEMES[theme]
    bands = acs["district"]["age_bands"]
    us = {b["id"]: b["pct"] for b in acs["us"]["age_bands"]}
    W, top, rh = 960, 120, 44
    H = top + rh * len(bands) + 60
    y1 = acs["vintage"]["acs1"]
    svg = SVG(W, H, theme, "Age of residents", "Bar chart comparing the district's age groups with the United States.")
    older = (acs["district"]["metrics"].get("median_age") or 0) > (acs["us"]["metrics"].get("median_age") or 99)
    svg.text(24, 44, "An older-than-average district" if older else "Age of residents", cls="title")
    svg.text(24, 70, f"Share of residents in each age group. American Community Survey {y1} 1-year estimates.", cls="sub muted")
    svg.rect(24, 88, 12, 12, t["accent"], rx=2)
    svg.text(42, 99, "District", cls="small muted")
    svg.rect(110, 88, 12, 12, t["us"], rx=2)
    svg.text(128, 99, "United States", cls="small muted")
    mx = nice_max(max(max(b["pct"], us[b["id"]]) for b in bands))
    x0, x1 = 200, W - 90
    for i, b in enumerate(bands):
        y = top + i * rh
        svg.text(24, y + 20, b["label"], cls="label")
        svg.add(f'<g class="grow" style="animation-delay:{0.05 * i:.2f}s">')
        svg.rect(x0, y + 4, (x1 - x0) * b["pct"] / mx, 16, t["accent"], rx=3)
        svg.rect(x0, y + 24, (x1 - x0) * us[b["id"]] / mx, 9, t["us"], rx=2)
        svg.add("</g>")
        svg.text(x0 + (x1 - x0) * b["pct"] / mx + 8, y + 17, f"{b['pct']:.1f}%", cls="value")
    svg.footer(f"Source: U.S. Census Bureau, American Community Survey {y1} 1-year estimates, table B01001.")
    return svg


# ---------------------------------------------------------------- driver

def render_all(d: District) -> list[str]:
    summary = load(d, "summary") or {}
    acs, laus, usa = load(d, "acs"), load(d, "laus"), load(d, "usaspending")
    ele, leg, geo = load(d, "elections"), load(d, "legislators"), load(d, "geography")
    made = []
    for theme in THEMES:
        builders = {
            "map": lambda: chart_map(d, theme, geo, summary) if geo else None,
            "compare": lambda: chart_compare(d, theme, acs) if acs and acs.get("district") else None,
            "age": lambda: chart_age(d, theme, acs) if acs and acs.get("district") and acs.get("us") else None,
            "population": lambda: chart_population(d, theme, summary),
            "unemployment": lambda: chart_unemployment(d, theme, laus, summary) if laus else None,
            "industry": lambda: chart_industry(d, theme, acs) if acs and acs.get("district") and acs.get("state") else None,
            "federal": lambda: chart_federal(d, theme, usa) if usa else None,
            "elections": lambda: chart_elections(d, theme, ele) if ele else None,
            "seat": lambda: chart_seat(d, theme, leg) if leg else None,
        }
        for name, build in builders.items():
            svg = build()
            if svg:
                write(name, theme, svg)
                made.append(f"{name}-{theme}")
    print(f"  charts: {len(made)} written to {OUT}")
    return made
