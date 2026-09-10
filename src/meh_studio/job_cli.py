"""CLI integration for the existing snapshot, ledger and isolated CAD worker."""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import uuid

from .jobs import JobQueue


def add_job_commands(commands):
    jobs = commands.add_parser('jobs', help='save, run and inspect experimental CAD jobs')
    operations = jobs.add_subparsers(dest='operation', required=True)
    init = operations.add_parser('init')
    init.add_argument('database', type=Path)
    init.add_argument('--artifacts', type=Path, required=True)
    submit = operations.add_parser('submit-geometry')
    submit.add_argument('database', type=Path)
    submit.add_argument('design', type=Path)
    run = operations.add_parser('run-geometry', help='run at most one queued geometry job')
    run.add_argument('database', type=Path)
    run.add_argument('--timeout-s', type=float, default=600)
    for name in ('status', 'cancel', 'retry', 'result'):
        command = operations.add_parser(name)
        command.add_argument('database', type=Path)
        command.add_argument('job_id')
    recover = operations.add_parser('recover', help='recover expired leases; does not stop orphan processes')
    recover.add_argument('database', type=Path)


def _submit(queue, source):
    from .geometry import HornGeometry
    from .geometry_worker import geometry_spec
    from .snapshots import InputSnapshot, SnapshotFile, capture_inputs, verify_snapshot

    with source.open('rb') as stream:
        payload = stream.read(1024 * 1024 + 1)
    if len(payload) > 1024 * 1024:
        raise ValueError('geometry design exceeds 1 MiB')
    design = HornGeometry.model_validate_json(payload)
    payload = design.canonical_json().encode('utf-8')
    snapshot = InputSnapshot(files=(SnapshotFile(name='design',
        sha256=hashlib.sha256(payload).hexdigest(), size_bytes=len(payload)),))
    destination = queue.artifact_root / 'inputs' / snapshot.content_hash
    queue.artifact_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.submit-', dir=queue.artifact_root) as temporary:
        canonical = Path(temporary) / 'design.json'
        canonical.write_bytes(payload)
        try:
            captured = capture_inputs({'design': canonical}, destination)
        except FileExistsError:
            captured = verify_snapshot(destination, snapshot.content_hash)
        if captured != snapshot:
            raise ValueError('captured design identity differs from submission')
    return queue.enqueue(geometry_spec(snapshot.content_hash))


def _status(queue, job_id):
    row = queue.get(job_id)
    return {'job_id': row['id'], 'status': row['status'], 'attempt': row['attempt'],
            'error': row['error'], 'result_integrity': 'not_checked'}


def execute_job_command(args):
    if args.operation == 'init':
        with JobQueue.create(args.database, args.artifacts):
            return {'created': True, 'database': str(args.database.absolute())}, 0
    with JobQueue(args.database) as queue:
        if args.operation == 'submit-geometry':
            return _status(queue, _submit(queue, args.design)), 0
        if args.operation == 'recover':
            return {'recovered': queue.recover_expired()}, 0
        if args.operation == 'run-geometry':
            import math
            from .geometry_worker import run_geometry
            if not math.isfinite(args.timeout_s) or not 0 < args.timeout_s <= 3600:
                raise ValueError('worker timeout must be positive and at most one hour')
            lease = queue.claim('cli-' + uuid.uuid4().hex, lease_seconds=30, kind='geometry')
            if lease is None:
                return {'status': 'idle'}, 0
            run_geometry(queue, lease, queue.artifact_root / 'inputs' / lease.spec.input_digest,
                         timeout_s=args.timeout_s)
            result = _status(queue, lease.job_id)
            return result, 0 if result['status'] == 'succeeded' else 1
        if args.operation == 'cancel':
            queue.cancel(args.job_id)
        elif args.operation == 'retry':
            queue.retry(args.job_id)
        elif args.operation == 'result':
            completion = queue.result(args.job_id)
            return {'job_id': args.job_id, 'status': 'succeeded', 'result_integrity': 'verified',
                    'directory': str(queue.artifact_root / args.job_id / completion.attempt_token),
                    'completion': completion.model_dump(mode='json')}, 0
        return _status(queue, args.job_id), 0
