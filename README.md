<div align="center">

<a href="https://tjnorman.github.io/wi7-atlas/"><img src="docs/media/hero.webp" alt="Animated map of Wisconsin's 7th Congressional District: the district outline draws itself and its 26 counties light up" width="100%" /></a>

<h1>WI-7 Atlas</h1>

<h3>Wisconsin's 7th Congressional District, counted.</h3>

<p>A public, nonpartisan atlas of Wisconsin's 7th Congressional District: who lives there, how they make a living,<br/>what federal money reaches it, and how the seat in Congress has been held and voted.<br/><b>Every number links to its primary source, and independent sources are checked against each other before anything ships.</b></p>

<p>
<a href="https://tjnorman.github.io/wi7-atlas/"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/media/buttons/open-dark.svg" /><img src="docs/media/buttons/open-light.svg" alt="Open the atlas" height="52" /></picture></a>
&nbsp;
<a href="#-how-every-number-is-checked"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/media/buttons/checks-dark.svg" /><img src="docs/media/buttons/checks-light.svg" alt="How every number is checked" height="52" /></picture></a>
&nbsp;
<a href="data/wi-07/"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/media/buttons/data-dark.svg" /><img src="docs/media/buttons/data-light.svg" alt="Download the data" height="52" /></picture></a>
</p>

