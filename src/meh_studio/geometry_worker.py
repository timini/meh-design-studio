"""One leased geometry task in a spawned process; no solver execution."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.metadata
import platform
import sys
import threading
import json
import math
import multiprocessing
from pathlib import Path
import time

from .geometry import HornGeometry, export_geometry
from .jobs import Artifact, Completion, JobQueue, JobSpec, Lease, file_digest
from .snapshots import read_snapshot_manifest, read_snapshot_payload


def geometry_runtime() -> dict:
    """Fingerprint a trusted local installation, not an attestation of binaries."""
    from . import geometry
    packages=sorted((distribution.metadata.get('Name',''),distribution.version)
                    for distribution in importlib.metadata.distributions())
    return {'python':sys.version,'implementation':platform.python_implementation(),
            'system':platform.system(),'release':platform.release(),'machine':platform.machine(),
            'packages':packages,
            'code':{name:hashlib.sha256(Path(path).read_bytes()).hexdigest()
                    for name,path in {'worker':__file__,'geometry':geometry.__file__}.items()}}


def geometry_spec(snapshot_digest: str, *, max_attempts=3) -> JobSpec:
    parameters={'operation':'export_geometry','version':2,'runtime':geometry_runtime()}
    return JobSpec(kind='geometry',input_digest=snapshot_digest,
                   parameters_json=json.dumps(parameters,sort_keys=True),max_attempts=max_attempts)


def _export(design_json: str, directory: str, expected_runtime: dict):
    # JSON round-trip normalizes package tuples to the persisted representation.
    def check():
        if json.loads(json.dumps(geometry_runtime()))!=expected_runtime:
            raise ValueError('geometry child runtime differs from queued identity')
    check()
    export_geometry(HornGeometry.model_validate_json(design_json),Path(directory)/'geometry')
    check()
    (Path(directory)/'geometry/runtime.json').write_text(
        json.dumps(expected_runtime,sort_keys=True,indent=2),encoding='utf-8')


def run_geometry(queue: JobQueue, lease: Lease, snapshot_directory: Path, *, timeout_s=600):
    """Run a caller-claimed geometry lease, heartbeat it and publish verified files.

    The snapshot must contain exactly one dependency named design. Other job
    kinds and parameters are rejected before launch. Storage is caller-owned.
    """
    process=None
    started=time.monotonic()
    try:
        if isinstance(timeout_s,bool) or not math.isfinite(timeout_s) or not 0<timeout_s<=3600:
            raise ValueError('worker timeout must be positive and at most one hour')
        if lease.spec != geometry_spec(lease.spec.input_digest,max_attempts=lease.spec.max_attempts):
            raise ValueError('unsupported geometry worker job')
        if queue.heartbeat(lease,lease_seconds=30):
            queue.acknowledge_cancel(lease)
            return
        snapshot=read_snapshot_manifest(snapshot_directory,lease.spec.input_digest)
        if len(snapshot.files)!=1 or snapshot.files[0].name!='design':
            raise ValueError('geometry worker requires one design dependency')
        entry=snapshot.files[0]
        if entry.size_bytes>1024*1024:
            raise ValueError('geometry design exceeds 1 MiB')
        payload=read_snapshot_payload(snapshot_directory,entry,max_bytes=1024*1024)
        design=HornGeometry.model_validate_json(payload)
        lease.output_directory.mkdir(parents=True,exist_ok=False)
        process=multiprocessing.get_context('spawn').Process(
            target=_export,args=(design.canonical_json(),str(lease.output_directory),
                                 json.loads(lease.spec.parameters_json)['runtime']),daemon=True)
        process.start()
        next_heartbeat=0.
        while True:
            now=time.monotonic()
            if now>=next_heartbeat:
                if queue.heartbeat(lease,lease_seconds=30):
                    _stop(process)
                    queue.acknowledge_cancel(lease)
                    return
                next_heartbeat=now+1
            if now-started>=timeout_s:
                raise TimeoutError('geometry worker exceeded time limit')
            process.join(timeout=.1)
            if not process.is_alive():
                break
        if process.exitcode!=0:
            raise RuntimeError(f'geometry worker exited with code {process.exitcode}')
        if queue.heartbeat(lease,lease_seconds=30):
            queue.acknowledge_cancel(lease)
            return
        with _publication_lease(queue,lease) as check_renewal:
            root=lease.output_directory
            report=json.loads((root/'geometry/geometry.json').read_text())
            if report.get('status')!='complete' or report.get('design_hash')!=design.content_hash:
                raise ValueError('geometry worker did not produce a matching complete report')
            files=[]
            for path in sorted((root/'geometry').rglob('*')):
                if path.is_symlink():
                    raise ValueError('worker output cannot contain symlinks')
                if path.is_file():
                    files.append(Artifact(path=path.relative_to(root).as_posix(),
                                          sha256=file_digest(path,check=check_renewal),size_bytes=path.stat().st_size))
            record=Completion(job_id=lease.job_id,attempt_token=lease.token,
                              evidence='experimental_geometry',files=tuple(files))
            temporary=root/'completion.json.tmp'
            temporary.write_text(record.canonical_json(),encoding='utf-8')
            temporary.replace(root/'completion.json')
            check_renewal()
            queue.complete(lease,check=check_renewal)
    except Exception as exc:
        if process is not None:
            _stop(process)
        # A stale lease cannot mutate a newer attempt. Preserve the original
        # diagnostic locally by re-raising if the queue rejects this finish.
        try:
            queue.fail(lease,f'{type(exc).__name__}: {exc}')
        except Exception as finish_error:
            raise exc from finish_error
    finally:
        if process is not None:
            _stop(process)


def _stop(process):
    if process.pid is not None:
        if process.is_alive():
            process.kill()
        process.join()


@contextmanager
def _publication_lease(queue, lease):
    """Renew using a separate SQLite connection while the caller hashes files."""
    stopped=threading.Event()
    errors=[]
    cancelled=threading.Event()
    def renew():
        try:
            with JobQueue(queue.path,clock=queue.clock) as connection:
                while not stopped.wait(.5):
                    if connection.heartbeat(lease,lease_seconds=30):
                        cancelled.set()
        except Exception as exc:
            errors.append(exc)
    thread=threading.Thread(target=renew,name='geometry-publication-lease',daemon=True)
    thread.start()
    def check():
        if cancelled.is_set():
            raise RuntimeError('geometry publication cancelled')
        if errors:
            raise RuntimeError('publication lease renewal failed') from errors[0]
    try:
        yield check
    finally:
        stopped.set()
        thread.join()
