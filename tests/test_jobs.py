import json
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from meh_studio.jobs import Artifact, Completion, JobQueue, JobSpec, file_digest


@pytest.fixture
def queue(tmp_path):
    now = [100.]
    with JobQueue.create(tmp_path/'jobs.sqlite',tmp_path/'artifacts',clock=lambda:now[0]) as queue:
        yield queue,now


def spec(**patch):
    return JobSpec.model_validate(dict(kind="solve",input_digest="a"*64,parameters_json='{"frequency":1000}') | patch)


def publish(lease):
    directory = lease.output_directory
    directory.mkdir(parents=True)
    path = directory/'prediction.json'
    path.write_text('{"evidence":"predicted"}')
    record = Completion(job_id=lease.job_id,attempt_token=lease.token,evidence='predicted',
                        files=(Artifact(path=path.name,sha256=file_digest(path),size_bytes=path.stat().st_size),))
    (directory/'completion.json').write_text(record.canonical_json())
    return path


def test_equivalent_input_deduplicates_and_inputs_are_immutable(queue):
    q,_ = queue
    a = q.enqueue(spec())
    b = q.enqueue(JobSpec(kind='solve',input_digest='a'*64,parameters_json='{ "frequency" : 1000 }'))
    assert a == b
    with pytest.raises(ValueError): spec(parameters_json='NaN')
    lease = q.claim('worker')
    assert lease.job_id == a and q.claim('another') is None
    assert q.get(a)['status'] == 'running'


@pytest.mark.parametrize('payload',['[]','{"x":NaN}','{"x":1e999}'])
def test_job_parameters_reject_nonfinite_and_nonobject(payload):
    with pytest.raises(ValueError):
        JobSpec(kind='solve',input_digest='a'*64,parameters_json=payload)


def test_competing_workers_get_only_one_lease(queue):
    q,_ = queue
    job = q.enqueue(spec())
    def claim(i):
        with JobQueue(q.path,clock=lambda:100.) as other:
            return other.claim(str(i))
    with ThreadPoolExecutor(max_workers=8) as pool:
        leases = list(pool.map(claim,range(8)))
    assert sum(lease is not None for lease in leases) == 1
    assert q.get(job)['attempt'] == 1


def test_expiry_recovers_and_fences_late_worker(queue):
    q,now = queue
    job = q.enqueue(spec())
    old = q.claim('old',lease_seconds=10)
    now[0] = 111
    assert q.recover_expired() == 1
    new = q.claim('new')
    assert new.token != old.token and new.attempt == 2
    publish(old)
    with pytest.raises(ValueError,match='stale'): q.complete(old)
    with pytest.raises(ValueError,match='stale'): q.heartbeat(old)
    publish(new)
    q.complete(new)
    assert q.result(job).attempt_token == new.token


def test_cancel_request_cannot_be_overridden_by_success(queue):
    q,_ = queue
    job = q.enqueue(spec())
    lease = q.claim('worker')
    publish(lease)
    q.cancel(job)
    assert q.heartbeat(lease)
    with pytest.raises(ValueError,match='cancelled'): q.complete(lease)
    q.acknowledge_cancel(lease)
    assert q.get(job)['status'] == 'cancelled'
    with pytest.raises(ValueError): q.result(job)


def test_cancelled_expired_work_is_not_automatically_requeued(queue):
    q,now = queue
    job = q.enqueue(spec())
    q.claim('worker',lease_seconds=10)
    q.cancel(job)
    now[0] = 111
    q.recover_expired()
    assert q.get(job)['status'] == 'cancelled' and q.claim('other') is None


def test_retry_budget_survives_process_restart(queue):
    q,now = queue
    job = q.enqueue(spec(max_attempts=2))
    q.fail(q.claim('a'),'first failure')
    with JobQueue(q.path,clock=lambda:now[0]) as restarted:
        restarted.retry(job)
        restarted.fail(restarted.claim('b'),'second failure')
        with pytest.raises(ValueError,match='retried'): restarted.retry(job)
    assert q.get(job)['attempt'] == 2
    assert q.connection.execute('SELECT count(*) FROM attempts WHERE job_id=?',(job,)).fetchone()[0] == 2


