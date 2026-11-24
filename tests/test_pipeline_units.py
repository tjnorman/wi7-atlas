"""Unit tests for parsers and checks, using canned responses in each API's real format."""

from __future__ import annotations

import json

import pytest

from conftest import FakeFetcher


def test_config_loads(district):
    assert district.geoid == "5507"
    assert district.expectations["county_count"] == 26
    assert len(district.expectations["split_counties"]) == 5


def test_redact_hides_keys():
    from pipeline.http import redact

    assert redact("https://x/api?get=A&key=SECRET&for=us:1") == "https://x/api?get=A&key=REDACTED&for=us:1"
    assert "SECRET" not in redact("https://api.open.fec.gov/v1/x?api_key=SECRET")


def test_census_query_chunks_and_merges():
    from pipeline import census

    def answer(url, _):
        import urllib.parse

        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        vars_ = q["get"][0].split(",")
        header = vars_ + ["state", "congressional district"]
        row = ["District 7"] + [str(i) for i in range(1, len(vars_))] + ["55", "07"]
        return [header, row]

    f = FakeFetcher([(r"api\.census\.gov", answer)])
    many = [f"B01001_{i:03d}E" for i in range(1, 60)]
    rows = census.query(f, "2025/acs/acs1", many, "congressional district:07", "state:55")
    assert len(rows) == 1
    assert rows[0]["NAME"] == "District 7"
    assert all(v in rows[0] for v in many)
    assert len(f.calls) == 2  # 59 variables -> two chunks of at most 48


def test_census_missing_values_become_none():
    from pipeline.census import _num

    assert _num("-666666666") is None
    assert _num("12.5") == 12.5
    assert _num(None) is None


@pytest.mark.parametrize("label,expected,ok", [
    ("Estimate!!Total:!!Male:!!Under 5 years", "=estimate!!total!!male!!under 5 years", True),
    ("Estimate!!Total:!!Female:!!Under 5 years", "=estimate!!total!!male!!under 5 years", False),
    ("Estimate!!Total:!!Veteran", "=estimate!!total!!veteran", True),
    ("Estimate!!Total:!!Nonveteran", "=estimate!!total!!veteran", False),
    ("Estimate!!Median household income in the past 12 months (in 2025 inflation-adjusted dollars)",
     "median household income", True),
])
def test_label_matching(label, expected, ok):
    from pipeline.census import label_matches

    assert label_matches(label, expected) is ok


def test_acs_summarize_computes_shares():
    from pipeline.sources import acs

    row = {v: 0.0 for v in acs.all_variables()}
    row.update({"B01003_001E": 1000.0, "B01001_001E": 1000.0, "B17001_001E": 900.0, "B17001_002E": 90.0,
                "B15003_001E": 600.0, "B15003_022E": 100.0, "B15003_023E": 50.0, "B15003_017E": 200.0,
                "B08013_001E": 24000.0, "B08303_001E": 1000.0, "B03002_001E": 1000.0, "B03002_005E": 30.0,
                "B01001_020E": 50.0, "B01001_044E": 70.0})
    edu = {"total": "B15003_001E", "hs": ["B15003_017E", "B15003_022E", "B15003_023E"], "ba": ["B15003_022E", "B15003_023E"]}
    s = acs.summarize(row, bad=set(), edu=edu)
    assert s["metrics"]["poverty_pct"] == pytest.approx(10.0)
    assert s["metrics"]["hs_plus_pct"] == pytest.approx(350 / 6)
    assert s["metrics"]["bachelors_plus_pct"] == pytest.approx(25.0)
    assert s["metrics"]["mean_commute_min"] == pytest.approx(24.0)
    assert s["metrics"]["age_65_plus_pct"] == pytest.approx(12.0)
    aian = next(r for r in s["race"] if r["id"] == "aian")
    assert aian["pct"] == pytest.approx(3.0)


def test_acs_bad_label_drops_metric():
    from pipeline.sources import acs

    row = {v: 1.0 for v in acs.all_variables()}
    s = acs.summarize(row, bad={"B17001_002E"})
    assert s["metrics"]["poverty_pct"] is None
    assert s["metrics"]["population"] == 1.0


def test_every_metric_variable_has_an_expected_label():
    from pipeline.sources import acs

    for m in acs.METRICS:
        for v in m.num + m.den:
            assert v in acs.EXPECT, f"{m.id}: {v} has no expected label"


REL = (
    "OID_CD119_20|GEOID_CD119_20|NAMELSAD_CD119_20|AREALAND_CD119_20|AREAWATER_CD119_20|MTFCC_CD119_20|"
    "FUNCSTAT_CD119_20|OID_COUNTY_20|GEOID_COUNTY_20|NAMELSAD_COUNTY_20|AREALAND_COUNTY_20|AREAWATER_COUNTY_20|"
    "MTFCC_COUNTY_20|FUNCSTAT_COUNTY_20|AREALAND_PART|AREAWATER_PART\n"
    "1|5507|Congressional District 7|100|0|G5200|N|2|55003|Ashland County|1000|50|G4020|A|1000|50\n"
    "1|5507|Congressional District 7|100|0|G5200|N|3|55017|Chippewa County|2000|10|G4020|A|500|2\n"
    "1|5507|Congressional District 7|100|0|G5200|N|4|55999|Lake County|0|900|G4020|A|0|30\n"
    "1|5503|Congressional District 3|100|0|G5200|N|3|55017|Chippewa County|2000|10|G4020|A|1500|8\n"
)


