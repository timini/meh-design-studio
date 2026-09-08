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


def test_unsupported_claimed_spec_fails_immediately(tmp_path):
    from meh_studio.jobs import JobSpec
    with JobQueue.create(tmp_path/'jobs.sqlite',tmp_path/'artifacts') as queue:
        job=queue.enqueue(JobSpec(kind='geometry',input_digest='0'*64,parameters_json='{"unsupported":true}'))
        lease=queue.claim('test')
        run_geometry(queue,lease,tmp_path/'missing')
        assert queue.get(job)['status']=='failed'
        assert 'unsupported geometry worker job' in queue.get(job)['error']
        assert not lease.output_directory.exists()


def _fake_export(design,directory):
    from meh_studio.geometry import HornGeometry
    root=Path(directory)/'geometry';root.mkdir()
    (root/'part.stl').write_bytes(b'synthetic publication fixture')
    (root/'geometry.json').write_text(json.dumps({'status':'complete','design_hash':HornGeometry.model_validate_json(design).content_hash}))


def test_lease_renewed_during_inventory_and_queue_verification(tmp_path,monkeypatch):
    import meh_studio.geometry_worker as worker
    import meh_studio.jobs as jobs
    queue,job,lease=setup_job(tmp_path)
    clock=[time.time()];queue.clock=lambda:clock[0]
    monkeypatch.setattr(worker,'_export',_fake_export)
    original=jobs.file_digest
    calls=[]
    def slow_hash(path,**kwargs):
        # Each hash advances near the lease expiry, then permits the independent
        # renewal connection to extend it. Repeated hashes exceed the initial
        # publication lease without spending a minute in the test suite.
        before=queue.get(job)['deadline']
        clock[0]=before-1
        deadline=time.monotonic()+3
        while queue.get(job)['deadline']<=before:
            assert time.monotonic()<deadline,'lease was not renewed while hashing'
            time.sleep(.02)
        calls.append(str(path))
        return original(path,**kwargs)
    monkeypatch.setattr(worker,'file_digest',slow_hash)
    monkeypatch.setattr(jobs,'file_digest',slow_hash)
    with queue:
        run_geometry(queue,lease,tmp_path/'snapshot')
        assert queue.get(job)['status']=='succeeded',queue.get(job)['error']
        assert len(calls)>=4


@pytest.mark.parametrize('timeout',[0,-1,True,float('nan'),3601])
def test_invalid_timeout_fails_claimed_job(tmp_path,timeout):
    queue,job,lease=setup_job(tmp_path)
    with queue:
        run_geometry(queue,lease,tmp_path/'snapshot',timeout_s=timeout)
        assert queue.get(job)['status']=='failed'
        assert 'timeout' in queue.get(job)['error']
        assert not lease.output_directory.exists()


def test_oversized_design_rejected_without_reading_contents(tmp_path,monkeypatch):
    from meh_studio.snapshots import InputSnapshot,SnapshotFile
    snapshot=InputSnapshot(files=(SnapshotFile(name='design',size_bytes=2*1024*1024,sha256='0'*64),))
    directory=tmp_path/'snapshot';directory.mkdir()
    (directory/'manifest.json').write_text(snapshot.canonical_json())
    # The absent file must not be opened; the bounded manifest suffices to reject.
    with JobQueue.create(tmp_path/'jobs.sqlite',tmp_path/'artifacts') as queue:
        job=queue.enqueue(geometry_spec(snapshot.content_hash));lease=queue.claim('test')
        run_geometry(queue,lease,directory)
        assert 'design exceeds 1 MiB' in queue.get(job)['error']


@pytest.mark.parametrize('during_queue',[False,True])
def test_cancellation_interrupts_publication_hashing(tmp_path,monkeypatch,during_queue):
    import meh_studio.geometry_worker as worker
    import meh_studio.jobs as jobs
    queue,job,lease=setup_job(tmp_path)
    monkeypatch.setattr(worker,'_export',_fake_export)
    original=jobs.file_digest
    reached=[]
    def cancelled_hash(path,*,check=None):
        with JobQueue(tmp_path/'jobs.sqlite') as other:other.cancel(job)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            try:check()
            except RuntimeError:
                reached.append(True)
                raise
            time.sleep(.02)
        pytest.fail('publication did not observe cancellation')
    monkeypatch.setattr(jobs if during_queue else worker,'file_digest',cancelled_hash)
    with queue:
        run_geometry(queue,lease,tmp_path/'snapshot')
        assert reached
        assert queue.get(job)['status']=='cancelled'
        with pytest.raises(ValueError):queue.result(job)
