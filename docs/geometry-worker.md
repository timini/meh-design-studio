# Experimental queued geometry worker

This draft connects the durable queue and input snapshots to real CadQuery export in a spawned child process. It runs one caller-claimed geometry lease; it does not run a background service, mesh acoustic domains or execute Boundary Lab.

Create a snapshot with exactly one logical dependency named `design`, containing a `HornGeometry` JSON record. Build its job using `geometry_spec(snapshot.content_hash)`, enqueue and claim it with `JobQueue`, then call `run_geometry(queue, lease, snapshot_directory)`. Python scripts using this API must protect their entry point with `if __name__ == '__main__':` because the worker uses multiprocessing spawn on every platform.

The parent verifies the snapshot, reads and checks the exact design bytes again, validates the geometry record and passes canonical JSON to the child. Subsequent source-file edits cannot change the design used by CAD. The child exports into a fresh `geometry` subdirectory of the leased attempt. A successful exit alone is insufficient: the parent requires a complete geometry report for the expected design and creates a hashed artifact inventory, then the queue independently verifies it before recording success. Evidence remains `experimental_geometry`; exported parts are not print-qualified or acoustically qualified.

The parent renews a 30-second lease while the child runs, polls cancellation, and kills and joins the child before acknowledging cancellation or reporting a timeout. The polling loop checks the configured elapsed-time threshold (default 600 seconds, maximum one hour). This is not a hard deadline on every validation or file-hashing operation. A child crash cannot publish a successful completion. Existing lease fencing prevents stale attempts from completing newer work.

## Evidence

Local integration tests execute the real geometry exporter through spawn and require STL output plus a queue-verified completion. Separate spawned-process tests exercise crashes and timeouts; a second database connection requests cancellation during execution. Snapshot corruption and cancellation before launch are rejected before output reservation.

## Draft limits before production worker support

- No operating-system memory or disk quota, worker resource scheduler, bounded log collection or persisted runtime accounting.
- Queue-requested cancellation is covered; launch-time signal handling and abrupt parent-process death still need the shared process supervisor and dedicated tests. A daemon multiprocessing child is not an operating-system guarantee against an orphan after forced parent termination.
- No automatic restart loop. Expired leases can be recovered through the queue API, but orphan process cleanup is not yet integrated.
- Snapshot and attempt storage remain caller-controlled. The worker does not protect against another process modifying its output files while publication hashes them.
- Worker code/runtime identity is represented only by the versioned operation marker at this stage. Native CAD/runtime fingerprints must enter production job identity before reusable cross-runtime caching is enabled.
- Native Windows and Linux execution of these worker tests remains required. Current local execution is on macOS; configured hosted CI remains blocked by account billing restrictions.

Do not promote this draft as completed B04 or enable unattended production execution until those boundaries have tests and implementations. The CLI/desktop service integration follows the worker contract rather than duplicating CAD logic in the UI.