def test_relationship_parsing(district):
    from pipeline.sources import geography

    f = FakeFetcher([(r"tab20_cd11920_county20_st55", REL)])
    parts, url = geography.relationship(f, district)
    assert [p["county_fips"] for p in parts] == ["003", "017", "999"]
    ash, chip = parts[0], parts[1]
    assert ash["land_share"] == pytest.approx(1.0)
    assert chip["land_share"] == pytest.approx(0.25)


PEP = (
    "SUMLEV,REGION,DIVISION,STATE,COUNTY,STNAME,CTYNAME,ESTIMATESBASE2020,POPESTIMATE2020,POPESTIMATE2021,"
    "BIRTHS2020,BIRTHS2021,DEATHS2020,DEATHS2021,NATURALCHG2020,NATURALCHG2021,DOMESTICMIG2020,DOMESTICMIG2021,"
    "INTERNATIONALMIG2020,INTERNATIONALMIG2021,NETMIG2020,NETMIG2021\n"
    "040,2,3,55,000,Wisconsin,Wisconsin,5893718,5896271,5880101,10,20,30,40,-20,-20,5,6,1,1,6,7\n"
    "050,2,3,55,003,Wisconsin,Ashland County,16027,16021,15950,1,2,3,4,-2,-2,10,11,0,0,10,11\n"
)


def test_pep_parsing(district, monkeypatch):
    from pipeline.sources import pep

    class FixedDate:
        @staticmethod
        def now(tz=None):
            import datetime as dt
            return dt.datetime(2022, 6, 1, tzinfo=dt.timezone.utc)

    monkeypatch.setattr(pep, "datetime", FixedDate)
    f = FakeFetcher([(r"co-est2022", Exception), (r"co-est2021-alldata", PEP)])
    f.routes[0] = (f.routes[0][0], lambda *_: __import__("pipeline.http", fromlist=["FetchError"]).FetchError("404"))
    payload, sources, _ = pep.fetch(f, district)
    ash = payload["counties"]["003"]
    assert payload["vintage"] == 2021
    assert ash["estimates"]["2021"] == 15950
    assert ash["components_since_2020"]["netmig"] == 21
    assert payload["state"]["name"] == "Wisconsin"


HOUSE = (
    "year,state,state_po,state_fips,state_cen,state_ic,office,district,stage,runoff,special,candidate,party,"
    "writein,mode,candidatevotes,totalvotes,unofficial,version,fusion_ticket\n"
    "2024,WISCONSIN,WI,55,35,25,US HOUSE,7,GEN,FALSE,FALSE,THOMAS P. TIFFANY,REPUBLICAN,FALSE,TOTAL,300000,470000,FALSE,1,FALSE\n"
    "2024,WISCONSIN,WI,55,35,25,US HOUSE,7,GEN,FALSE,FALSE,KYLE KILBOURN,DEMOCRAT,FALSE,TOTAL,170000,470000,FALSE,1,FALSE\n"
    "2020,WISCONSIN,WI,55,35,25,US HOUSE,7,GEN,FALSE,TRUE,THOMAS P. TIFFANY,REPUBLICAN,FALSE,TOTAL,100,200,FALSE,1,FALSE\n"
    "2024,WISCONSIN,WI,55,35,25,US HOUSE,3,GEN,FALSE,FALSE,SOMEONE ELSE,REPUBLICAN,FALSE,TOTAL,1,1,FALSE,1,FALSE\n"
)


def test_house_results_parsing():
    from pipeline.sources import elections

    res = elections.parse(HOUSE, "WI", 7, 1976)
    assert [r["year"] for r in res] == [2024]  # special election excluded, other district excluded
    top = res[0]["candidates"][0]
    assert top["name"] == "Thomas P. Tiffany"
    assert top["party"] == "Republican"
    assert top["pct"] == pytest.approx(100 * 300000 / 470000)


VOTE_XML = b"""<?xml version="1.0"?>
<rollcall-vote><vote-metadata><majority>R</majority><congress>119</congress><session>1st</session>
<rollcall-num>12</rollcall-num><legis-num>H R 123</legis-num><vote-question>On Passage</vote-question>
<vote-type>YEA-AND-NAY</vote-type><vote-result>Passed</vote-result><action-date>15-Jan-2025</action-date>
<vote-desc>A test bill</vote-desc></vote-metadata><vote-data>
<recorded-vote><legislator name-id="T000165" party="R" state="WI" role="legislator">Tiffany</legislator><vote>Yea</vote></recorded-vote>
<recorded-vote><legislator name-id="A000001" party="R" state="OH" role="legislator">A</legislator><vote>Yea</vote></recorded-vote>
<recorded-vote><legislator name-id="B000001" party="D" state="CA" role="legislator">B</legislator><vote>Nay</vote></recorded-vote>
<recorded-vote><legislator name-id="C000001" party="D" state="NY" role="legislator">C</legislator><vote>Not Voting</vote></recorded-vote>
</vote-data></rollcall-vote>"""


