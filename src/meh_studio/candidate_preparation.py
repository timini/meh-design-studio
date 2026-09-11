"""Isolate CAD/meshing failures from the parent evolutionary search."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

# The parent executes this exact trusted helper with isolated Python. Use the
# same source tree even when the application is running from a frozen checkout.
if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meh_studio.boundary_lab import BoundaryLabRuntime, _execute, _read_json, _write_json, sha256, _preparation_process_group
from meh_studio.geometry_worker import geometry_runtime


def _identity():
    return json.loads(json.dumps(geometry_runtime()))


def _command(request, root):
    return [str(Path(sys.executable).absolute()), '-I', str(Path(__file__).resolve()),
            '--request', str(request), '--output', str(root)]


def prepare_candidate(candidate, root, runtime, brief, *, timeout_s):
    """Return only after the child has published matching, hashed preparation."""
    root = Path(root).resolve()
    request_path = root / 'preparation-request.json'
    child_report = root / 'preparation-child.json'
    report_path = root / 'preparation.json'
    if any(path.exists() for path in (request_path, child_report, report_path)):
        raise FileExistsError('candidate preparation must use a new attempt directory')
    started = time.monotonic()
    request = {'candidate': _read_json(root / 'candidate.json'),
               'candidate_sha256': sha256(root / 'candidate.json'),
               'brief': brief.model_dump(mode='json'), 'application_runtime': _identity(),
               'runtime': {'checkout': str(Path(runtime.checkout).resolve()),
                           'python': str(Path(runtime.python).absolute()),
                           'julia': str(Path(runtime.julia).absolute()),
                           'backend': runtime.backend, 'julia_threads': runtime.julia_threads},
               'native_runtime': runtime.verify()}
    # The saved candidate is also used by replay and exports; bind it here.
    from meh_studio.optimisation import candidate_record
    if request['candidate'] != candidate_record(candidate):
        raise ValueError('preparation candidate differs from the saved search input')
    _write_json(request_path, request)
    digest = sha256(request_path)
    report = {'status': 'running', 'request_sha256': digest, 'isolated_process': True}
    _write_json(report_path, report)
    try:
        _execute(_command(request_path, root), root, root / 'preparation.log', timeout_s,
                 process_name='Candidate preparation')
        result = _read_json(child_report)
        if (result.get('status') != 'complete' or result.get('request_sha256') != digest
                or sha256(request_path) != digest or _identity() != request['application_runtime']
                or runtime.verify() != request['native_runtime']):
            raise ValueError('candidate preparation identity changed or is incomplete')
        verify_prepared_files(root, result['files_sha256'])
        report.update(status='complete', child_report_sha256=sha256(child_report),
                      files_sha256=result['files_sha256'])
    except BaseException as exc:
        report.update(status='cancelled' if isinstance(exc, KeyboardInterrupt) else 'failed',
                      error=f'{type(exc).__name__}: {exc}')
        if child_report.exists():
            report['child_report_sha256'] = sha256(child_report)
        raise
    finally:
        report['wall_elapsed_s'] = time.monotonic() - started
        _write_json(report_path, report)
    return report


def prepared_files(root):
    files = [root / 'candidate.json']
    if (root / 'build-cost.json').exists():
        files.append(root / 'build-cost.json')
    for name in ('geometry', 'system'):
        files.extend(path for path in (root / name).rglob('*') if path.is_file())
    if any(path.is_symlink() for path in files):
        raise ValueError('prepared artifacts cannot be symlinks')
    return {path.relative_to(root).as_posix(): sha256(path) for path in sorted(files)}


def verify_prepared_files(root, expected):
    if prepared_files(root) != expected:
        raise ValueError('prepared candidate artifacts changed after child completion')
    for name in ('geometry/geometry.json', 'geometry/analysis/mesh.json', 'system/compilation.json'):
        if name not in expected or _read_json(root / name).get('status') != 'complete':
            raise ValueError('child did not complete CAD, meshes and coupled compilation')
    if 'system/project.blab.json' not in expected:
        raise ValueError('child did not produce the coupled solver project')


def prepare_in_process(candidate, root, runtime, brief):
    """Executed only in the disposable child; keep budget checks before meshing."""
    from meh_studio.geometry import export_geometry, mesh_geometry
    from meh_studio.build_cost import estimate_build_cost
    from meh_studio.radiating_system import compile_radiating_system
    export_geometry(candidate['design'], root / 'geometry')
    if brief.build_budget is not None:
        estimate = estimate_build_cost(brief.build_budget, _read_json(root / 'geometry/geometry.json'), candidate['cost'])
        _write_json(root / 'build-cost.json', estimate)
        if not estimate['within_budget']:
            raise ValueError('candidate exceeds declared total build budget')
    mesh_geometry(root / 'geometry')
    options = {}
    if brief.acoustic_objectives is not None:
        options['observation_distance_m'] = brief.acoustic_objectives.observation_distance_m
        if brief.acoustic_objectives.sphere is not None:
            options['sphere_angle_deg'] = brief.acoustic_objectives.sphere.angle_precision_deg
    compile_radiating_system(root / 'geometry', candidate['sources'], root / 'system', runtime,
                             exterior_mesh_size_m=brief.exterior_mesh_size_m, **options)


def run_child(request_path, root):
    from meh_studio.geometry import HornGeometry
    from meh_studio.generated_system import HornSources
    from meh_studio.optimisation import SearchBrief
    from meh_studio.domain import DriverRevision
    digest = sha256(request_path)
    report = {'status': 'running', 'request_sha256': digest}
    try:
        request = _read_json(request_path)
        if _identity() != request['application_runtime']:
            raise ValueError('candidate child imports a different application runtime')
        runtime = BoundaryLabRuntime(**{key: Path(value) if key in ('checkout', 'python', 'julia') else value
                                       for key, value in request['runtime'].items()})
        if runtime.verify() != request['native_runtime']:
            raise ValueError('candidate child uses a different native runtime')
        saved = request['candidate']
        if (sha256(root / 'candidate.json') != request['candidate_sha256']
                or _read_json(root / 'candidate.json') != saved):
            raise ValueError('candidate changed before child preparation')
        candidate = {'design': HornGeometry.model_validate(saved['design']),
                     'sources': HornSources.model_validate(saved['sources']), 'cost': saved['driver_cost'],
                     'drivers': [DriverRevision.model_validate(value) for value in saved['driver_revisions']]}
        with _preparation_process_group():
            prepare_in_process(candidate, root, runtime, SearchBrief.model_validate(request['brief']))
        if (sha256(request_path) != digest or _identity() != request['application_runtime']
                or runtime.verify() != request['native_runtime']):
            raise ValueError('candidate child inputs or runtime changed during preparation')
        files = prepared_files(root)
        verify_prepared_files(root, files)
        report.update(status='complete', files_sha256=files)
    except BaseException as exc:
        report.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        _write_json(root / 'preparation-child.json', report)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    run_child(args.request, args.output)
