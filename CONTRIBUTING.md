# Contributing

Thank you for helping keep the WI-7 Atlas accurate and useful.

## Corrections come first

If a number, label, or statement looks wrong, open a **Correction** issue with a link to the primary source. Corrections are checked against that source before anything changes, and every accepted correction is noted in [CHANGELOG.md](CHANGELOG.md).

## Ground rules

- **Primary sources only.** New data must come from the publisher (a federal or state agency, the Clerk of the House, the FEC, or an academic archive of official results), never from a news story or a secondary aggregator.
- **Record provenance.** Every source module returns `Source` records (publisher, title, URL, exact query, vintage, retrieval date). The APA citation is generated from them.
- **Cross-check what matters.** If a new number can be compared with an independent source, add a check in `pipeline/checks.py`.
- **Neutral wording.** Describe; do not characterize. Party colors are used only on election charts.
- **Labels over guesses.** Mark estimates, preliminary values, and unofficial results as such.

## Add a data source

1. Create `pipeline/sources/<name>.py` with a `fetch(fetcher, district, ...)` function that returns `(payload, sources, checks)`.
2. Register it in `pipeline/build.py` (`ORDER` and `steps`).
3. Add unit tests in `tests/` using canned responses in the source's real format (see `tests/conftest.py`).
4. Show it on the site (`site/assets/js/app.js`) and, if useful, in the README (`pipeline/readme.py`, `docs/README.template.md`).

## Add a district

Copy `config/districts/wi-07.yaml`, change the identifiers and expectations, and run:

```bash
python -m pipeline all --district <id>
```

## Development

```bash
pip install -r requirements.txt && npm install
python -m pipeline all
python -m pytest
python -m http.server -d site 8000
```

The README is generated: edit `docs/README.template.md`, not `README.md`.