def test_vote_parsing_and_rates(district, monkeypatch):
    from pipeline.sources import votes

    v = votes.parse_vote(VOTE_XML)
    assert v["roll"] == 12 and v["date"] == "2025-01-15"
    assert v["by_party"]["R"]["Yea"] == 2
    assert votes.bill_url("H R 123", 119) == "https://www.congress.gov/bill/119th-congress/house-bill/123"

    def route(url, _):
        if url.endswith("2025/roll001.xml"):
            return VOTE_XML
        from pipeline.http import FetchError
        return FetchError("404")

    import datetime as dt

    class D(dt.date):
        @classmethod
        def today(cls):
            return dt.date(2025, 6, 1)

    monkeypatch.setattr(votes, "date", D)
    f = FakeFetcher([(r"clerk\.house\.gov", route)])
    terms = [{"bioguide": "T000165", "name": "Tom Tiffany", "start": "2025-01-03", "end": "2027-01-03", "party": "Republican"}]
    payload, _, _ = votes.fetch(f, district, terms)
    assert payload["votes_cast"] == 1
    assert payload["with_party_majority_pct"] == 100.0
    assert payload["on_winning_side_pct"] == 100.0
    assert payload["house_missed_pct"] == pytest.approx(25.0)
    assert payload["gaps"] == []


def test_seat_history_merges_consecutive_terms():
    from pipeline.sources import legislators

    people = [{
        "id": {"bioguide": "T000165"}, "name": {"official_full": "Thomas P. Tiffany", "last": "Tiffany"},
        "terms": [
            {"type": "rep", "state": "WI", "district": 7, "party": "Republican", "start": "2020-05-19", "end": "2021-01-03"},
            {"type": "rep", "state": "WI", "district": 7, "party": "Republican", "start": "2021-01-03", "end": "2023-01-03"},
            {"type": "rep", "state": "WI", "district": 3, "party": "Republican", "start": "2019-01-03", "end": "2020-01-03"},
        ],
    }]
    terms = legislators.seat_terms(people, "WI", 7)
    members = legislators.members_from_terms(terms)
    assert len(terms) == 2 and len(members) == 1
    assert members[0]["terms"] == 2 and members[0]["end"] == "2023-01-03"


def test_checks_detect_mismatch(district):
    from pipeline import checks

    geo = {"data": {"county_count": 26, "whole_count": 20, "split": ["Chippewa", "Jackson", "Juneau", "Monroe", "Wood", "Polk"],
                    "counties": [], "pop_2020": 736715, "pop_2020_sum_of_parts": 736714, "boundary": None,
                    "land_sq_mi_relationship": 0}}
    res = {c["id"]: c for c in checks.run(district, {"geography": geo}, [], [])}
    assert res["county-list"]["status"] == "fail"
    assert res["pop-2020"]["status"] == "fail"
    assert res["acs-share"]["status"] == "skip"


def test_checks_pass_on_consistent_data(district):
    from pipeline import checks

    counties = [{"short_name": n, "whole": n not in district.expectations["split_counties"],
                 "pop_2020_in_district": 10, "pop_2020_county": 10 if n not in district.expectations["split_counties"] else 20,
                 "county_fips": f"{i:03d}"} for i, n in enumerate(
        ["A%02d" % i for i in range(21)] + district.expectations["split_counties"])]
    geo = {"data": {"county_count": 26, "whole_count": 21, "split": district.expectations["split_counties"],
                    "counties": counties, "pop_2020": 736715, "pop_2020_sum_of_parts": 736715,
                    "boundary": {"land_sq_mi": 23110.0}, "land_sq_mi_relationship": 23111.0}}
    res = {c["id"]: c for c in checks.run(district, {"geography": geo}, [], [])}
    for k in ("county-list", "pop-2020", "whole-county-pop", "land-area"):
        assert res[k]["status"] == "pass", res[k]


def test_overdue_note_is_flagged(district):
    from pipeline import checks

    notes = [{"id": "x", "title": "Old note", "status": "unofficial", "verified_on": "2020-01-01",
              "review_by": "2020-02-01", "sources": [{"id": "s"}]}]
    res = {c["id"]: c for c in checks.run(district, {}, notes, [])}
    assert res["note-x"]["status"] == "warn"


def test_curated_notes_have_sources():
    from pipeline.build import load_notes

    for n in load_notes():
        assert n["sources"], n["id"]
        assert n["review_by"] and n["verified_on"]
        for s in n["sources"]:
            assert s["url"].startswith("https://")


