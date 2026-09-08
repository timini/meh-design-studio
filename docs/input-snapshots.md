# Input snapshots for durable jobs

This library increment supplies a verifiable input identity for the existing `JobSpec.input_digest`. Callers enumerate all dependencies under stable logical names. Original absolute paths do not enter the identity; logical names, byte counts and SHA-256 content hashes do. Copying the same inputs to another machine preserves identity, while changing a named dependency changes it.

```python
from pathlib import Path
from meh_studio.snapshots import capture_inputs, verify_snapshot
from meh_studio.jobs import JobSpec

snapshot = capture_inputs(
    {"project": Path("project.json"), "mesh": Path("mesh.msh")},
    Path("captured-inputs"),
)
spec = JobSpec(kind="solve", input_digest=snapshot.content_hash,
               parameters_json='{"backend":"beat_cpu"}')
verified = verify_snapshot(Path("captured-inputs"), spec.input_digest)
# A future worker must consume the verified copies, not the original paths.
project_copy = Path("captured-inputs") / verified.files[1].filename
```

Files use portable lowercase logical names and generated flat filenames. Input symlinks and special files are rejected. Capture streams at most 256 MiB per file, 1 GiB in total and 128 files, using 1 MiB chunks. Before/after descriptor metadata checks reject detected source changes during an individual copy. The limits deliberately bound this initial API; larger meshes need a separately reviewed capacity change.

Capture requires a fresh output directory. It writes copies first and atomically renames the manifest last. Failed or interrupted capture may leave a partial directory without a manifest; retry in a new directory. This is process-interruption handling, not a power-loss durability guarantee: files are not fsynced. Existing directories are never overwritten. Snapshot storage is not write-protected; verification detects changed copies against the externally held identity.

The reader bounds manifests to 64 KiB before parsing, rejects duplicate JSON keys, validates strict sizes and versions, and streams every listed file again. Verification requires the expected identity, normally obtained from the queued job. It returns the validated manifest; it does not open a persistent read lease. Callers must own the snapshot directory and prevent concurrent mutation during subsequent consumption. Unlisted files are not dependencies and must never be consumed by a worker.

Dependencies are captured sequentially, not as an atomic filesystem transaction. Callers must freeze inputs when cross-file consistency matters. This increment does not discover mesh references, rewrite project paths, verify upstream versions, run workers, cancel jobs, or provide acoustic qualification. Those remain subsequent integration tasks. Job parameters separately bind the queued operation through the existing JobSpec identity.

Capture rejects source paths resolving inside the destination before reserving that directory, including aliases through symlinked parents. On POSIX the snapshot directory is created with mode 0700 and all copies and the manifest with mode 0600, subject to a more restrictive umask. Windows access remains governed by the containing directory ACL; callers must select a private storage location.

All source handles are opened before reserving the output directory or creating copies. Later changes to a source parent link therefore cannot substitute a generated output for a dependency. The supplied output entry itself must not be a symlink, including a dangling link; capture reserves that exact directory entry rather than following it to another location.

Parent directory aliases are resolved once before reservation; subsequent writes use that canonical parent location. Retargeting an original parent link after mkdir cannot redirect publication into another directory. As with other local project storage, the resolved storage ancestors must remain under caller control throughout capture.
