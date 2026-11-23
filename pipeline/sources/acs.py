"""American Community Survey: people, homes, work, and income.

Uses detailed tables (B and C tables) because their variable IDs are stable
across years. Before any value is used, the variable's official label is
checked against what this module expects it to mean. A mismatch drops the
metric and fails an integrity check instead of publishing a wrong number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .. import census
from ..config import District
from ..http import Fetcher, FetchError
from ..provenance import Source

AGES = [
    "under 5 years", "5 to 9 years", "10 to 14 years", "15 to 17 years",
    "18 and 19 years", "20 years", "21 years", "22 to 24 years",
    "25 to 29 years", "30 to 34 years", "35 to 39 years", "40 to 44 years",
    "45 to 49 years", "50 to 54 years", "55 to 59 years", "60 and 61 years",
    "62 to 64 years", "65 and 66 years", "67 to 69 years", "70 to 74 years",
    "75 to 79 years", "80 to 84 years", "85 years and over",
]


def _b01001(i: int) -> str:
    return f"B01001_{i:03d}E"


# Expected label fragment for every variable used. "=" means exact match.
EXPECT: dict[str, str] = {
    "B01003_001E": "=estimate!!total",
    "B01002_001E": "median age",
    "B01001_001E": "=estimate!!total",
    "B19013_001E": "median household income",
    "B19301_001E": "per capita income",
    "B17001_001E": "=estimate!!total",
    "B17001_002E": "income in the past 12 months below poverty level",
    "B15003_001E": "=estimate!!total",
    "B21001_001E": "=estimate!!total",
    "B21001_002E": "=estimate!!total!!veteran",
    "B25077_001E": "median value",
    "B25064_001E": "median gross rent",
    "B25003_001E": "=estimate!!total",
    "B25003_002E": "=estimate!!total!!owner occupied",
    "B28002_001E": "=estimate!!total",
    "B28002_004E": "broadband of any type",
    "B28002_013E": "no internet access",
    "B27010_001E": "=estimate!!total",
    "B27010_017E": "under 19 years!!no health insurance coverage",
    "B27010_033E": "19 to 34 years!!no health insurance coverage",
    "B27010_050E": "35 to 64 years!!no health insurance coverage",
    "B27010_066E": "65 years and over!!no health insurance coverage",
    "B23025_001E": "=estimate!!total",
    "B23025_002E": "=estimate!!total!!in labor force",
    "B23025_003E": "=estimate!!total!!in labor force!!civilian labor force",
    "B23025_005E": "=estimate!!total!!in labor force!!civilian labor force!!unemployed",
    "B08303_001E": "=estimate!!total",
    "B08013_001E": "aggregate travel time to work",
    "B08301_001E": "=estimate!!total",
    "B08301_021E": "worked from home",
    "B03002_001E": "=estimate!!total",
    "B03002_003E": "not hispanic or latino!!white alone",
    "B03002_004E": "not hispanic or latino!!black or african american alone",
    "B03002_005E": "not hispanic or latino!!american indian and alaska native alone",
    "B03002_006E": "not hispanic or latino!!asian alone",
    "B03002_007E": "not hispanic or latino!!native hawaiian and other pacific islander alone",
    "B03002_008E": "not hispanic or latino!!some other race alone",
    "B03002_009E": "not hispanic or latino!!two or more races",
    "B03002_012E": "=estimate!!total!!hispanic or latino",
    "C24050_001E": "=estimate!!total",
    "C24050_002E": "=estimate!!total!!agriculture, forestry, fishing and hunting, and mining",
    "C24050_003E": "=estimate!!total!!construction",
    "C24050_004E": "=estimate!!total!!manufacturing",
    "C24050_005E": "=estimate!!total!!wholesale trade",
    "C24050_006E": "=estimate!!total!!retail trade",
    "C24050_007E": "=estimate!!total!!transportation and warehousing, and utilities",
    "C24050_008E": "=estimate!!total!!information",
    "C24050_009E": "=estimate!!total!!finance and insurance, and real estate, and rental and leasing",
    "C24050_010E": "=estimate!!total!!professional, scientific, and management, and administrative, and waste management services",
    "C24050_011E": "=estimate!!total!!educational services, and health care and social assistance",
    "C24050_012E": "=estimate!!total!!arts, entertainment, and recreation, and accommodation and food services",
    "C24050_013E": "=estimate!!total!!other services, except public administration",
    "C24050_014E": "=estimate!!total!!public administration",
    "B11001_001E": "=estimate!!total",
    "B25010_001E": "average household size",
    "B25001_001E": "=estimate!!total",
    "B25002_001E": "=estimate!!total",
    "B25002_003E": "=estimate!!total!!vacant",
    "B25004_006E": "for seasonal, recreational, or occasional use",
}
for _i, _age in enumerate(AGES):
    EXPECT[_b01001(3 + _i)] = f"=estimate!!total!!male!!{_age}"
    EXPECT[_b01001(27 + _i)] = f"=estimate!!total!!female!!{_age}"

# Labels that may legitimately use slightly different punctuation across years.
LOOSE = {
    "C24050_009E": ["finance and insurance", "real estate"],
    "C24050_010E": ["professional, scientific", "waste management services"],
    "C24050_012E": ["arts, entertainment", "accommodation and food services"],
}

MALE_UNDER18 = [_b01001(i) for i in range(3, 7)]
FEMALE_UNDER18 = [_b01001(i) for i in range(27, 31)]
MALE_65 = [_b01001(i) for i in range(20, 26)]
FEMALE_65 = [_b01001(i) for i in range(44, 50)]


@dataclass
class Metric:
    id: str
    label: str
    unit: str            # count | usd | pct | years | minutes | persons
    num: list[str]
    den: list[str] = field(default_factory=list)
    moe: str | None = None   # margin-of-error variable for single-value metrics
    universe: str = ""
    higher: str = "neutral"  # how to read the metric; always neutral wording on the site
    note: str = ""

    def compute(self, row: dict) -> float | None:
        try:
            n = sum(row[v] for v in self.num)
        except (KeyError, TypeError):
            return None
        if not self.den:
            return n
        try:
            d = sum(row[v] for v in self.den)
        except (KeyError, TypeError):
            return None
        if not d:
            return None
        return 100.0 * n / d


METRICS: list[Metric] = [
    Metric("population", "Population", "count", ["B01003_001E"], moe="B01003_001M", universe="All residents"),
    Metric("median_age", "Median age", "years", ["B01002_001E"], moe="B01002_001M", universe="All residents"),
    Metric("under_18_pct", "Under 18", "pct", MALE_UNDER18 + FEMALE_UNDER18, ["B01001_001E"], universe="All residents"),
    Metric("age_65_plus_pct", "Age 65 and older", "pct", MALE_65 + FEMALE_65, ["B01001_001E"], universe="All residents"),
    Metric("median_household_income", "Median household income", "usd", ["B19013_001E"], moe="B19013_001M",
           universe="Households", note="In inflation-adjusted dollars of the survey year"),
    Metric("per_capita_income", "Per capita income", "usd", ["B19301_001E"], moe="B19301_001M", universe="All residents"),
    Metric("poverty_pct", "Below the poverty line", "pct", ["B17001_002E"], ["B17001_001E"],
           universe="People whose poverty status is determined"),
    Metric("veterans_pct", "Veterans", "pct", ["B21001_002E"], ["B21001_001E"], universe="Civilian adults 18 and older"),
    Metric("median_home_value", "Median home value", "usd", ["B25077_001E"], moe="B25077_001M",
           universe="Owner-occupied homes"),
    Metric("median_gross_rent", "Median gross rent", "usd", ["B25064_001E"], moe="B25064_001M",
           universe="Renter-occupied homes paying cash rent"),
    Metric("owner_occupied_pct", "Homes lived in by their owners", "pct", ["B25003_002E"], ["B25003_001E"],
           universe="Occupied homes"),
    Metric("seasonal_homes_pct", "Seasonal or recreational homes", "pct", ["B25004_006E"], ["B25001_001E"],
           universe="All housing units", note="Vacant units held for seasonal, recreational, or occasional use"),
    Metric("broadband_pct", "Households with broadband", "pct", ["B28002_004E"], ["B28002_001E"], universe="Households"),
    Metric("no_internet_pct", "Households with no internet access", "pct", ["B28002_013E"], ["B28002_001E"],
           universe="Households"),
    Metric("uninsured_pct", "Without health insurance", "pct",
           ["B27010_017E", "B27010_033E", "B27010_050E", "B27010_066E"], ["B27010_001E"],
           universe="Civilian residents not in institutions"),
    Metric("labor_force_pct", "In the labor force", "pct", ["B23025_002E"], ["B23025_001E"], universe="Residents 16 and older"),
    Metric("unemployment_acs_pct", "Unemployed (survey)", "pct", ["B23025_005E"], ["B23025_003E"],
           universe="Civilian labor force", note="Survey-based; official monthly rates come from BLS"),
    Metric("work_from_home_pct", "Work from home", "pct", ["B08301_021E"], ["B08301_001E"], universe="Workers 16 and older"),
    Metric("households", "Households", "count", ["B11001_001E"], moe="B11001_001M", universe="Households"),
    Metric("avg_household_size", "Average household size", "persons", ["B25010_001E"], universe="Occupied homes"),
    Metric("housing_units", "Housing units", "count", ["B25001_001E"], moe="B25001_001M", universe="All housing units"),
]

# Education rows are found by their official labels each year. The Census Bureau
# renumbered table B15003 in the 2025 release (B15003_022E moved from "Bachelor's
# degree" to "Professional school degree"), so variable numbers cannot be trusted.
EDU_GROUP = "B15003"
EDU_HS = ("high school diploma", "ged", "some college", "associate", "bachelor", "master", "professional school", "doctorate")
EDU_BA = ("bachelor", "master", "professional school", "doctorate")
EDU_METRICS = [
    {"id": "hs_plus_pct", "label": "High school diploma or more", "unit": "pct", "universe": "Adults 25 and older", "note": ""},
    {"id": "bachelors_plus_pct", "label": "Bachelor's degree or more", "unit": "pct", "universe": "Adults 25 and older", "note": ""},
]


def edu_vars(labels: dict[str, str]) -> dict | None:
    """Pick the B15003 rows directly under Total whose names match each level."""
    rows = {}
    for var, lab in labels.items():
        if not (var.startswith(EDU_GROUP + "_") and var.endswith("E")):
            continue
        parts = census.normalize_label(lab).split("!!")
        if len(parts) == 3 and parts[:2] == ["estimate", "total"]:
            rows[var] = parts[2]
    total = f"{EDU_GROUP}_001E" if census.normalize_label(labels.get(f"{EDU_GROUP}_001E", "")) == "estimate!!total" else None
    hs = sorted(v for v, name in rows.items() if any(k in name for k in EDU_HS) and "no diploma" not in name)
    ba = sorted(v for v, name in rows.items() if any(k in name for k in EDU_BA))
    if not total or len(ba) < 3 or len(hs) < len(ba) + 2:
        return None
    return {"total": total, "hs": hs, "ba": ba, "rows": {v: rows[v] for v in hs}}


# Mean commute is a ratio of an aggregate to a count, not a percentage.
COMMUTE = ("B08013_001E", "B08303_001E")

RACE = [
    ("white", "White", "B03002_003E"),
    ("aian", "American Indian and Alaska Native", "B03002_005E"),
    ("hispanic", "Hispanic or Latino (any race)", "B03002_012E"),
    ("two_plus", "Two or more races", "B03002_009E"),
    ("asian", "Asian", "B03002_006E"),
    ("black", "Black or African American", "B03002_004E"),
    ("other", "Some other race", "B03002_008E"),
    ("nhpi", "Native Hawaiian and Pacific Islander", "B03002_007E"),
]

INDUSTRY = [
    ("health_ed", "Health care, social assistance, and education", "C24050_011E"),
    ("manufacturing", "Manufacturing", "C24050_004E"),
    ("retail", "Retail", "C24050_006E"),
    ("arts_food", "Arts, recreation, lodging, and food service", "C24050_012E"),
    ("construction", "Construction", "C24050_003E"),
    ("professional", "Professional, scientific, and administrative services", "C24050_010E"),
    ("transport", "Transportation, warehousing, and utilities", "C24050_007E"),
    ("ag_mining", "Agriculture, forestry, fishing, and mining", "C24050_002E"),
    ("finance", "Finance, insurance, and real estate", "C24050_009E"),
    ("public_admin", "Public administration", "C24050_014E"),
    ("other_services", "Other services", "C24050_013E"),
    ("wholesale", "Wholesale trade", "C24050_005E"),
    ("information", "Information", "C24050_008E"),
]

INDUSTRY_SHORT = {"health_ed": "Health care and education", "manufacturing": "Manufacturing", "retail": "Retail", "arts_food": "Recreation, lodging, and food", "construction": "Construction", "professional": "Professional services", "transport": "Transportation and utilities", "ag_mining": "Farming, forestry, and mining", "finance": "Finance and real estate", "public_admin": "Public administration", "other_services": "Other services", "wholesale": "Wholesale trade", "information": "Information"}

AGE_BANDS = [
    ("0-17", "Under 18", list(range(3, 7))),
    ("18-24", "18 to 24", list(range(7, 11))),
    ("25-44", "25 to 44", list(range(11, 15))),
    ("45-64", "45 to 64", list(range(15, 20))),
    ("65-74", "65 to 74", list(range(20, 23))),
    ("75+", "75 and older", list(range(23, 26))),
]


def all_variables() -> list[str]:
    vs: list[str] = []
    for m in METRICS:
        vs += m.num + m.den
        if m.moe:
            vs.append(m.moe)
    vs += list(COMMUTE)
    vs += ["B03002_001E"] + [v for _, _, v in RACE]
    vs += ["C24050_001E"] + [v for _, _, v in INDUSTRY]
    vs += ["B01001_001E"] + [_b01001(i) for i in range(3, 26)] + [_b01001(i) for i in range(27, 50)]
    vs += ["B25002_001E", "B25002_003E"]
    return list(dict.fromkeys(vs))


def verify_labels(fetcher: Fetcher, path: str) -> tuple[list[dict], set[str], dict[str, str]]:
    """Check every variable's official label. Returns (checks, bad_vars, labels)."""
    groups = sorted({v.split("_")[0] for v in EXPECT} | {EDU_GROUP})
    labels: dict[str, str] = {}
    for g in groups:
        labels.update(census.group_labels(fetcher, path, g))
    checks, bad = [], set()
    for var, expected in sorted(EXPECT.items()):
        actual = labels.get(var, "")
        if var in LOOSE:
            ok = bool(actual) and all(f in census.normalize_label(actual) for f in LOOSE[var])
        else:
            ok = bool(actual) and census.label_matches(actual, expected)
        if not ok:
            bad.add(var)
        checks.append({"variable": var, "expected": expected, "official_label": actual, "ok": ok})
    return checks, bad, labels


