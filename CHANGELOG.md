# Changelog

All notable changes to the WI-7 Atlas. Corrections to data or wording are listed under **Corrections**.

## 1.2.0 — 2026-11-24

### Added
- Bridge update: the Blatnik Bridge replacement between Superior and Duluth, with cost, federal grant, closure, and reopening dates, each read from the Minnesota or Wisconsin transportation department's own page (`data/curated/projects.yaml`). The build fails if a fact has no listed source and warns when the pages are due for re-reading.
- Listening links for radio stations, starting with Wisconsin Public Radio. A link is added only after the broadcaster's own page has been read (`data/curated/station_links.yaml`).

## 1.1.0 — 2026-11-23

### Added
- Social Security and Supplemental Security Income in the district (SSA Congressional Statistics): people receiving benefits and the amount paid in December.
- Radio and television stations transmitting from inside the district (FCC licensing records), and the district's 607 cities, villages, and towns with each one's status relative to the district line (Census relationship file).
- Colleges and universities with their main address in the district, with links, from the NCES IPEDS directory file.
- Ten years of attendance for the seat (2017 forward): roll calls voted and missed by year and by member, a comparison with the whole House, roll calls taken during the vacancy, and a list of every missed vote with links to the Clerk's record.
- "Right now": public road cameras inside the district and a twice-hourly snapshot of aircraft overhead, adapted from the Global Intelligence Atlas with its author's permission.
- `NOTICE.md`: records permission to adapt code from Normansrule/global-intelligence-atlas under this repository's MIT license.
- Federal individual income tax by district, from IRS Statistics of Income congressional district data: returns, adjusted gross income, total tax liability, and per-return comparisons with the state and the United States. Variables are confirmed against the IRS documentation guide before use. The site and README state what the figure leaves out.
- Not published: the IRS file's earned income credit column (A59660), whose tax year 2023 value for the district ($23.0 billion on 38,770 returns) is not plausible. A range test now withholds any such value.
- The website now requests only the datasets the latest build produced.

## 1.0.0 — 2026-11-20

### Added
- Config-driven pipeline for one congressional district (`config/districts/wi-07.yaml`).
- Sources: Census cartographic boundaries, 119th District relationship file and summary file, ACS 1-year and 5-year detailed tables, Population Estimates, BLS LAUS and QCEW, USAspending.gov, congress-legislators, Clerk of the House member data and roll calls, MIT Election Data and Science Lab U.S. House results, and FEC candidate totals.
- Provenance on every dataset (publisher, exact query, vintage, retrieval date) with generated APA citations.
- Census label verification before any ACS value is used.
- Cross-checks between independent sources, published on the site and in the README.
- Curated notes with sources and review-by dates (2026 election status, seat transition, map stability).
- Website: scroll-driven map, comparisons, unemployment, industries, pay, federal dollars, seat history, roll-call participation, election history, campaign finance, county profiles, sources, and method; light and dark appearance; reduced-motion support.
- Generated README with light and dark SVG charts; rendered hero animation and tour video.
- GitHub Actions: tests, weekly data refresh, Pages deploy, monthly media rendering.

### Corrections
- 2026-11-23: District land area. The figure recorded from widistrict7.com (18,787 sq mi) disagreed with three Census Bureau products: the 119th Congress cartographic boundary file, the district-to-county relationship file, and the Gazetteer, which agree on about 23,111 sq mi of land. The atlas uses the Census figure.
- 2026-11-23: Gazetteer citation. The source record gave the current year (2026) as the edition, but the file used is the 2024 Gazetteer. The year and title now come from the file actually downloaded. The land-area value was unaffected. widistrict7.com was corrected to 23,111 sq mi the same day.
- 2026-11-23: Unemployment. BLS county and state series IDs were one digit short, so the first builds had no county or state rates. Fixed before publication.
