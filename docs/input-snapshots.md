# Input snapshots for durable jobs

`capture_inputs(inputs, output)` copies explicitly named dependencies and returns an `InputSnapshot`. Its `content_hash` can be used as `JobSpec.input_digest`. `verify_snapshot(output, expected_digest)` validates the manifest and rehashes all listed files against an identity held outside the snapshot. Original source locations are excluded from the identity; logical names, byte counts and content hashes are included.

```python
from pathlib import Path
from meh_studio.snapshots import capture_inputs, verify_snapshot
from meh_studio.jobs import JobSpec

snapshot = capture_inputs({"project": Path("project.json"), "mesh": Path("mesh.msh")},
                          Path("captured-inputs"))
spec = JobSpec(kind="solve", input_digest=snapshot.content_hash, parameters_json='{}')
verified = verify_snapshot(Path("captured-inputs"), spec.input_digest)
# A worker must consume only the verified copies, never the original paths.
```

The initial API permits 128 regular dependencies, 256 MiB per file and 1 GiB total, streamed in 1 MiB chunks. Stable lowercase logical names produce portable flat filenames. Manifests are bounded to 64 KiB before parsing and reject duplicate JSON keys, noninteger sizes, unsupported versions and duplicate names.

Capture opens all sources before creating copies. POSIX uses nonblocking/no-follow opens and descriptor checks; Windows opens native handles with OPEN_REPARSE_POINT, rejects reparse points and directories, and transfers the validated file handle to a Python stream. Descriptor state before and after copying detects changes. Source paths inside the requested destination, source symlinks and special files are rejected.

Capture writes into an unpredictable sibling staging directory. It compares the opened directory identity with the staging reservation before copying. POSIX writes are relative to a directory descriptor; Windows holds a directory handle that denies rename/deletion. The manifest is written last inside staging. After checking staging identity again and closing handles, a platform-native no-replace rename atomically installs the complete directory at the requested destination. Linux uses renameat2(RENAME_NOREPLACE), macOS renamex_np(RENAME_EXCL), and Windows MoveFileW. An existing destination—including one created during capture—is never replaced. Dangling output links are rejected too.

On POSIX staging is private (0700) and copies/manifest use 0600 subject to a more restrictive umask. Windows inherits the chosen parent ACL, so callers must select private storage. Failed captures may leave a hidden `.meh-snapshot-*` staging directory, possibly containing a complete manifest if final installation failed. It is not the requested published snapshot; cleanup is manual and must not follow substituted paths. Successful capture leaves no staging directory. No fsync or power-loss durability guarantee is made.

Callers must control resolved storage ancestors throughout capture and consumption. This is not protection against an adversary with unrestricted access to the same account. Files are captured sequentially, not as an atomic filesystem-wide transaction; freeze related inputs when cross-file consistency matters. Verification does not hold an enduring read lease, so callers must prevent subsequent mutation while consuming copies. Unlisted files must not be used as dependencies.

This module does not discover project mesh references, rewrite paths, verify solver versions, run workers or grant acoustic/print qualification. Those are separate integration tasks. Cross-platform CI includes directory replacement, no-overwrite, special-file, Windows reparse-swap and lock tests; a configured test is not a claim that every platform run has passed.
