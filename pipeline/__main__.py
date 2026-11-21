"""Command line: python -m pipeline <command> [--district wi-07]

  build    fetch every source, run the cross-checks, write data/<district>/
  checks   re-run the cross-checks on the data already on disk
  charts   draw the README charts from the data on disk
  readme   render README.md from docs/README.template.md
  all      build, charts, and readme
"""

from __future__ import annotations

import argparse
import sys

from . import config


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pipeline")
    p.add_argument("command", choices=["build", "checks", "charts", "readme", "all"])
    p.add_argument("--district", default="wi-07")
    p.add_argument("--only", help="comma-separated sources to run, e.g. acs,laus")
    p.add_argument("--strict", action="store_true", help="exit non-zero if any integrity check fails")
    args = p.parse_args(argv)
    d = config.load(args.district)
    only = args.only.split(",") if args.only else None
    status = 0
    if args.command in ("build", "all"):
        from . import build
        print(f"Building {d.name}")
        result = build.run(d, only)
        if args.strict and not result["integrity"]["summary"]["ok"]:
            status = 1
    if args.command == "checks":
        from . import build, checks
        out = build.data_dir(d)
        data = {n: build.load_json(out / f"{n}.json") for n in build.ORDER}
        prev = build.load_json(out / "integrity.json") or {}
        extra = [c for c in prev.get("checks", []) if c["id"] == "acs-labels"]
        res = checks.run(d, data, build.load_notes(), extra)
        for c in res:
            print(f"  {c['status']:5}  {c['title']}")
        if args.strict and any(c["status"] == "fail" for c in res):
            status = 1
    if args.command in ("charts", "all"):
        from . import charts
        charts.render_all(d)
    if args.command in ("readme", "all"):
        from . import readme
        readme.render(d)
    return status


if __name__ == "__main__":
    sys.exit(main())
