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
