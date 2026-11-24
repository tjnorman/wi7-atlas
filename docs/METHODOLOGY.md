# Methodology

How the WI-7 Atlas turns public records into the numbers on the site, and how it checks them.

## Geography

- **District boundaries** come from the U.S. Census Bureau's cartographic boundary files (1:500,000) for the 119th Congress. Wisconsin's congressional map is the same for the 118th and 119th Congresses and has been in effect since January 3, 2023.
- **Which counties are in the district** comes from the Census Bureau's 119th Congressional District to 2020 county relationship file. A county counts as part of the district only if it shares land with it; contact across water (Lake Superior) does not count. A county is **whole** when the land inside the district equals the county's land area.
- **Split counties** are drawn from the "county within 119th congressional district" boundary file, so the map shows only the part inside the district. The share of each split county's people living in the district comes from the 2020 Census 119th Congressional District Summary File, tabulated by county part.
- **County statistics** such as income and unemployment always describe the whole county, including any part outside the district, and are labeled that way.

## People and homes

- District, Wisconsin, and U.S. figures use the **American Community Survey (ACS) 1-year estimates**, the most recent available. County figures use **ACS 5-year estimates**, which are more reliable for small counties.
- The atlas reads **detailed tables** (B and C tables), whose variable numbers are stable across years. Before any value is used, the pipeline downloads the official label for every variable and compares it with what the atlas expects it to mean. A mismatch drops the measure and fails a public check.
- ACS figures are estimates from a sample. District figures are shown with **margins of error at 90% confidence** where the Census Bureau publishes them. Small differences may not be meaningful.
- The **district trend** starts in 2022, the first year the ACS used the current district lines. Dollar amounts are in each year's dollars.

## Population change

County populations since 2020 come from the Census Bureau's **Population Estimates Program** (the vintage in the data file). Change is measured from the April 1, 2020 estimates base. Components of change (births, deaths, and migration) are summed over the estimate years.

## Work and pay

- **Unemployment rates** come from the Bureau of Labor Statistics' Local Area Unemployment Statistics, **not seasonally adjusted**, because county rates are published only that way. The state and national lines use the not seasonally adjusted series to match. The latest month is preliminary.
- **Jobs and pay** come from the Quarterly Census of Employment and Wages (QCEW), annual averages for all ownerships. QCEW counts jobs where people work, not where they live.

## Federal dollars

Award obligations come from **USAspending.gov**, filtered by place of performance in the district under current lines. Obligations are commitments to spend and agencies revise them. Payments reported only at the county or state level, such as many benefits paid to individuals, are not included in district totals. County totals describe whole counties.

## Federal income tax

The IRS Statistics of Income Division publishes totals from individual income tax returns (Form 1040) by congressional district. The atlas reports the district's number of returns, adjusted gross income, and total tax liability for the most recent tax year, with the same figures per return for the state and the United States (the sum of the 50 states and the District of Columbia).

- **This is not all federal tax.** Employer payroll taxes, corporate income tax, excise taxes, and estate and gift taxes are not published by congressional district. The atlas does not estimate them.
- **It is not a balance against federal awards.** The tax figure covers one tax year of individual returns; the award figures cover federal fiscal years and only awards reported by place of performance. The atlas shows both and does not subtract one from the other.
- The IRS places returns in districts by the ZIP code on the return, so a small share of returns near district lines may be assigned to a neighboring district.
- The IRS file has no labels. Before a variable is used, its description in the IRS documentation guide for that tax year must contain the expected words (for example, "total tax liability"). A variable that does not match is not published, and the build reports it.
- A value can carry the right label and still be wrong. Any amount larger than half of the district's adjusted gross income is withheld and reported. The earned income credit column in the tax year 2023 file showed $23.0 billion for this district on 38,770 returns, which is not believable, so the atlas does not publish that column.
- Checks: the income classes must add up to the published district total; the state's districts are compared with the state row; and the Congress named in the IRS documentation is compared with the atlas's district lines.

## Colleges and universities

The list comes from the National Center for Education Statistics' IPEDS directory file (HD), which covers every institution that takes part in federal student aid. An institution is listed when its coordinates fall inside the district outline and IPEDS marks it active.