def test_claim_is_durable_when_worker_process_crashes(queue):
    q,now = queue
    job = q.enqueue(spec())
    code = "import os,sys;from pathlib import Path;from meh_studio.jobs import JobQueue;q=JobQueue(Path(sys.argv[1]),clock=lambda:100.);q.claim('crashed',lease_seconds=10);os._exit(9)"
    result = subprocess.run([sys.executable,'-c',code,str(q.path)])
    assert result.returncode == 9 and q.get(job)['status'] == 'running'
    now[0] = 111
    assert q.recover_expired() == 1 and q.get(job)['status'] == 'queued'


def test_incomplete_or_changed_artifacts_do_not_publish(queue):
    q,_ = queue
    job = q.enqueue(spec())
    lease = q.claim('worker')
    with pytest.raises(FileNotFoundError): q.complete(lease)
    path = publish(lease)
    path.write_text('changed')
    with pytest.raises(ValueError,match='integrity'): q.complete(lease)
    assert q.get(job)['status'] == 'running'


def test_later_archive_corruption_is_detected(queue):
    q,_ = queue
    job = q.enqueue(spec())
    lease = q.claim('worker')
    path = publish(lease)
    q.complete(lease)
    assert q.result(job).evidence == 'predicted'
    path.write_text('archive damage')
    with pytest.raises(ValueError,match='integrity'): q.result(job)


@pytest.mark.parametrize('path',['../escape','/absolute','a/../b','a//b','C:/drive','a\\b','completion.json'])
def test_artifact_paths_are_contained(path):
    with pytest.raises(ValueError): Artifact(path=path,sha256='a'*64,size_bytes=1)


def test_completion_cannot_belong_to_different_attempt(queue):
    q,_ = queue
    q.enqueue(spec())
    lease = q.claim('worker')
    publish(lease)
    path = lease.output_directory/'completion.json'
    data = json.loads(path.read_text());data['attempt_token']='other'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='another job or attempt'): q.complete(lease)


def test_existing_database_is_never_replaced(queue):
    q,_ = queue
    job = q.enqueue(spec())
    with pytest.raises(FileExistsError): JobQueue.create(q.path,q.artifact_root)
    assert q.get(job)['status'] == 'queued'


def test_cancellation_during_hashing_wins_publication(queue,monkeypatch):
    q,_ = queue
    job = q.enqueue(spec())
    lease = q.claim('worker')
    publish(lease)
    original = q._verified_completion
    def cancel_then_verify(row):
        with JobQueue(q.path,clock=lambda:100.) as other:
            other.cancel(job)
        return original(row)
    monkeypatch.setattr(q,'_verified_completion',cancel_then_verify)
    with pytest.raises(ValueError,match='cancelled'): q.complete(lease)
    assert q.get(job)['status'] == 'cancel_requested'


def test_lease_expiring_during_hashing_cannot_publish(queue,monkeypatch):
    q,now = queue
    job = q.enqueue(spec())
    lease = q.claim('worker',lease_seconds=10)
    publish(lease)
    original = q._verified_completion
    def expire(row):
        result = original(row)
        now[0] = 111
        return result
    monkeypatch.setattr(q,'_verified_completion',expire)
    with pytest.raises(ValueError,match='stale'): q.complete(lease)
    assert q.get(job)['status'] == 'running'
    q.recover_expired()
    assert q.get(job)['status'] == 'queued'


def test_job_identity_cannot_be_changed_in_database(queue):
    q,_ = queue
    job = q.enqueue(spec())
    changed = spec(parameters_json='{"frequency":2000}').canonical_json()
    q.connection.execute('UPDATE jobs SET spec=? WHERE id=?',(changed,job))
    with pytest.raises(ValueError,match='corrupt'): q.claim('worker')


def test_frozen_job_spec_rejects_mutation():
    value = spec()
    with pytest.raises(ValueError): value.parameters_json = '{}'


def test_symlink_cannot_escape_attempt_directory(queue,tmp_path):
    q,_ = queue
    q.enqueue(spec())
    lease = q.claim('worker')
    publish(lease)
    external = tmp_path/'external.json'
    external.write_text('{"evidence":"predicted"}')
    linked = lease.output_directory/'prediction.json'
    linked.unlink()
    try:
        linked.symlink_to(external)
    except OSError:
        pytest.skip('symbolic links unavailable')
    with pytest.raises(ValueError,match='escaped'): q.complete(lease)