def test_fec_workbook_parsing():
    import io
    from openpyxl import Workbook
    from pipeline.sources import elections

    wb = Workbook()
    wb.active.title = "Table 1"
    ws = wb.create_sheet("2022 US House Results")
    ws.append(["FEDERAL ELECTIONS 2022"])
    ws.append(["1", "STATE", "STATE ABBREVIATION", "D", "FEC ID#", "(I)", "CANDIDATE NAME", "PARTY", "PRIMARY VOTES", "GENERAL VOTES ", "GE WINNER INDICATOR"])
    ws.append([2, "Wisconsin", "WI", "07", "H0WI07101", "(I)", "Tiffany, Thomas P.", "R", 1000, 209224, "W"])
    ws.append([3, "Wisconsin", "WI", "07", "H2WI07999", "", "Ausman, Richard", "D", 900, 135759, ""])
    ws.append([4, "Wisconsin", "WI", "07", "", "", "Scattered", "W", None, 210, ""])
    ws.append([5, "Wisconsin", "WI", "07", "", "", "District Votes:", "", None, 345193, ""])
    ws.append([6, "Wisconsin", "WI", "03", "", "", "Someone Else", "R", None, 5, ""])
    buf = io.BytesIO()
    wb.save(buf)
    r = elections.parse_fec_xlsx(buf.getvalue(), 2022, "WI", 7)
    assert r["year"] == 2022 and r["new_lines"] is True
    names = [c["name"] for c in r["candidates"]]
    assert names == ["Thomas P. Tiffany", "Richard Ausman", "Scattering (write-ins)"]
    assert r["candidates"][0]["party"] == "Republican" and r["candidates"][1]["party"] == "Democrat"
    assert r["total_votes"] == 209224 + 135759 + 210


def test_surname_normalization():
    from pipeline.sources.elections import surname

    assert surname("Sean P. Duffy") == surname("Sean P Duffy") == "duffy"
    assert surname("David R. Obey Jr.") == "obey"


def test_bls_series_ids_have_the_official_length():
    from pipeline.sources.laus import county_series, state_series

    assert county_series("55", "003") == "LAUCN550030000000003"
    assert state_series("55") == "LAUST550000000000003"
    assert len(county_series("55", "003")) == len(state_series("55")) == 20


def _labels(rows):
    lab = {"B15003_001E": "Estimate!!Total:"}
    for i, name in enumerate(rows, start=2):
        lab[f"B15003_{i:03d}E"] = f"Estimate!!Total:!!{name}"
    return lab


def test_education_rows_found_by_label_in_old_and_new_layouts():
    from pipeline.sources import acs

    old = _labels(["No schooling completed"] + [f"Grade {g}" for g in range(1, 15)] +
                  ["Regular high school diploma", "GED or alternative credential", "Some college, less than 1 year",
                   "Some college, 1 or more years, no degree", "Associate's degree", "Bachelor's degree",
                   "Master's degree", "Professional school degree", "Doctorate degree"])
    e = acs.edu_vars(old)
    assert e["ba"] == ["B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E"]
    assert len(e["hs"]) == 9
    # A renumbered layout like the 2025 release: fewer rows below high school.
    new = _labels(["No schooling completed", "Nursery school to 12th grade, no diploma"] + [f"Other {g}" for g in range(11)] +
                  ["Regular high school diploma", "GED or alternative credential", "Some college, no degree",
                   "Associate's degree", "Bachelor's degree", "Master's degree", "Professional school degree", "Doctorate degree"])
    e2 = acs.edu_vars(new)
    assert [new[v].split("!!")[-1] for v in e2["ba"]] == ["Bachelor's degree", "Master's degree", "Professional school degree", "Doctorate degree"]
    assert all("no diploma" not in new[v].lower() for v in e2["hs"])
    assert len(e2["hs"]) == 8


def test_gazetteer_year_comes_from_the_file_downloaded():
    from pipeline.sources.geography import gazetteer_year
    url = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_119CDs_national.zip"
    assert gazetteer_year(url) == "2024"
    assert gazetteer_year(None) is None
    assert gazetteer_year("https://example.com/no-year.zip") is None


