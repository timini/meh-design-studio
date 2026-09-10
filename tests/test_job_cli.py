import json
from pathlib import Path

import pytest

from meh_studio.cli import main
from meh_studio.jobs import JobQueue, JobSpec

EXAMPLE = Path(__file__).resolve().parents[1] / 'examples/compact-three-driver-geometry.json'


def invoke(capsys, *args, code=0):
    assert main(['jobs', *map(str, args)]) == code
    captured = capsys.readouterr()
    return json.loads(captured.err if code == 2 else captured.out)


def submit(tmp_path, capsys):
    database = tmp_path / 'jobs.sqlite'
    invoke(capsys, 'init', database, '--artifacts', tmp_path / 'artifacts')
    result = invoke(capsys, 'submit-geometry', database, EXAMPLE)
    return database, result['job_id']


def test_submit_deduplicates_and_freezes_validated_inputs(tmp_path, capsys):
    database, job = submit(tmp_path, capsys)
    source = tmp_path / 'design.json'
    source.write_text(EXAMPLE.read_text(), encoding='utf-8')
    assert invoke(capsys, 'submit-geometry', database, source)['job_id'] == job
    source.write_text('{}')
    assert 'error' in invoke(capsys, 'submit-geometry', database, source, code=2)
    with JobQueue(database) as queue:
        spec = JobSpec.model_validate_json(queue.get(job)['spec'])
        frozen = queue.artifact_root / 'inputs' / spec.input_digest / 'input-design.bin'
        from meh_studio.geometry import HornGeometry
        assert HornGeometry.model_validate_json(frozen.read_bytes()) == HornGeometry.model_validate_json(EXAMPLE.read_bytes())
        frozen.write_text('{}')
    assert 'integrity' in invoke(capsys, 'submit-geometry', database, EXAMPLE, code=2)['error']


def test_cancel_retry_and_no_unverified_result(tmp_path, capsys):
    database, job = submit(tmp_path, capsys)
    assert invoke(capsys, 'status', database, job)['result_integrity'] == 'not_checked'
    assert 'error' in invoke(capsys, 'result', database, job, code=2)
    assert invoke(capsys, 'cancel', database, job)['status'] == 'cancelled'
    assert invoke(capsys, 'run-geometry', database)['status'] == 'idle'
    assert invoke(capsys, 'retry', database, job)['status'] == 'queued'
    assert invoke(capsys, 'recover', database)['recovered'] == 0
    assert 'error' in invoke(capsys, 'status', database, 'missing', code=2)


def test_worker_skips_other_job_kinds_and_rejects_bad_timeout_before_claim(tmp_path, capsys):
    database, job = submit(tmp_path, capsys)
    with JobQueue(database) as queue:
        other = queue.enqueue(JobSpec(kind='solve', input_digest='a'*64, parameters_json='{}'))
    invoke(capsys, 'run-geometry', database, '--timeout-s', 'nan', code=2)
    assert invoke(capsys, 'status', database, job)['attempt'] == 0
    invoke(capsys, 'cancel', database, job)
    assert invoke(capsys, 'run-geometry', database)['status'] == 'idle'
    assert invoke(capsys, 'status', database, other)['status'] == 'queued'
    with JobQueue(database) as queue:
        assert queue.claim('unfiltered').job_id == other


def test_corrupt_input_reports_failed_exit(tmp_path, capsys):
    database, job = submit(tmp_path, capsys)
    with JobQueue(database) as queue:
        spec = JobSpec.model_validate_json(queue.get(job)['spec'])
        (queue.artifact_root / 'inputs' / spec.input_digest / 'input-design.bin').write_text('{}')
    result = invoke(capsys, 'run-geometry', database, code=1)
    assert result['status'] == 'failed'
    assert 'integrity' in result['error']


@pytest.mark.cad
def test_real_cli_spawn_export_and_result_corruption(tmp_path, capsys):
    pytest.importorskip('cadquery')
    database, job = submit(tmp_path, capsys)
    result = invoke(capsys, 'run-geometry', database)
    assert result['status'] == 'succeeded'
    result = invoke(capsys, 'result', database, job)
    assert result['result_integrity'] == 'verified'
    assert result['completion']['evidence'] == 'experimental_geometry'
    stl = next(item for item in result['completion']['files'] if item['path'].endswith('.stl'))
    path = Path(result['directory']) / stl['path']
    assert path.stat().st_size > 100
    path.write_bytes(b'corrupted')
    assert invoke(capsys, 'status', database, job)['status'] == 'succeeded'
    assert 'integrity' in invoke(capsys, 'result', database, job, code=2)['error']
