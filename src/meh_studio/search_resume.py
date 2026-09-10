"""Continue stopped searches while preserving the original evidence and paths."""
from pathlib import Path
import json
import shutil
import tempfile

from .boundary_lab import _read_json, sha256, SolveRequest
from .catalogue import Catalogue
from .domain import DriverRevision
from .geometry import HornGeometry
from .optimisation import SearchBrief, candidate_record, optimise, response_score

CONTROLS = ('brief.json', 'base-geometry.json', 'catalogue-snapshot.json')


def resume_optimise(source, runtime, output):
    try:
        return _resume_optimise(source, runtime, output)
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError('incomplete or invalid recovery record') from exc


def _control(source, name):
    if name == 'catalogue-snapshot.json':
        value = json.loads((source / name).read_text(encoding='utf-8'))
        if not isinstance(value, list):
            raise ValueError('catalogue snapshot must be an array')
        return value
    return _read_json(source / name)


def _resume_optimise(source, runtime, output):
    source = Path(source).absolute()
    saved = _read_json(source / 'search.json')
    brief = SearchBrief.model_validate(_read_json(source / 'brief.json'))
    base = HornGeometry.model_validate(_read_json(source / 'base-geometry.json'))
    drivers = [DriverRevision.model_validate(row) for row in _control(source, 'catalogue-snapshot.json')]
    with tempfile.TemporaryDirectory(prefix='meh-resume-') as temporary:
        database = Path(temporary) / 'catalogue.sqlite'
        with Catalogue.create(database) as catalogue:
            for driver in drivers:
                catalogue.add(driver)
        return optimise(brief, base, database, runtime, output,
                        solver_stage_timeout_s=saved['per_solver_stage_timeout_s'], resume_from=source)


def _inventory(root):
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('recovery trial cannot contain symlinks')
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha256(path)
        elif not path.is_dir():
            raise ValueError('recovery trial must contain regular files')
    return result


class Recovery:
    def __init__(self, source, output, brief, base, drivers, pool, runtime, application, timeout):
        self.source = Path(source).resolve()
        if output.resolve().is_relative_to(self.source):
            raise ValueError('recovery output must be outside the original search')
        self.hashes = {name: sha256(self.source / name) for name in ('search.json', *CONTROLS)}
        saved = _read_json(self.source / 'search.json')
        if saved.get('status') not in ('cancelled', 'failed'):
            raise ValueError('only cancelled or failed searches can be resumed')
        if saved.get('control_sha256') != {name: self.hashes[name] for name in CONTROLS}:
            raise ValueError('recovery search control identity mismatch')
        if saved.get('runtime') != runtime or saved.get('application_runtime') != application:
            raise ValueError('recovery requires the original solver and application runtime; legacy searches cannot resume')
        if saved.get('per_solver_stage_timeout_s') != timeout:
            raise ValueError('recovery timeout differs from original search')
        expected = (brief.model_dump(mode='json'), base.model_dump(mode='json'),
                    [driver.model_dump(mode='json') for driver in drivers])
        if any(_control(self.source, name) != value for name, value in zip(CONTROLS, expected)):
            raise ValueError('recovery inputs differ from original search')
        trials = saved.get('trials')
        if not isinstance(trials, list) or len(trials) > len(pool):
            raise ValueError('invalid recovery trial sequence')
        self.completed = {}
        for i, trial in enumerate(trials):
            if not isinstance(trial, dict) or type(trial.get('index')) is not int or trial.get('index') != i or trial.get('status') not in ('complete','failed','cancelled'):
                raise ValueError('invalid recovery trial sequence')
            if trial['status'] == 'complete':
                self.completed[i] = trial
        self.brief, self.runtime = brief, runtime
        self.provenance = {'source_directory': str(self.source), 'source_sha256': self.hashes,
                           'reused_trial_indices': sorted(self.completed),
                           'mode': 'whole_completed_trials',
                           'original_search_required': True}
        self.check_source()

    def check_source(self):
        if any(sha256(self.source / name) != digest for name, digest in self.hashes.items()):
            raise ValueError('original search changed during recovery')

    def _verify_trial(self, root, candidate, index):
        if _read_json(root / 'candidate.json') != candidate_record(candidate):
            raise ValueError('recovery candidate differs from declared search')
        score = _read_json(root / 'score.json')
        if self.completed[index] != dict(score, index=index, status='complete'):
            raise ValueError('recovery score differs from recorded trial')
        geometry = root / 'geometry/geometry.json'
        if score.get('geometry_manifest_sha256') != sha256(geometry):
            raise ValueError('recovery geometry differs from scored trial')
        manifest = _read_json(geometry)
        if manifest.get('design') != candidate_record(candidate)['design']:
            raise ValueError('recovery geometry design differs')
        from .export_validation import validate_export
        validate_export(geometry.parent)
        evaluation = root / 'evaluation'
        request = SolveRequest(frequencies_hz=self.brief.frequencies_hz,
            include_project_observations=True, retain=('fem_nodal_pressure','bem_boundary_traces'))
        if SolveRequest.model_validate(_read_json(evaluation / 'request.json')) != request:
            raise ValueError('recovery solve request differs from search')
        if _read_json(evaluation / 'evaluation.json')['runtime'] != self.runtime:
            raise ValueError('recovery evaluation runtime differs')
        recomputed = response_score(root / 'system/project.blab.json', evaluation, self.brief.side_gains)
        recomputed.update(objective=recomputed['ripple_db'] + self.brief.cost_weight_db*candidate['cost']/self.brief.max_driver_cost,
                          driver_count=candidate['design'].driver_count, driver_cost=candidate['cost'],
                          evaluation_sha256=sha256(evaluation / 'evaluation.json'),
                          geometry_manifest_sha256=sha256(geometry))
        if recomputed != score:
            raise ValueError('recovery score failed independent recomputation')
        return score

    def copy_trial(self, index, candidate, destination):
        self.check_source()
        root = self.source / f'trial-{index:03d}'
        before = _inventory(root)
        score = self._verify_trial(root, candidate, index)
        shutil.copytree(root, destination)
        if _inventory(root) != before or _inventory(destination) != before:
            raise ValueError('recovery trial changed during copy')
        self._verify_trial(destination, candidate, index)
        self.check_source()
        return score
