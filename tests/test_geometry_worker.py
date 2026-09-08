import json
from pathlib import Path
import time

import pytest

from meh_studio.jobs import JobQueue
from meh_studio.snapshots import capture_inputs
from meh_studio.geometry_worker import geometry_spec,run_geometry


def setup_job(tmp_path):
    source=Path(__file__).resolve().parents[1]/'examples/three-driver-geometry.json'
    snapshot=capture_inputs({'design':source},tmp_path/'snapshot')
    queue=JobQueue.create(tmp_path/'jobs.sqlite',tmp_path/'artifacts')
    job=queue.enqueue(geometry_spec(snapshot.content_hash))
    lease=queue.claim('test')
    return queue,job,lease


def _crash(design,directory):
    raise RuntimeError('synthetic worker crash')


def _slow(design,directory):
    time.sleep(10)


def test_cancel_before_launch(tmp_path):
    queue,job,lease=setup_job(tmp_path)
    with queue:
        queue.cancel(job)
        run_geometry(queue,lease,tmp_path/'snapshot')
        assert queue.get(job)['status']=='cancelled'
        assert not lease.output_directory.exists()


def test_changed_input_fails_before_launch(tmp_path):
    queue,job,lease=setup_job(tmp_path)
    with queue:
        (tmp_path/'snapshot/input-design.bin').write_bytes(b'changed')
        run_geometry(queue,lease,tmp_path/'snapshot')
        assert queue.get(job)['status']=='failed'
        assert not lease.output_directory.exists()


def test_child_crash_fails_without_completion(tmp_path,monkeypatch):
    import meh_studio.geometry_worker as module
    queue,job,lease=setup_job(tmp_path)
    monkeypatch.setattr(module,'_export',_crash)
    with queue:
        run_geometry(queue,lease,tmp_path/'snapshot')
        assert queue.get(job)['status']=='failed'
        assert not (lease.output_directory/'completion.json').exists()


def test_timeout_kills_child(tmp_path,monkeypatch):
    import meh_studio.geometry_worker as module
    queue,job,lease=setup_job(tmp_path)
    monkeypatch.setattr(module,'_export',_slow)
    with queue:
        started=time.monotonic()
        run_geometry(queue,lease,tmp_path/'snapshot',timeout_s=.5)
        assert time.monotonic()-started<5
        assert queue.get(job)['status']=='failed'
        assert 'time limit' in queue.get(job)['error']


@pytest.mark.cad
def test_real_geometry_job_publishes_verified_files(tmp_path):
    pytest.importorskip('cadquery')
    queue,job,lease=setup_job(tmp_path)
    with queue:
        run_geometry(queue,lease,tmp_path/'snapshot')
        assert queue.get(job)['status']=='succeeded',queue.get(job)['error']
        result=queue.result(job)
        assert result.evidence=='experimental_geometry'
        assert any(file.path.endswith('.stl') for file in result.files)
        report=json.loads((lease.output_directory/'geometry/geometry.json').read_text())
        assert report['print_verified'] is False


def test_cancellation_during_execution_stops_worker(tmp_path,monkeypatch):
    import threading
    import meh_studio.geometry_worker as module
    queue,job,lease=setup_job(tmp_path)
    monkeypatch.setattr(module,'_export',_slow)
    errors=[]
    def cancel():
        try:
            deadline=time.monotonic()+5
            while not lease.output_directory.exists():
                if time.monotonic()>deadline:raise RuntimeError('worker did not reserve output')
                time.sleep(.02)
            with JobQueue(tmp_path/'jobs.sqlite') as other:other.cancel(job)
        except Exception as exc:errors.append(exc)
    thread=threading.Thread(target=cancel);thread.start()
    with queue:
        run_geometry(queue,lease,tmp_path/'snapshot')
        thread.join(timeout=6)
        assert not thread.is_alive() and not errors
        assert queue.get(job)['status']=='cancelled'
        assert not (lease.output_directory/'completion.json').exists()