def summarize(row: dict, bad: set[str], edu: dict | None = None) -> dict:
    """Compute every metric and breakdown for one geography row."""
    out: dict = {"metrics": {}, "moe": {}}
    tot = row.get(edu["total"]) if edu else None
    for key, cols in (("hs_plus_pct", "hs"), ("bachelors_plus_pct", "ba")):
        vals = [row.get(v) for v in edu[cols]] if edu else []
        out["metrics"][key] = (100 * sum(vals) / tot) if edu and tot and all(v is not None for v in vals) else None
    for m in METRICS:
        if bad.intersection(m.num + m.den):
            out["metrics"][m.id] = None
            continue
        out["metrics"][m.id] = m.compute(row)
        if m.moe and row.get(m.moe) is not None:
            out["moe"][m.id] = row[m.moe]
    agg, n = row.get(COMMUTE[0]), row.get(COMMUTE[1])
    out["metrics"]["mean_commute_min"] = (agg / n) if agg and n and not bad.intersection(COMMUTE) else None
    total = row.get("B03002_001E")
    out["race"] = [
        {"id": k, "label": lab, "pct": (100 * row[v] / total) if total and row.get(v) is not None and v not in bad else None}
        for k, lab, v in RACE
    ]
    emp = row.get("C24050_001E")
    out["industry"] = [
        {"id": k, "label": lab, "short": INDUSTRY_SHORT.get(k, lab), "workers": row.get(v),
         "pct": (100 * row[v] / emp) if emp and row.get(v) is not None and v not in bad else None}
        for k, lab, v in INDUSTRY
    ]
    pop = row.get("B01001_001E")
    bands = []
    for k, lab, idx in AGE_BANDS:
        male = sum(row.get(_b01001(i)) or 0 for i in idx)
        female = sum(row.get(_b01001(i + 24)) or 0 for i in idx)
        bands.append({"id": k, "label": lab, "male": male, "female": female,
                      "pct": 100 * (male + female) / pop if pop else None})
    out["age_bands"] = bands
    return out