# ---------------------------------------------------------------- IRS income tax by district
def _irs_docx(rows, text="Money amounts are reported in thousands of dollars. Districts are those of the 118th Congress."):
    import io
    import zipfile

    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    cell = lambda t: f"<w:tc><w:p><w:r><w:t>{t}</w:t></w:r></w:p></w:tc>"
    table = "".join("<w:tr>" + "".join(cell(c) for c in r) + "</w:tr>" for r in rows)
    doc = f'<w:document {ns}><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p><w:tbl>{table}</w:tbl></w:body></w:document>'
    core = ('<cp:coreProperties xmlns:cp="x" xmlns:dcterms="http://purl.org/dc/terms/">'
            '<dcterms:modified xsi:type="dcterms:W3CDTF" xmlns:xsi="y">2026-10-20T12:00:00Z</dcterms:modified></cp:coreProperties>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", doc)
        z.writestr("docProps/core.xml", core)
    return buf.getvalue()


IRS_DOC_ROWS = [
    ["N1", "Number of returns", "", "Num"],
    ["A00100", "Adjust gross income (AGI) [8]", "1040:11", "Num"],
    ["A10300", "Total tax liability amount [13]", "", "Num"],
    ["A06500", "Income tax after credits amount", "", "Num"],
    ["A59660", "Earned income credit amount [12]", "", "Num"],
    ["A11902", "Overpayments refunded amount [15]", "", "Num"],
    ["A11901", "Tax due at time of filing amount [14]", "", "Num"],
]
IRS_CSV = "\n".join([
    "STATEFIPS,STATE,CONG_DISTRICT,agi_stub,N1,A00100,A10300,A06500,A59660,A11902,A11901",
    "55,WI,0,0,3000,240000,30000,28000,900,6000,3000",
    "55,WI,7,0,400,28000,3000,2800,120,800,400",
    "55,WI,7,1,300,12000,600,500,120,600,100",
    "55,WI,7,2,100,16000,2400,2300,0,200,300",
    "55,WI,8,0,2590,212000,27000,25200,780,5200,2600",
    "27,MN,0,0,1000,100000,15000,14000,100,2000,1500",
    "27,MN,1,0,1000,100000,15000,14000,100,2000,1500",
])


def _irs_fetcher(doc_rows=IRS_DOC_ROWS, csv_text=IRS_CSV, **kw):
    from datetime import datetime, timezone

    from conftest import FakeFetcher

    y = str(datetime.now(timezone.utc).year - 1)[2:]
    return FakeFetcher([(rf"{y}incd\.csv", csv_text), (rf"{y}incddocguide", _irs_docx(doc_rows, **kw))])


def test_irs_totals_ratios_and_checks(district):
    from pipeline.sources import irs

    payload, sources, checks = irs.fetch(_irs_fetcher(), district)
    d = payload["district"]
    assert d["returns"] == 400 and d["total_tax_liability"] == 3_000_000 and d["agi"] == 28_000_000
    assert round(d["tax_per_return"]) == 7500 and round(d["tax_share_of_agi_pct"], 2) == 10.71
    assert payload["state"]["returns"] == 3000
    assert payload["us"]["returns"] == 4000  # Wisconsin and Minnesota state rows; districts not double counted
    status = {c["id"]: c["status"] for c in checks}
    assert status == {"irs-labels": "pass", "irs-classes-sum": "pass", "irs-state-sum": "pass", "irs-district-lines": "pass"}
    assert sources[0].year == "2026" and "not all federal tax" in sources[0].notes


def test_irs_refuses_a_variable_whose_description_changed(district):
    from pipeline.sources import irs

    moved = [r if r[0] != "A10300" else ["A10300", "Something else entirely"] for r in IRS_DOC_ROWS]
    with pytest.raises(ValueError, match="A10300"):
        irs.fetch(_irs_fetcher(doc_rows=moved), district)
    # An optional variable that fails is dropped and reported, and the rest still publishes.
    optional = [r if r[0] != "A11902" else ["A11902", "Renamed amount"] for r in IRS_DOC_ROWS]
    payload, _, checks = irs.fetch(_irs_fetcher(doc_rows=optional), district)
    assert "refunds" not in payload["district"]
    assert next(c for c in checks if c["id"] == "irs-labels")["status"] == "warn"


def test_irs_withholds_a_value_that_is_not_believable(district):
    from pipeline.sources import irs

    # Refunds for the district larger than half of its income: right label, wrong number.
    broken = IRS_CSV.replace("55,WI,7,0,400,28000,3000,2800,120,800,400", "55,WI,7,0,400,28000,3000,2800,120,23000,400")
    payload, _, checks = irs.fetch(_irs_fetcher(csv_text=broken), district)
    assert "refunds" not in payload["district"] and payload["district"]["total_tax_liability"] == 3_000_000
    assert any("A11902" in m and "withheld" in m for m in payload["not_published"])


def test_irs_needs_units_stated(district):
    from pipeline.sources import irs

    with pytest.raises(ValueError, match="thousands"):
        irs.fetch(_irs_fetcher(text="No units here."), district)


# ---------------------------------------------------------------- cameras and live aircraft
SQUARE = {"district": {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": {
    "type": "Polygon", "coordinates": [[[-91, 45], [-90, 45], [-90, 46], [-91, 46], [-91, 45]]]}}]},
    "parts": {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"county_fips": "073"}, "geometry": {
        "type": "Polygon", "coordinates": [[[-91, 45], [-90, 45], [-90, 46], [-91, 46], [-91, 45]]]}}]}}


def _square(tmp_path):
    p = tmp_path / "shape.json"
    p.write_text(json.dumps(SQUARE))
    return p