- IPEDS lists an institution once, at its main address. A branch campus or outreach center inside the district that reports under a parent elsewhere is not listed, and an institution whose main address is outside the district is not listed even if it has a campus inside.
- Variable names are confirmed against the IPEDS dictionary, and the words for control, level, and size come from the dictionary's own code lists.
- Check: IPEDS also records a congressional district code for each institution. The build compares that code with the outline and reports any institution where they differ.

## Radio and television

Stations come from the Federal Communications Commission's AM, FM, and TV query tools. A station is listed when it holds a licence (not only a construction permit) and its transmitter coordinates fall inside the district outline. Full-power and low-power FM, AM, and full-power, Class A, and low-power television are included; translators and boosters are not.

- **Licensed here is not the same as received here.** Stations in Duluth, Eau Claire, Green Bay, and the Twin Cities reach parts of the district from transmitters outside it. Reception depends on power, antenna height, and terrain, and the atlas does not model it. A separate short list shows stations licensed to a community in the district whose transmitter stands outside it.
- The FCC output has no column names. Each row must show hemisphere letters and plausible coordinates in the expected positions, or the build stops.
- FCC records change continuously; the list carries its retrieval date.

## Cities, villages, and towns

The Census Bureau's relationship file between the 119th Congress districts and 2020 county subdivisions gives, for every city, village, and town, the land area inside each district. A municipality is *inside* when all of its land is in the district, *split* when the line divides it, and *outside* otherwise; a share under 0.1% is treated as a boundary sliver. The file has no population by part, so "split" describes land, not residents. A municipality that crosses a county line appears once in each county.

## Right now: cameras and aircraft

This section is a window, not a dataset. Nothing in it feeds the figures elsewhere in the atlas.

- **Road cameras.** Locations come from Open Eagle Eye, a volunteer-maintained public registry (MIT licence). The build keeps a camera only if it is inside the district outline, is marked verified, needs no sign-in, uses HTTPS, and its address carries no credentials. The atlas stores the name, position, and address. Images load from the agency that runs the camera and belong to that agency. The registry lists only some of the public cameras in the district.
- **Aircraft.** A scheduled job asks a community flight tracker (adsb.lol first, then adsb.fi, then airplanes.live) for aircraft near the district, keeps those inside the outline, and publishes the result on the repository's `live` branch about twice an hour. The page shows the time of the snapshot and says so when it is old. Positions come from volunteer receivers, which are sparse over the Northwoods, so the count is a floor, not a census.
- Both use the simplified district outline, so something exactly on the line can fall on either side.
- Code for this section is adapted from the Global Intelligence Atlas with its author's permission (`NOTICE.md`).

## The seat

- **Members** come from the public-domain [congress-legislators](https://github.com/unitedstates/congress-legislators) dataset and are cross-checked with the Clerk of the House's member data.
- **Roll-call votes** come from the Clerk's official XML records. Each vote is attributed to whoever held the seat on that date. Agreement rates use only yes-or-no votes; quorum calls and the election of the Speaker are excluded. Definitions:
  - *Votes missed*: share of yes-or-no roll calls recorded as Not Voting.
  - *With own party's majority*: share of the member's yes-or-no votes matching the position taken by most members of the member's party (ties excluded).
  - *On the winning side*: share of the member's yes-or-no votes matching the outcome.
- **Attendance over ten years** reads every roll call from 2017 forward and counts, for each year and each member, the yes-or-no roll calls taken while that member held the seat and how many are recorded as Not Voting. Roll calls taken while the seat was vacant are shown separately and are not counted as missed. The comparison figure is the share of Not Voting records for every House member on the same roll calls. The Clerk's record does not give a reason for an absence, so the atlas does not either.
- **Election results** come from the MIT Election Data and Science Lab's U.S. House dataset, compiled from official state results. General elections only. The most recent election appears after official certification; until then, a dated note labeled *unofficial* describes the status with sources.
- **Campaign finance** comes from the Federal Election Commission's candidate totals for each two-year cycle, through each committee's latest report.

## Cross-checks

Each build runs checks that compare independent sources, listed with results on the site and in the README. A failed check is shown publicly; it is never hidden. Hand-written notes carry a review-by date, and an overdue note is flagged for review.

## What the atlas does not do

It does not rate, endorse, or characterize candidates, officeholders, or parties, and it does not predict elections.
