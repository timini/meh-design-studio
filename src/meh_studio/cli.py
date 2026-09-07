"""Small headless interface for contracts, private catalogue and reference data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys

from .catalogue import Catalogue
from .domain import DesignBrief, DriverRevision
from .references import cavity_modes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="meh", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    brief = commands.add_parser("validate-brief", help="validate a versioned SI design brief")
    brief.add_argument("path", type=Path)
    catalogue = commands.add_parser("catalogue", help="manage private user driver imports")
    ops = catalogue.add_subparsers(dest="operation", required=True)
    init = ops.add_parser("init")
    init.add_argument("database", type=Path)
    add = ops.add_parser("add")
    add.add_argument("database", type=Path)
    add.add_argument("record", type=Path)
    show = ops.add_parser("list")
    show.add_argument("database", type=Path)
    ref = commands.add_parser("cavity-reference", help="emit analytic data, not solver validation")
    ref.add_argument("--lengths-m", nargs=3, required=True, type=float)
    ref.add_argument("--max-hz", required=True, type=float)
    ref.add_argument("--sound-speed-m-s", type=float, default=343.0)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-brief":
            record = DesignBrief.model_validate_json(args.path.read_text())
            result = {"valid": True, "brief_hash": record.content_hash,
                      "acoustic_feasibility": "not_evaluated", "brief": record.model_dump(mode="json")}
        elif args.command == "catalogue":
            if args.operation == "init":
                with Catalogue.create(args.database):
                    result = {"created": True, "qualified_bundled_pack": False}
            elif args.operation == "add":
                record = DriverRevision.model_validate_json(args.record.read_text())
                with Catalogue(args.database) as cat:
                    added = cat.add(record)
                result = {"added": added, "record_hash": record.content_hash,
                          "qualification": "user_declared_not_independently_verified"}
            else:
                with Catalogue(args.database, readonly=True) as cat:
                    result = {"drivers": [d.model_dump(mode="json") for d in cat.list()]}
        else:
            result = {"kind": "analytic_reference", "acoustic_solver_executed": False,
                      "lengths_m": args.lengths_m, "max_hz": args.max_hz,
                      "sound_speed_m_s": args.sound_speed_m_s,
                      "modes": cavity_modes(tuple(args.lengths_m), args.max_hz, args.sound_speed_m_s)}
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