def test_cameras_keep_only_usable_ones_inside_the_district(district, tmp_path):
    from conftest import FakeFetcher
    from pipeline.sources import cameras

    cam = lambda id_, lat, lng, url="https://511wi.gov/map/Cctv/1", **kw: {
        "id": id_, "name": id_, "url": url, "category": "highway", "verified": True, "auth": False,
        "coordinates": {"lat": lat, "lng": lng}, **kw}
    registry = [cam("in", 45.5, -90.5), cam("outside", 44.0, -90.5), cam("http", 45.5, -90.5, url="http://x.gov/a.jpg"),
                cam("secret", 45.5, -90.5, url="https://x.gov/a.jpg?token=abc"), cam("login", 45.5, -90.5, auth={"required": True}),
                cam("ip", 45.5, -90.5, url="https://10.0.0.1/a.jpg"), cam("unverified", 45.5, -90.5, verified=False)]
    payload, sources, _ = cameras.fetch(FakeFetcher([("Open-Eagle-Eye", registry)]), district, _square(tmp_path), {"073": "Marathon"})
    assert [c["id"] for c in payload["cameras"]] == ["in"]
    assert payload["cameras"][0]["county"] == "Marathon" and "Wisconsin Department of Transportation" in payload["cameras"][0]["operator"]
    assert sum(payload["rejected_inside_district"].values()) == 5 and sources[0].id == "open-eagle-eye"


def test_live_snapshot_filters_to_the_district_and_falls_back(tmp_path):
    import importlib.util

    import pathlib

    spec = importlib.util.spec_from_file_location(
        "live_snapshot", pathlib.Path(__file__).resolve().parent.parent / "tools" / "live_snapshot.py")
    live = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(live)
    from pipeline.geo import DistrictShape

    shape = DistrictShape(_square(tmp_path))
    lat, lon, nm = live.circle(shape.bbox)
    assert (lat, lon) == (45.5, -90.5) and 30 < nm < 60
    calls = []

    def get(url):
        calls.append(url)
        if "adsb.lol" in url:
            raise RuntimeError("down")
        return {"ac": [{"hex": "A1B2C3", "flight": "DAL123 ", "lat": 45.5, "lon": -90.5, "alt_baro": 35000, "gs": 450.4, "track": 271.2, "t": "B739"},
                       {"hex": "ffffff", "lat": 44.0, "lon": -90.5, "alt_baro": "ground"}, {"hex": "nopos"}]}

    snap = live.snapshot(shape, get)
    assert snap["ok"] and snap["source"] == "adsb.fi" and snap["errors"] == ["adsb.lol: RuntimeError"]
    assert snap["heard_in_circle"] == 2 and snap["count"] == 1
    assert snap["aircraft"][0] == {"hex": "a1b2c3", "callsign": "DAL123", "lat": 45.5, "lon": -90.5, "altitude_ft": 35000,
                                   "on_ground": False, "speed_kt": 450, "track": 271, "type": "B739", "category": None}
    assert live.snapshot(shape, lambda url: (_ for _ in ()).throw(RuntimeError("x")))["ok"] is False


def _roll(year, n, day, seat_votes):
    """A small roll call; seat_votes maps bioguide -> vote for whoever held the seat."""
    members = "".join(f'<recorded-vote><legislator name-id="{b}" party="R" state="WI">x</legislator><vote>{v}</vote></recorded-vote>'
                      for b, v in seat_votes.items())
    return (f'<rollcall-vote><vote-metadata><congress>{(year - 1789) // 2 + 1}</congress><session>1st</session>'
            f'<rollcall-num>{n}</rollcall-num><legis-num>H R {n}</legis-num><vote-question>On Passage</vote-question>'
            f'<vote-type>YEA-AND-NAY</vote-type><vote-result>Passed</vote-result><action-date>{day}-{year}</action-date>'
            f'<vote-desc>Bill {n}</vote-desc></vote-metadata><vote-data>{members}'
            '<recorded-vote><legislator name-id="A000001" party="R" state="OH">A</legislator><vote>Yea</vote></recorded-vote>'
            '<recorded-vote><legislator name-id="B000001" party="D" state="CA">B</legislator><vote>Nay</vote></recorded-vote>'
            '</vote-data></rollcall-vote>').encode()