[![Tests](https://github.com/tjnorman/wi7-atlas/actions/workflows/tests.yml/badge.svg)](https://github.com/tjnorman/wi7-atlas/actions/workflows/tests.yml)
[![Data refresh](https://github.com/tjnorman/wi7-atlas/actions/workflows/data.yml/badge.svg)](https://github.com/tjnorman/wi7-atlas/actions/workflows/data.yml)
[![Deploy to Pages](https://github.com/tjnorman/wi7-atlas/actions/workflows/pages.yml/badge.svg)](https://github.com/tjnorman/wi7-atlas/actions/workflows/pages.yml)
[![Cross-checks](https://img.shields.io/badge/cross--checks-21_of_21_passing-2e7d32)](#-how-every-number-is-checked)
[![Sources](https://img.shields.io/badge/primary_sources-8-0071e3)](#-sources)
[![Data as of](https://img.shields.io/badge/data_as_of-2026--11--23-555)](data/wi-07/manifest.json)
![Nonpartisan](https://img.shields.io/badge/nonpartisan-follows_the_seat-555)
[![License: MIT](https://img.shields.io/badge/code-MIT-1f4e9c)](LICENSE)

<table>
<tr>
<td align="center" width="25%"><h2>750,669</h2>People</td>
<td align="center" width="25%"><h2>23,111</h2>Square miles of land</td>
<td align="center" width="25%"><h2>26</h2>Counties</td>
<td align="center" width="25%"><h2>$76,055</h2>Median household income</td>
</tr>
<tr>
<td align="center" width="25%"><h2>46.3</h2>Median age</td>
<td align="center" width="25%"><h2>7.5%</h2>Adults who are veterans</td>
<td align="center" width="25%"><h2>90.3%</h2>Households with broadband</td>
<td align="center" width="25%"><h2>17.4%</h2>Homes held for seasonal use</td>
</tr>
</table>

<sub>People, income, age, and homes: American Community Survey 2025 1-year estimates. Land and counties: U.S. Census Bureau, 119th Congress boundaries. Federal awards: USAspending.gov.</sub>

[The district](#-the-district-in-one-picture) · [People](#-who-lives-here) · [Work](#-how-people-make-a-living) · [Federal dollars](#-federal-dollars) · [Representation](#-representation-and-elections) · [Counties](#-county-by-county) · [Checks](#-how-every-number-is-checked) · [Reuse it](#-reuse-it-for-another-district) · [Sources](#-sources)

</div>

---

## 🧭 What this is

<table>
<tr>
<td width="33%" valign="top">

### 📍 One district, in full
Twenty-six counties from Lake Superior to central Wisconsin, mapped to the boundaries the U.S. House uses today, with the five split counties drawn as they really are.

</td>
<td width="33%" valign="top">

### 🧾 Every number has a receipt
Each figure carries its publisher, the exact query, the data vintage, and the day it was retrieved. Sources are cited in APA style on the site and below.

</td>
<td width="33%" valign="top">

### 🔁 Refreshed and re-checked
A scheduled GitHub Action rebuilds the data each week, runs 21 cross-checks between independent sources, and redraws every chart in this README.

</td>
</tr>
</table>

<p align="center"><a href="https://tjnorman.github.io/wi7-atlas/media/tour.mp4"><img src="docs/media/tour.webp" alt="A tour of the WI-7 Atlas website: the district map draws itself, then the people, work, federal dollars, and representation sections scroll past" width="100%" /></a></p>
<p align="center"><sub>A 40-second tour of the website. Click for the full-quality video.</sub></p>

## 🖼 Gallery

<table>
<tr><td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/media/screens/land-dark.png" /><img src="docs/media/screens/land-light.png" alt="The scroll-driven map: each step recolors the counties" width="100%" /></picture><br/><sub>The scroll-driven map: each step recolors the counties</sub></td><td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/media/screens/people-dark.png" /><img src="docs/media/screens/people-light.png" alt="How the district compares with Wisconsin and the nation" width="100%" /></picture><br/><sub>How the district compares with Wisconsin and the nation</sub></td></tr>
<tr><td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/media/screens/seat-dark.png" /><img src="docs/media/screens/seat-light.png" alt="The seat: members, notes, votes, and elections" width="100%" /></picture><br/><sub>The seat: members, notes, votes, and elections</sub></td><td width="50%" valign="top"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/media/screens/trust-dark.png" /><img src="docs/media/screens/trust-light.png" alt="Every cross-check, in public" width="100%" /></picture><br/><sub>Every cross-check, in public</sub></td></tr>
</table>

## 🗺 The district in one picture

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/media/charts/map-dark.svg" /><img src="docs/media/charts/map-light.svg" alt="Map of Wisconsin's 7th Congressional District with counties shaded by population change since 2020" width="100%" /></picture></p>

Since the 2020 Census, **17 of the district's 26 counties have gained people and 9 have lost people** (whole-county estimates to July 2025). The largest gain is in **St. Croix County (+5.1%)** and the largest decline in **Douglas County (-0.7%)**. In 22 counties deaths have outnumbered births since 2020, and 25 counties have gained people through migration. It is the largest of Wisconsin's 8 districts by land area, covering 43% of the state's land. The district had **736,715 residents in the 2020 Census** and an estimated **750,669 in 2025**.

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/media/charts/population-dark.svg" /><img src="docs/media/charts/population-light.svg" alt="Bar chart of population change by county since 2020" width="100%" /></picture></p>

## 👥 Who lives here

American Community Survey 2025 1-year estimates. Margins of error appear on the website. American Indian and Alaska Native residents make up 2.0% of the district (not Hispanic, one race alone), compared with 0.6% nationally.

| | District | Wisconsin | United States |
|---|---:|---:|---:|
| Median age | **46.3** (±0.4) | 41.3 | 39.5 |
| Age 65 and older | **25.3%** | 20.9% | 19.0% |
| Veterans (adults) | **7.5%** | 5.7% | 5.9% |
| Homes held for seasonal use | **17.4%** | 5.2% | 2.9% |
| Households with broadband | **90.3%** | 92.7% | 94.0% |

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/media/charts/compare-dark.svg" /><img src="docs/media/charts/compare-light.svg" alt="Dot plot comparing the district with Wisconsin and the United States on ten measures" width="100%" /></picture></p>

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/media/charts/age-dark.svg" /><img src="docs/media/charts/age-light.svg" alt="Bar chart of the district's age groups compared with the United States" width="100%" /></picture></p>

## 💼 How people make a living

The most common line of work for district residents is **health care, social assistance, and education (22.4% of workers)**. Manufacturing employs **18.4%** of working residents, compared with 16.6% statewide. In September 2026, county unemployment rates ranged from **2.3% to 4.0%**, against 2.9% for Wisconsin and 4.0% nationally (not seasonally adjusted; the latest month is preliminary).

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/media/charts/industry-dark.svg" /><img src="docs/media/charts/industry-light.svg" alt="Bar chart of the share of workers in each industry" width="100%" /></picture></p>

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/media/charts/unemployment-dark.svg" /><img src="docs/media/charts/unemployment-light.svg" alt="Line chart of monthly unemployment for Wisconsin, the United States, and the range across district counties" width="100%" /></picture></p>

## 🏛 Federal dollars

In fiscal year 2026, federal agencies obligated **$5.74 billion** in contracts, grants, loans, and other awards for work performed in the district. The largest category was direct payments ($5.31 billion). Obligations are commitments to spend, and agencies revise them over time. Payments that agencies report only at the county or state level, such as many benefits paid to individuals, are not included.

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/media/charts/federal-dark.svg" /><img src="docs/media/charts/federal-light.svg" alt="Column chart of federal award obligations in the district by fiscal year" width="100%" /></picture></p>

<details><summary><b>Top awarding agencies, FY2026</b></summary>

| Agency | Obligations |
|---|---:|
| Social Security Administration | $4.55 billion |
| Department of Veterans Affairs | $468.6 million |
| Department of Transportation | $175.4 million |
| Department of Health and Human Services | $122.4 million |
| Department of Agriculture | $115.2 million |
| Department of the Interior | $64.5 million |

</details>

### What residents pay in federal income tax

On 368,470 individual returns for tax year 2023, people living in the district reported a total federal tax liability of **$3.61 billion**, or 12.2% of their adjusted gross income.

| Per return, tax year 2023 | Adjusted gross income | Federal income tax | Tax as a share of income |
|---|---:|---:|---:|
| The district | $80,296 | $9,803 | 12.2% |
| Wisconsin | $86,605 | $11,238 | 13.0% |
| United States | $95,156 | $14,127 | 14.8% |

<sub>Source: IRS Statistics of Income, congressional district data. Individual income tax returns only. Employer payroll taxes, corporate income tax, excise taxes, and estate taxes are not published by congressional district, so this is not the district's total federal tax, and it is not a balance against the awards above.</sub>

## 🗳 Representation and elections

The seat is held by **Thomas P. Tiffany (Republican)**, whose current term runs from January 3, 2025 to January 3, 2027. 17 people have represented the 7th District since 1873, under boundaries redrawn after each census.

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/media/charts/seat-dark.svg" /><img src="docs/media/charts/seat-light.svg" alt="Timeline of members who have held the seat" width="100%" /></picture></p>

> **2026 general election** — 🟡 Unofficial, verified November 20, 2026
>
> The Associated Press called the November 3, 2026 race for the open 7th District seat for Republican Michael Alfonso over Democrat Fred Clark on election night. Results stay unofficial until the Wisconsin Elections Commission completes the state canvass, which state law requires on or before December 1, 2026.
>
> <sub>Sources: [WPR, Nov 4, 2026](https://www.wpr.org/news/republican-michael-alfonso-wins-northern-wisconsin-district) · [Wis. Stat. § 7.70](https://docs.legis.wisconsin.gov/statutes/statutes/7/70) · [Brennan Center](https://www.brennancenter.org/our-work/research-reports/wisconsin-election-certification-processes-and-guardrails)</sub>

> **Change of member on January 3, 2027** — 🗓 Scheduled, verified November 20, 2026
>
> Rep. Tom Tiffany did not seek re-election to the House in 2026, so the seat was open. The term of the member elected in 2026 begins January 3, 2027, the date the 20th Amendment sets for House terms.
>
> <sub>Sources: [WPR results](https://www.wpr.org/news/wisconsin-congressional-election-results-november-2026) · [20th Amendment](https://constitution.congress.gov/constitution/amendment-20/)</sub>

<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/media/charts/elections-dark.svg" /><img src="docs/media/charts/elections-light.svg" alt="Stacked columns of each candidate's share in every general election for the seat" width="100%" /></picture></p>

<details open><summary><b>How the seat voted in the 119th Congress</b> (686 yes-or-no roll calls)</summary>

| Measure | The seat | Plain definition |
|---|---:|---|
| Votes missed | **11.2%** | Share of yes-or-no roll calls, while the member held the seat, recorded as Not Voting. House-wide: 3.2%. |
| Voted with own party's majority | **93.6%** | Share of the member's yes-or-no votes that matched the position taken by most members of the member's own party. Ties are left out. |
| Voted on the winning side | **83.6%** | Share of the member's yes-or-no votes that matched the outcome. |

Source: Office of the Clerk, U.S. House of Representatives, roll call votes. The website lists the 25 most recent votes with links.

</details>

<details><summary><b>Campaign money, 2026 cycle</b> (Federal Election Commission)</summary>

| Candidate | Party | Raised | Spent | Cash on hand | Through |
|---|---|---:|---:|---:|---|
| [Wassgren, Paul](https://www.fec.gov/data/candidate/H6WI07215/?cycle=2026) | REPUBLICAN PARTY | $3.4 million | $3.4 million | $0 | 2026-06-30 |
| [Alfonso, Michael](https://www.fec.gov/data/candidate/H6WI07223/?cycle=2026) | REPUBLICAN PARTY | $1.8 million | $1.3 million | $426,939 | 2026-10-14 |
| [Hermening, Kevin](https://www.fec.gov/data/candidate/H6WI07249/?cycle=2026) | REPUBLICAN PARTY | $1.6 million | $1.5 million | $51,049 | 2026-09-30 |
| [Clark, Frederic](https://www.fec.gov/data/candidate/H6WI07207/?cycle=2026) | DEMOCRATIC PARTY | $863,780 | $602,936 | $260,844 | 2026-10-14 |
| [Ebben, Jessi](https://www.fec.gov/data/candidate/H0WI03159/?cycle=2026) | REPUBLICAN PARTY | $555,645 | $496,402 | $60,845 | 2026-09-30 |
| [Tiffany, Tom](https://www.fec.gov/data/candidate/H0WI07101/?cycle=2026) | REPUBLICAN PARTY | $170,882 | $326,460 | $20,363 | 2026-10-14 |
| [Murray, Ginger L](https://www.fec.gov/data/candidate/H6WI07231/?cycle=2026) | DEMOCRATIC PARTY | $159,921 | $138,920 | $21,000 | 2026-07-22 |
| [Armstrong, Christopher Campbell](https://www.fec.gov/data/candidate/H6WI07199/?cycle=2026) | DEMOCRATIC PARTY | $38,552 | $38,875 | $-323 | 2026-09-30 |
| [Threlfall-Baum, Niina](https://www.fec.gov/data/candidate/H6WI07256/?cycle=2026) | REPUBLICAN PARTY | $25,274 | $21,024 | $4,249 | 2026-07-22 |

Totals for each candidate's principal campaign committee over the two-year cycle, through its latest report. Sorted by amount raised.

</details>

## 🏘 County by county

<details open><summary><b>All 26 counties</b></summary>

| County | In district | Population 2025 | Since 2020 | Median household income | Median age | Unemployment | Jobs (QCEW) |
|---|---|---:|---:|---:|---:|---:|---:|
| Ashland | Whole | 16,203 | +1.1% | $62,462 | 43.1 | 2.9% | 7,864 |
| Barron | Whole | 46,484 | -0.5% | $65,933 | 44.9 | 2.8% | 21,222 |
| Bayfield | Whole | 16,787 | +3.5% | $71,151 | 54.6 | 3.0% | 4,295 |
| Burnett | Whole | 17,223 | +4.2% | $62,819 | 56.0 | 3.3% | 5,212 |
| Chippewa | Part (47% of people) | 67,614 | +2.0% | $74,680 | 42.2 | 2.7% | 27,224 |
| Clark | Whole | 35,052 | +1.2% | $67,400 | 36.7 | 2.3% | 11,428 |
| Douglas | Whole | 43,990 | -0.7% | $75,099 | 42.7 | 3.5% | 15,643 |
| Florence | Whole | 4,748 | +4.1% | $61,086 | 55.3 | 3.4% | 954 |
| Forest | Whole | 9,574 | +4.2% | $61,071 | 49.3 | 2.9% | 3,222 |
| Iron | Whole | 6,127 | -0.2% | $60,625 | 56.1 | 4.0% | 1,615 |
| Jackson | Part (10% of people) | 20,999 | -0.7% | $68,110 | 43.4 | 3.1% | 7,570 |
| Juneau | Part (22% of people) | 26,649 | -0.3% | $67,270 | 45.8 | 3.0% | 9,194 |
| Langlade | Whole | 19,534 | +0.2% | $55,878 | 48.7 | 3.0% | 7,152 |
| Lincoln | Whole | 28,403 | -0.0% | $68,164 | 49.3 | 2.9% | 9,938 |
| Marathon | Whole | 139,432 | +1.0% | $77,884 | 41.3 | 2.5% | 69,778 |
| Monroe | Part (10% of people) | 46,572 | +0.6% | $69,467 | 39.7 | 2.6% | 21,034 |
| Oneida | Whole | 38,131 | +0.8% | $69,371 | 52.7 | 2.6% | 17,262 |
| Polk | Whole | 45,803 | +1.8% | $77,219 | 46.7 | 3.0% | 15,663 |
| Price | Whole | 13,988 | -0.5% | $60,546 | 52.6 | 3.3% | 4,702 |
| Rusk | Whole | 14,146 | -0.2% | $59,944 | 49.2 | 3.5% | 4,396 |
| Sawyer | Whole | 18,846 | +4.2% | $60,801 | 52.8 | 3.2% | 7,329 |
| St. Croix | Whole | 98,276 | +5.1% | $103,046 | 40.4 | 2.8% | 37,379 |
| Taylor | Whole | 20,118 | +1.0% | $69,350 | 44.2 | 2.5% | 7,776 |
| Vilas | Whole | 23,761 | +3.1% | $68,431 | 55.7 | 3.0% | 8,411 |
| Washburn | Whole | 17,087 | +2.8% | $63,441 | 52.7 | 3.2% | 5,459 |
| Wood | Part (41% of people) | 74,060 | -0.2% | $67,989 | 43.8 | 2.9% | 35,407 |

Whole-county figures. Population: Census Bureau estimates. Income and age: American Community Survey 5-year estimates. Unemployment: BLS, latest month, not seasonally adjusted. Jobs: BLS QCEW annual average, counted where people work.

</details>

## ✅ How every number is checked

```mermaid
flowchart LR
  subgraph S["Primary sources"]
    direction TB
    C["U.S. Census Bureau<br/>boundaries · ACS · estimates"]
    B["Bureau of Labor Statistics<br/>LAUS · QCEW"]
    U["USAspending.gov"]
    H["Clerk of the House<br/>members · roll calls"]
    M["MIT Election Lab ·<br/>FEC certified results"]
    F["Federal Election<br/>Commission"]
    L["congress-legislators"]
  end
  S --> P["Pipeline<br/>fetch · record provenance<br/>verify Census labels"]
  P --> X{"Cross-checks<br/>source vs. source"}
  X -->|pass| D[("data/ JSON + CSV<br/>with citations")]
  X -->|fail or review| I["Integrity report<br/>flags it in public"]
  D --> W["Website<br/>GitHub Pages"]
  D --> R["README charts<br/>light and dark SVG"]
```

Three rules keep the atlas honest:

1. **Two sources or a recorded fact, every time it matters.** The county list is checked against the recorded 26 counties; the 2020 population must agree three ways; the sitting member must be the same in the volunteer-maintained record and in the Clerk's; the most recent election winner must be the member who took office after it.
2. **A label check before any Census number is used.** Every Census variable's official label is compared with what the atlas says it means. If a table is renumbered, that measure is dropped and the check fails in public.
3. **Nothing unofficial without a label and a review date.** Hand-written notes (like a race called by news organizations before certification) carry sources, a verification date, and a review-by date; an overdue note turns the check yellow.

**Latest build: 21 of 21 checks passing**.

| | Check | What was compared |
|---|---|---|
| ✅ Pass | Every Census variable means what the atlas says it means | 210 of 210 variable labels matched the Census Bureau's official definitions for ACS 2025 1-year and ACS 2024 5-year. Education rows were chosen by label (found). |
| ✅ Pass | IRS variables match their published descriptions | 6 of 6 variables confirmed against the tax year 2023 documentation guide and within plausible range. |
| ✅ Pass | IRS income classes add up to the district total | Total tax liability: published total $3,612,071,000; sum of income classes $3,612,071,000 (tolerance 1%; the IRS rounds and suppresses small cells). |
| ✅ Pass | Wisconsin's districts add up to the state total in the IRS file | Returns: state row 2,944,320; sum of 8 districts 2,944,320 (tolerance 2%; returns the IRS could not place in a district are counted only in the state row). |
| ✅ Pass | IRS file uses the current district lines | The tax year 2023 documentation names the 118th Congress; this atlas uses the 119th. Wisconsin's lines have not changed since the 118th Congress. |
| ✅ Pass | Two election compilations agree on the same race | 2018 general election: MIT Election Lab has Sean P. Duffy with 194,061 votes; the FEC compilation has Sean P. Duffy with 194,061 votes (tolerance 0.2%). |
| ✅ Pass | The district's counties match the recorded list (26 counties: 21 whole, 5 split) | Census relationship file: 26 counties with land in the district, 21 whole; split: Chippewa, Jackson, Juneau, Monroe, Wood. Recorded: 26 counties, 21 whole; split: Chippewa, Jackson, Juneau, Monroe, Wood. |
| ✅ Pass | 2020 Census population agrees three ways (district total, sum of county parts, recorded figure) | District total 736,715; sum of county parts 736,715; recorded 736,715. |
| ✅ Pass | For whole counties, two Census files report the same 2020 population | 21 of 21 whole counties match between the 119th District Summary File and the 2020 redistricting file. |
| ✅ Pass | Land area agrees between the boundary file, the relationship file, and the recorded figure | Boundary file 23,111 sq mi; relationship file 23,111 sq mi; Gazetteer 23,111 sq mi; recorded 23,111 sq mi (tolerance 0.5% between Census files, 1% against the recorded figure). |
| ✅ Pass | The district holds about one-eighth of Wisconsin's people, as its eight equal districts should | ACS 2025 1-year: district 12.6% of the state (expected 11.5% to 13.5%). |
| ✅ Pass | County population estimates start from the 2020 Census counts | 26 counties compared; largest gap between the estimates base and the census count is 0.08% (Clark). Tolerance 1%. |
| ✅ Pass | Two independent records name the same sitting member | congress-legislators: Thomas P. Tiffany (T000165); Clerk of the House: Thomas P. Tiffany (T000165). |
| ✅ Pass | The most recent election winner in the results file is the member who took office after it | FEC certified results: Tom Tiffany won in 2022. congress-legislators: term starting 2023-01-03 held by Thomas P. Tiffany. |
| ✅ Pass | Two USAspending endpoints report the same district total for the last full fiscal year | FY2026: spending over time $5,736,701,212; spending by geography $5,736,701,212 (tolerance 1%). |
| ✅ Pass | No House roll call is missing from the vote record | 689 roll calls read for the 119th Congress; none missing. |
| ✅ Pass | Every county has unemployment data through the same latest month | County data through 2026-09. All counties current. National data run through 2026-10; the atlas compares counties, Wisconsin, and the nation in the same month. |
| ✅ Pass | The sitting member's campaign appears in FEC records for the election they won | 3 candidates with financial activity in the 2022 cycle; found Tiffany. |
| ✅ Pass | Curated note reviewed on schedule: 2026 general election | Status unofficial; verified 2026-11-20; review by 2026-12-02. |
| ✅ Pass | Curated note reviewed on schedule: Change of member on January 3, 2027 | Status scheduled; verified 2026-11-20; review by 2027-01-04. |
| ✅ Pass | Curated note reviewed on schedule: Same lines for the 118th and 119th Congresses | Status verified; verified 2026-11-20; review by 2027-06-30. |

<details>
<summary><b>What a receipt looks like</b></summary>

Every data file wraps its numbers with the sources used to make them:

```json
{
  "generated_at": "2026-11-24T04:56:26+00:00",
  "sources": [
    {
      "id": "acs1",
      "publisher": "U.S. Census Bureau",
      "title": "American Community Survey 1-year estimates, 2025: Detailed tables",
      "url": "https://api.census.gov/data/2025/acs/acs1",
      "year": "2026",
      "kind": "Data set",
      "query": "https://api.census.gov/data/2025/acs/acs1?get=...&for=congressional district:07&in=state:55",
      "vintage": "ACS 2025 1-year",
      "accessed": "2026-11-24",
      "apa": "U.S. Census Bureau. (2026). American Community Survey 1-year estimates, 2025: Detailed tables [Data set]. Retrieved November 24, 2026, from https://api.census.gov/data/2025/acs/acs1"
    }
  ],
  "data": {
    "...": "numbers"
  }
}
```

</details>

## ♻️ Reuse it for another district

The whole atlas is driven by one small file. Copy [`config/districts/wi-07.yaml`](config/districts/wi-07.yaml), change the identifiers, and build:

```yaml
id: mn-08
name: Minnesota's 8th Congressional District
short_name: MN-8
state: { name: Minnesota, abbr: MN, fips: "27" }
district: "08"
district_number: 8
congress: 119
```

```bash
python -m pipeline all --district mn-08
```

The pipeline, the checks, the charts, and the website read everything district-specific from that file.

## 🛠 Run it yourself

```bash
git clone https://github.com/tjnorman/wi7-atlas.git && cd wi7-atlas
pip install -r requirements.txt && npm install  # Python pipeline, mapshaper for the map
python -m pipeline all                           # fetch, check, chart, and write README.md
python -m http.server -d site 8000               # then open http://localhost:8000
python -m pytest                                 # unit tests and site checks
```

Optional free API keys raise rate limits: `CENSUS_API_KEY`, `BLS_API_KEY`, `FEC_API_KEY` (from api.data.gov). Without them the pipeline uses the public limits.

<details>
<summary><b>Repository layout</b></summary>

```
config/districts/      one YAML file per district
pipeline/              Python: sources/, checks.py, charts.py, readme.py
data/<district>/       JSON outputs with citations, plus geo/ TopoJSON
data/curated/          hand-written notes, each with sources and a review date
site/                  the website (plain HTML, CSS, and ES modules; no build step)
tools/                 screenshots, video, and GIF rendering
tests/                 pytest unit tests and Playwright site checks
.github/workflows/     tests, weekly data refresh, Pages deploy, media
```

</details>

## 🤝 Principles

- **Nonpartisan.** The atlas follows the seat, not any officeholder or party. It describes votes, money, and public data, not personalities. Party colors appear only on election charts.
- **Primary sources.** Census Bureau, Bureau of Labor Statistics, USAspending.gov, the Clerk of the House, the Federal Election Commission (campaign finance and certified election results), and the MIT Election Data and Science Lab, which compiles official state results.
- **Labels over guesses.** Unofficial results are labeled until certified, estimates carry their margins of error, and split counties are never counted as whole.
- **Open by default.** Code, data, and the method are public. Corrections are welcome as GitHub issues.

## 📚 Sources

- Brennan Center for Justice. (2026, August 3). Wisconsin election certification processes and guardrails.
- Federal Election Commission. (2023). Federal Elections: Election results for the U.S. Senate and the U.S. House of Representatives (2018, 2020, 2022) [Data set]. Retrieved November 24, 2026, from https://www.fec.gov/introduction-campaign-finance/election-results-and-voting-information/
- Federal Election Commission. (2026). Candidate financial totals, U.S. House [Data set]. Retrieved November 24, 2026, from https://www.fec.gov/data/elections/house/WI/07/2026/
- Internal Revenue Service, Statistics of Income Division. (2026). Individual income tax returns: Congressional district data, tax year 2023 [Data set]. Retrieved November 24, 2026, from https://www.irs.gov/statistics/soi-tax-stats-data-by-congressional-district-2023
- MIT Election Data and Science Lab. (2019). U.S. House 1976-2018 (constituency returns) [Data set]. Retrieved November 24, 2026, from https://github.com/MEDSL/constituency-returns
- Office of the Clerk, U.S. House of Representatives. (2026). Member data (XML) [Data set]. Retrieved November 24, 2026, from https://clerk.house.gov/xml/lists/MemberData.xml
- Office of the Clerk, U.S. House of Representatives. (2026). Roll call votes, 119th Congress [Data set]. Retrieved November 24, 2026, from https://clerk.house.gov/Votes
- The @unitedstates project. (2026). congress-legislators: Members of the United States Congress, 1789 to present [Data set]. Retrieved November 24, 2026, from https://github.com/unitedstates/congress-legislators
- U.S. Bureau of Labor Statistics. (2026). Local Area Unemployment Statistics: county, state, and national unemployment rates, not seasonally adjusted [Data set]. Retrieved November 24, 2026, from https://www.bls.gov/lau/
- U.S. Bureau of Labor Statistics. (2026). Quarterly Census of Employment and Wages: 2025 annual averages by county [Data set]. Retrieved November 24, 2026, from https://www.bls.gov/cew/
- U.S. Census Bureau. (2021). 2020 Census redistricting data (Public Law 94-171) [Data set]. Retrieved November 24, 2026, from https://api.census.gov/data/2020/dec/pl
- U.S. Census Bureau. (2024). 119th Congressional District to 2020 county relationship file (Wisconsin) [Data set]. Retrieved November 24, 2026, from https://www.census.gov/geographies/reference-files/time-series/geo/relationship-files.2020.html
- U.S. Census Bureau. (2024). 2024 Gazetteer files: 119th congressional districts [Data set]. Retrieved November 24, 2026, from https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html
- U.S. Census Bureau. (2025). 119th Congress block equivalency files.
- U.S. Census Bureau. (2025). 2020 Census 119th Congressional District Summary File [Data set]. Retrieved November 24, 2026, from https://api.census.gov/data/2020/dec/cd119
- U.S. Census Bureau. (2025). 2025 cartographic boundary files, 1:500,000: 119th congressional districts, county within 119th congressional district, counties, and states [Data set]. Retrieved November 24, 2026, from https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html
- U.S. Census Bureau. (2025). American Community Survey 5-year estimates, 2020-2024: Detailed tables [Data set]. Retrieved November 24, 2026, from https://api.census.gov/data/2024/acs/acs5
- U.S. Census Bureau. (2026). American Community Survey 1-year estimates, 2025: Detailed tables [Data set]. Retrieved November 24, 2026, from https://api.census.gov/data/2025/acs/acs1
- U.S. Census Bureau. (2026). County population totals and components of change: April 1, 2020 to July 1, 2025 (Vintage 2025) [Data set]. Retrieved November 24, 2026, from https://www.census.gov/programs-surveys/popest/data/tables.html
- U.S. Const. amend. XX, § 1.
- U.S. Department of the Treasury, Bureau of the Fiscal Service. (2026). USAspending.gov award obligations by place of performance [Data set]. Retrieved November 24, 2026, from https://www.usaspending.gov/search
- Wis. Stat. § 7.70 (2025). State canvass.
- Wisconsin Public Radio. (2026, November 4). Republican Michael Alfonso wins northern Wisconsin district.
- Wisconsin Public Radio. (2026, November). Wisconsin congressional election results, November 2026.

## ℹ️ About

Published by **Thomas J. Norman** as an independent civic resource. Not affiliated with any candidate, party, campaign, or government office. Companion site: [widistrict7.com](https://widistrict7.com/).

Design inspired by the [Global Intelligence Atlas](https://github.com/Normansrule/global-intelligence-atlas). Built with plain HTML, CSS, and JavaScript, [D3](https://d3js.org/), and [mapshaper](https://github.com/mbloch/mapshaper).

Code: MIT License. Text and charts: CC BY 4.0. Federal data are in the public domain; see each source's terms.

<sub>README generated November 23, 2026 from the data in this repository by <code>python -m pipeline readme</code>. Do not edit README.md by hand; edit <code>docs/README.template.md</code>.</sub>
