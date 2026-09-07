"""Experimental geometry export and named acoustic meshing."""
import argparse
import json
from pathlib import Path
import sys

from .geometry import HornGeometry, export_geometry, mesh_geometry


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("design", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mesh", action="store_true")
    args = parser.parse_args(argv)
    try:
        design = HornGeometry.model_validate_json(args.design.read_text(encoding="utf-8"))
        report = export_geometry(design, args.output)
        if args.mesh:
            report = {"geometry": report, "mesh": mesh_geometry(args.output)}
        print(json.dumps(report, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, ImportError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