def test_ten_year_attendance_follows_the_seat(district, monkeypatch):
    from pipeline.http import FetchError
    from pipeline.sources import votes

    calls = {
        "2019/roll001": _roll(2019, 1, "10-Jan", {"D000614": "Yea"}),
        "2019/roll002": _roll(2019, 2, "11-Jan", {"D000614": "Not Voting"}),
        "2020/roll001": _roll(2020, 1, "10-Jan", {}),                       # seat vacant
        "2020/roll002": _roll(2020, 2, "20-May", {"T000165": "Nay"}),
        "2025/roll001": _roll(2025, 1, "15-Jan", {"T000165": "Not Voting"}),
    }

    def route(url, _):
        key = next((k for k in calls if url.endswith(k + ".xml")), None)
        return calls[key] if key else FetchError("404")

    import datetime as dt

    class D(dt.date):
        @classmethod
        def today(cls):
            return dt.date(2025, 6, 1)

    monkeypatch.setattr(votes, "date", D)
    terms = [{"bioguide": "D000614", "name": "Sean P. Duffy", "start": "2019-01-03", "end": "2019-09-23", "party": "Republican"},
             {"bioguide": "T000165", "name": "Thomas P. Tiffany", "start": "2020-05-19", "end": "2027-01-03", "party": "Republican"}]
    p, sources, _ = votes.fetch(FakeFetcher([(r"clerk\.house\.gov", route)]), district, terms)
    assert p["period"] == {"from_year": 2017, "to_year": 2025, "roll_calls_parsed": 5, "through": "2025-01-15"}
    years = {y["year"]: y for y in p["by_year"]}
    assert years[2019]["members"] == ["Sean P. Duffy"] and years[2019]["missed"] == 1 and years[2019]["missed_pct"] == 50.0
    assert years[2020]["while_seat_vacant"] == 1 and years[2020]["yes_no_votes_while_held"] == 1 and years[2020]["missed"] == 0
    members = {m["name"]: m for m in p["by_member"]}
    assert members["Thomas P. Tiffany"]["missed"] == 1 and members["Thomas P. Tiffany"]["yes_no_votes_while_held"] == 2
    assert members["Sean P. Duffy"]["last_vote"] == "2019-01-11"
    assert [(m["date"], m["member"]) for m in p["missed_votes"]] == [("2025-01-15", "Thomas P. Tiffany"), ("2019-01-11", "Sean P. Duffy")]
    assert p["missed_votes"][1]["bill_url"].startswith("https://www.congress.gov/bill/116th-congress/")
    # The headline figures still describe the current Congress only.
    assert p["yes_no_votes_while_held"] == 1 and p["missed"] == 1 and p["roll_calls_parsed"] == 1
    assert "2017 to 2025" in sources[0].title


# ---------------------------------------------------------------- colleges (IPEDS)
def _ipeds_zip(csv_text):
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(zipfile.ZipInfo("hd2025.csv", date_time=(2026, 9, 1, 0, 0, 0)), csv_text)
    return buf.getvalue()


def _ipeds_dict(titles, codes):
    import io
    import zipfile

    import openpyxl

    wb = openpyxl.Workbook()
    v = wb.active
    v.title = "Varlist"
    v.append(["varNumber", "varName", "DataType", "FieldWidth", "format", "imputationvar", "varTitle"])
    for name, title in titles.items():
        v.append([1, name, "A", 1, "", "", title])
    f = wb.create_sheet("Frequencies")
    f.append(["varnumber", "varname", "codevalue", "valuelabel", "frequency", "percent"])
    for name, code, lab in codes:
        f.append([1, name, code, lab, 1, 1])
    x = io.BytesIO()
    wb.save(x)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hd2025.xlsx", x.getvalue())
    return buf.getvalue()


IPEDS_TITLES = {"INSTNM": "Institution (entity) name", "CITY": "City location of institution", "STABBR": "State abbreviation",
                "WEBADDR": "Institution's internet website address", "LONGITUD": "Longitude location of institution",
                "LATITUDE": "Latitude location of institution", "CNGDSTCD": "Congressional district code",
                "CONTROL": "Control of institution", "ICLEVEL": "Level of institution", "INSTSIZE": "Institution size category",
                "CYACTIVE": "Institution is active in current year", "COUNTYNM": "County name", "CLOSEDAT": "Date institution closed"}
IPEDS_CODES = [("CONTROL", 1, "Public"), ("ICLEVEL", 1, "Four or more years"), ("ICLEVEL", 2, "At least 2 but less than 4 years"),
               ("INSTSIZE", 2, "1,000 - 4,999")]
IPEDS_CSV = ("UNITID,INSTNM,CITY,STABBR,WEBADDR,LONGITUD,LATITUDE,CNGDSTCD,CONTROL,ICLEVEL,INSTSIZE,CYACTIVE,COUNTYNM,CLOSEDAT\n"
             "1,Northwoods University,Wausau,WI,www.example.edu/,-90.5,45.5,5507,1,1,2,1,Marathon County,-2\n"
             "2,Elsewhere College,Madison,WI,elsewhere.edu,-89.4,43.07,5502,1,2,2,1,Dane County,-2\n"
             "3,Minnesota Tech,Duluth,MN,mn.edu,-90.5,45.5,2708,1,2,2,1,St. Louis County,-2\n"
             "4,Edge School,Edge,WI,,-90.4,45.4,5503,1,2,2,1,Marathon County,-2\n")


def _ipeds_fetcher(titles=IPEDS_TITLES):
    from pipeline.http import FetchError

    def route(url, _):
        if "HD2025_Dict" in url:
            return _ipeds_dict(titles, IPEDS_CODES)
        if "HD2025.zip" in url:
            return _ipeds_zip(IPEDS_CSV)
        return FetchError("404")

    return FakeFetcher([(r"nces\.ed\.gov", route)])


