"""Small headless interface for contracts, private catalogue and reference data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
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
    solve = commands.add_parser("solve-project", help="run the pinned external Boundary Lab solver")
    solve.add_argument("project", type=Path)
    solve.add_argument("--request", type=Path, required=True)
    solve.add_argument("--checkout", type=Path, required=True)
    solve.add_argument("--python", type=Path, required=True, help="Boundary Lab environment Python")
    solve.add_argument("--julia", type=Path, required=True)
    solve.add_argument("--output", type=Path, required=True, help="new evaluation directory")
    backends = ["beat_cpu", "beat_cuda", "beat_rocm", "coupled_reference"]
    solve.add_argument("--backend", choices=backends, default="beat_cpu")
    solve.add_argument('--julia-threads', type=int)
    solve.add_argument("--timeout-per-stage-s", type=float, default=1800)
    compile_system = commands.add_parser("compile-interior", help="compile experimental generated horn air meshes")
    compile_system.add_argument("geometry", type=Path)
    compile_system.add_argument("--sources", type=Path, required=True)
    compile_system.add_argument("--output", type=Path, required=True)
    validate_basis = commands.add_parser("validate-electrical", help="check full-basis circuit consistency")
    validate_basis.add_argument("project", type=Path)
    validate_basis.add_argument("evaluation", type=Path)
    radiating = commands.add_parser("compile-radiating", help="compile experimental FEM/BEM horn domains")
    radiating.add_argument("geometry", type=Path)
    radiating.add_argument("--sources", type=Path, required=True)
    radiating.add_argument("--output", type=Path, required=True)
    radiating.add_argument("--checkout", type=Path, required=True)
    radiating.add_argument("--python", type=Path, required=True)
    radiating.add_argument("--julia", type=Path, required=True)
    radiating.add_argument("--exterior-mesh-size-m", type=float, default=.02)
    search = commands.add_parser('optimise', help='run experimental bounded FEM/BEM search')
    search.add_argument('brief', type=Path)
    search.add_argument('--geometry', type=Path, required=True)
    search.add_argument('--database', type=Path, required=True)
    search.add_argument('--output', type=Path, required=True)
    search.add_argument('--checkout', type=Path, required=True)
    search.add_argument('--python', type=Path, required=True)
    search.add_argument('--julia', type=Path, required=True)
    search.add_argument('--julia-threads', type=int, help='explicit Julia thread count')
    search.add_argument('--backend', choices=backends, default='beat_cpu')
    search.add_argument('--timeout-per-solver-stage-s',type=float,default=1800)
    resume = commands.add_parser('resume-optimise', help='continue a stopped search in a new directory')
    resume.add_argument('search', type=Path)
    resume.add_argument('--output', type=Path, required=True)
    resume.add_argument('--checkout', type=Path, required=True)
    resume.add_argument('--python', type=Path, required=True)
    resume.add_argument('--julia', type=Path, required=True)
    resume.add_argument('--julia-threads', type=int, help='match the original explicit Julia thread count')
    resume.add_argument('--backend', choices=backends, default='beat_cpu', help='match the original backend')
    bundle = commands.add_parser('export-search', help='export experimental winning geometry, driver BOM and relative gains')
    bundle.add_argument('search', type=Path)
    bundle.add_argument('--output', type=Path, required=True, help='new ZIP file; existing files are never replaced')
    operating = commands.add_parser('operating-report', help='predict frozen-winner pressure, excursion and current at an explicit RMS input')
    operating.add_argument('search', type=Path)
    operating.add_argument('--input-rms-v', type=float, required=True)
    operating.add_argument('--output', type=Path, required=True, help='new JSON report; existing files are never replaced')
    from .job_cli import add_job_commands, execute_job_command
    add_job_commands(commands)
    args = parser.parse_args(argv)
    try:
        if args.command == 'jobs':
            result, code = execute_job_command(args)
            print(json.dumps(result, indent=2, allow_nan=False))
            return code
        elif args.command == 'export-search':
            from .build_bundle import export_search
            result = export_search(args.search, args.output)
        elif args.command == 'operating-report':
            from .operating import search_operating_report
            result = search_operating_report(args.search, args.input_rms_v)
            encoded = json.dumps(result, indent=2, allow_nan=False)
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(encoded+'\n')
        elif args.command == 'resume-optimise':
            from .search_resume import resume_optimise
            from .boundary_lab import BoundaryLabRuntime
            result = resume_optimise(args.search, BoundaryLabRuntime(args.checkout,args.python,args.julia,args.backend,julia_threads=args.julia_threads),args.output)
        elif args.command == 'optimise':
            from .optimisation import SearchBrief, optimise
            from .geometry import HornGeometry
            from .boundary_lab import BoundaryLabRuntime
            result = optimise(SearchBrief.model_validate_json(args.brief.read_text()),
                HornGeometry.model_validate_json(args.geometry.read_text()), args.database,
                BoundaryLabRuntime(args.checkout,args.python,args.julia,args.backend,julia_threads=args.julia_threads),args.output,solver_stage_timeout_s=args.timeout_per_solver_stage_s)
        elif args.command == "compile-radiating":
            from .boundary_lab import BoundaryLabRuntime
            from .generated_system import HornSources
            from .radiating_system import compile_radiating_system
            sources = HornSources.model_validate_json(args.sources.read_text(encoding="utf-8"))
            result = compile_radiating_system(args.geometry, sources, args.output,
                BoundaryLabRuntime(args.checkout, args.python, args.julia),
                exterior_mesh_size_m=args.exterior_mesh_size_m)
        elif args.command == "validate-electrical":
            from .validation import validate_electrical_basis
            result = validate_electrical_basis(args.project, args.evaluation)
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0 if result["passed"] else 1
        elif args.command == "compile-interior":
            from .generated_system import HornSources, compile_interior_system
            sources = HornSources.model_validate_json(args.sources.read_text(encoding="utf-8"))
            result = compile_interior_system(args.geometry, sources, args.output)
        elif args.command == "solve-project":
            from .boundary_lab import BoundaryLabRuntime, SolveRequest
            request = SolveRequest.model_validate_json(args.request.read_text(encoding="utf-8"))
            runtime = BoundaryLabRuntime(args.checkout, args.python, args.julia, args.backend, args.julia_threads)
            result = runtime.solve(args.project, request, args.output, timeout_s=args.timeout_per_stage_s)
        elif args.command == "validate-brief":
            record = DesignBrief.model_validate_json(args.path.read_text(encoding="utf-8"))
            result = {"valid": True, "brief_hash": record.content_hash,
                      "acoustic_feasibility": "not_evaluated", "brief": record.model_dump(mode="json")}
        elif args.command == "catalogue":
            if args.operation == "init":
                with Catalogue.create(args.database):
                    result = {"created": True, "qualified_bundled_pack": False}
            elif args.operation == "add":
                record = DriverRevision.model_validate_json(args.record.read_text(encoding="utf-8"))
                with Catalogue(args.database) as cat:
                    added = cat.add(record)
                result = {"added": added, "record_hash": record.content_hash,
                          "qualification": ("not_qualified" if record.qualification is None
                                            else "user_declared_not_independently_verified")}
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
    except KeyboardInterrupt as exc:
        print(json.dumps({"status":"cancelled", "error":str(exc) or "interrupted"}), file=sys.stderr)
        return 143 if getattr(exc,"signum",None) == 15 else 130
    except (ValueError, OSError, ImportError, sqlite3.Error, subprocess.SubprocessError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