def fetch(fetcher: Fetcher, d: District) -> tuple[dict, list[Source], list[dict]]:
    """Return (payload, sources, checks)."""
    year_now = datetime.now(timezone.utc).year
    cd_for = f"congressional district:{d.district}"
    st_in = f"state:{d.state_fips}"

    def probe1(y: int) -> bool:
        return bool(census.query(fetcher, f"{y}/acs/acs1", ["B01003_001E"], cd_for, st_in))

    def probe5(y: int) -> bool:
        return bool(census.query(fetcher, f"{y}/acs/acs5", ["B01003_001E"], "county:*", st_in))

    y1 = census.first_available(fetcher, [year_now - 1, year_now - 2, year_now - 3], probe1)
    y5 = census.first_available(fetcher, [year_now - 1, year_now - 2, year_now - 3], probe5)

    prepared: dict[str, dict] = {}

    def prepare(path: str) -> dict:
        """Verify labels for one dataset and decide which variables are safe to request."""
        if path not in prepared:
            checks_, bad_, labels_ = verify_labels(fetcher, path)
            edu = edu_vars(labels_)
            safe = []
            for v in all_variables():
                base = v[:-1] + "E"          # a margin of error follows its estimate
                if base not in bad_ and base in labels_:
                    safe.append(v)
            if edu:
                safe += [edu["total"], *edu["hs"]]
            prepared[path] = {"checks": checks_, "bad": bad_, "edu": edu, "vars": list(dict.fromkeys(safe))}
        return prepared[path]

    p1, p5 = prepare(f"{y1}/acs/acs1"), prepare(f"{y5}/acs/acs5")

    def rows_for(path: str, for_: str, in_: str | None = None) -> list[dict]:
        return census.query(fetcher, path, prepare(path)["vars"], for_, in_)

    def summ(path: str, row: dict) -> dict:
        pp = prepare(path)
        return summarize(row, pp["bad"], pp["edu"])

    a1, a5 = f"{y1}/acs/acs1", f"{y5}/acs/acs5"
    district_rows = rows_for(a1, cd_for, st_in)
    state_rows = rows_for(a1, st_in)
    us_rows = rows_for(a1, "us:1")
    county_rows = rows_for(a5, "county:*", st_in)
    district5 = rows_for(a5, cd_for, st_in)
    state5 = rows_for(a5, st_in)

    trend: dict[str, dict] = {}
    for y in range(d.comparable_acs1_years_from, y1 + 1):
        path = f"{y}/acs/acs1"
        try:
            rows = district_rows if y == y1 else rows_for(path, cd_for, st_in)
        except FetchError:
            continue
        if rows:
            s_ = summ(path, rows[0])
            trend[str(y)] = {k: s_["metrics"].get(k) for k in (
                "population", "median_household_income", "poverty_pct", "median_age",
                "bachelors_plus_pct", "broadband_pct", "median_home_value", "age_65_plus_pct",
                "uninsured_pct", "work_from_home_pct")}

    bad = p1["bad"] | p5["bad"]
    label_checks = p1["checks"] + p5["checks"]
    edu_ok = bool(p1["edu"] and p5["edu"])
    payload = {
        "vintage": {"acs1": y1, "acs5": y5},
        "metrics": [
            {"id": m.id, "label": m.label, "unit": m.unit, "universe": m.universe, "note": m.note}
            for m in METRICS
        ] + EDU_METRICS + [{"id": "mean_commute_min", "label": "Average commute", "unit": "minutes",
              "universe": "Workers 16 and older who do not work at home", "note": ""}],
        "district": summ(a1, district_rows[0]) if district_rows else None,
        "state": summ(a1, state_rows[0]) if state_rows else None,
        "us": summ(a1, us_rows[0]) if us_rows else None,
        "district_5yr": summ(a5, district5[0]) if district5 else None,
        "state_5yr": summ(a5, state5[0]) if state5 else None,
        "counties": {
            r["county"]: {"name": r["NAME"].split(",")[0], **summ(a5, r)} for r in county_rows
        },
        "district_trend": trend,
        "label_checks": label_checks,
        "education_rows": {"acs1": p1["edu"], "acs5": p5["edu"]},
        "dropped_variables": sorted(bad),
    }
    sources = [
        Source(
            id="acs1",
            publisher="U.S. Census Bureau",
            title=f"American Community Survey 1-year estimates, {y1}: Detailed tables",
            url=f"https://api.census.gov/data/{y1}/acs/acs1",
            year=str(y1 + 1),
            vintage=f"ACS {y1} 1-year",
            query=f"https://api.census.gov/data/{y1}/acs/acs1?get=...&for={cd_for}&in={st_in}",
            notes="District, Wisconsin, and United States figures; margins of error at 90% confidence.",
        ),
        Source(
            id="acs5",
            publisher="U.S. Census Bureau",
            title=f"American Community Survey 5-year estimates, {y5 - 4}-{y5}: Detailed tables",
            url=f"https://api.census.gov/data/{y5}/acs/acs5",
            year=str(y5 + 1),
            vintage=f"ACS {y5 - 4}-{y5} 5-year",
            query=f"https://api.census.gov/data/{y5}/acs/acs5?get=...&for=county:*&in={st_in}",
            notes="County figures (5-year estimates are the most reliable for small counties).",
        ),
    ]
    n = len(label_checks)
    detail = (f"{n - len([c for c in label_checks if not c['ok']])} of {n} variable labels matched the Census Bureau's "
              f"official definitions for ACS {y1} 1-year and ACS {y5} 5-year. Education rows were chosen by label "
              f"({'found' if edu_ok else 'NOT found'}).")
    if bad:
        detail += f" Left out because the label did not match or the variable no longer exists: {', '.join(sorted(bad))}."
    checks = [{
        "id": "acs-labels",
        "title": "Every Census variable means what the atlas says it means",
        "status": "pass" if not bad and edu_ok else "warn",
        "detail": detail,
        "sources": ["acs1", "acs5"],
    }]
    return payload, sources, checks