def test_colleges_inside_the_district(district, tmp_path, monkeypatch):
    import datetime as dt

    from pipeline.sources import colleges

    class Now(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 11, 23, tzinfo=tz)

    monkeypatch.setattr(colleges, "datetime", Now)
    payload, sources, checks = colleges.fetch(_ipeds_fetcher(), district, _square(tmp_path))
    names = [c["name"] for c in payload["institutions"]]
    assert names == ["Edge School", "Northwoods University"] and payload["directory_year"] == 2025
    nu = payload["institutions"][1]
    assert nu["website"] == "https://www.example.edu/" and nu["control"] == "Public" and nu["level"] == "Four or more years"
    assert nu["county"] == "Marathon" and nu["size"] == "1,000 - 4,999" and nu["closed"] is None
    assert payload["institutions"][0]["website"] is None
    status = {c["id"]: c["status"] for c in checks}
    assert status == {"ipeds-labels": "pass", "ipeds-district": "warn"}  # Edge School carries another district's code
    assert sources[0].year == "2026" and "HD2025" in sources[0].title

    renamed = dict(IPEDS_TITLES, LATITUDE="Something else")
    with pytest.raises(ValueError, match="LATITUDE"):
        colleges.fetch(_ipeds_fetcher(renamed), district, _square(tmp_path))


# ---------------------------------------------------------------- municipalities and broadcast stations
def test_municipality_status_by_land_share():
    from pipeline.sources.municipalities import classify

    assert classify({"07": 100}, 100, "07") == ("inside", 1.0)
    assert classify({"03": 100}, 100, "07")[0] == "outside"
    assert classify({"07": 60, "03": 40}, 100, "07") == ("split", 0.6)
    assert classify({"07": 1, "03": 99999}, 100000, "07")[0] == "outside"   # a boundary sliver
    assert classify({"07": 99999, "03": 1}, 100000, "07")[0] == "inside"


def _fcc(call, service, city, lat_deg, lon_deg, status="LIC", freq="88.1  MHz", channel="201", fid="1", licensee="SOMEBODY INC"):
    c = [""] * 41
    c[1], c[2], c[3], c[4], c[9], c[10], c[11], c[18] = call, freq, service, channel, status, city, "WI", fid
    c[19], c[20], c[21], c[22], c[23], c[24], c[25], c[26], c[27] = "N", str(lat_deg), "30", "0.0", "W", str(lon_deg), "30", "0.0", licensee
    return "|".join(c)


def test_broadcast_stations_by_transmitter_site(district, tmp_path):
    from pipeline.sources import broadcast

    fm = "\n".join(["header without pipes",
                    _fcc("WAAA", "FM", "WAUSAU", 45, 90, fid="10"),                      # inside the square (45.5, -90.5)
                    _fcc("WBBB", "FM", "MADISON", 43, 89, fid="11"),                     # far outside
                    _fcc("WCCC", "FM", "WAUSAU", 45, 89, fid="12"),                      # licensed here, tower just outside
                    _fcc("WDDD", "FM", "WAUSAU", 45, 90, status="CP", fid="13"),          # not licensed yet
                    _fcc("W250AA", "FX", "WAUSAU", 45, 90, fid="14")])                    # translator
    am = "\n".join([_fcc("WEEE", "AM", "MERRILL", 45, 90, freq="550   kHz", channel="", fid="20"),
                    _fcc("WEEE", "AM", "MERRILL", 45, 90, freq="550   kHz", channel="", fid="20")])  # day and night rows
    tv = _fcc("WFFF", "DTV", "WAUSAU", 45, 90, freq="-", channel="7", fid="30")

    def route(url, _):
        return am if "amq" in url else tv if "tvq" in url else fm if "serv=FM" in url else ""

    payload, sources, checks = broadcast.fetch(FakeFetcher([(r"fcc\.gov", route)]), district, _square(tmp_path),
                                               {"073": "Marathon"}, {"WAUSAU", "MERRILL"})
    assert [(s["call"], s["band"]) for s in payload["stations"]] == [("WEEE", "AM"), ("WAAA", "FM"), ("WFFF", "TV")]
    assert payload["by_band"] == {"AM": 1, "FM": 1, "TV": 1}
    assert payload["stations"][2]["channel"] == "7" and payload["stations"][2]["frequency"] is None
    assert payload["stations"][1]["transmitter_county"] == "Marathon" and payload["stations"][1]["licensee"] == "Somebody Inc"
    assert [s["call"] for s in payload["licensed_to_district_community_transmitter_outside"]] == ["WCCC"]
    assert checks[0]["status"] == "pass" and sources[0].id == "fcc-queries"

    with pytest.raises(ValueError, match="expected layout"):
        broadcast.fetch(FakeFetcher([(r"fcc\.gov", "|".join(["x"] * 30))]), district, _square(tmp_path), {}, set())
