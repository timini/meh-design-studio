# Preserve completed frequencies after a timeout

A solver timeout does not erase the frequencies already completed. Their arrays
can be inspected and combined with a supplementary solve without changing the
original timeout, its request, or its native result manifest.

```sh
meh inspect-stopped original/project.blab.json original/evaluation > partial.json
meh assemble-frequencies original/project.blab.json original/evaluation supplemental/evaluation \
  --request original/evaluation/request.json > assembled.json
```

The first command accepts a managed evaluation marked `timed_out` or `cancelled`.
A live evaluation, a completed evaluation, or a generic failure is not eligible
for partial reuse through that command. In particular, a failure caused by a
changed runtime or invalid contract must not be treated as an ordinary timeout.
Normal completed-result inspection continues to reject partial native runs.

All completed samples receive the same source, mesh, physical-domain, output,
axis, unit, shape, finite-value and complex-storage checks used by the complete
result reader. Incomplete mask entries must have no result row; the original
request and missing frequencies remain explicit. This verifies numerical artifacts,
not acoustic accuracy.

Run the supplementary frequencies against the **unchanged original project and
meshes**, including at least one already-completed frequency. Use the same pinned
solver runtime and options and a sufficient explicit solver timeout. Assembly
requires matching runtime, project, compiled system, physical-domain artifacts,
excitation basis and requested outputs. Every additional part must overlap the
previously accepted samples, and every frequency in the explicit full request
must be covered.

Overlaps must agree within `1e-5` relative complex norm for every retained
quantity. Exterior pressure also has a 0.05 dB magnitude and 0.5° phase limit,
with a 0.001 relative-null floor applied independently to each excitation.
Excluded display-comparison samples are recorded; the norm check uses every
sample. Zero reference quantities must remain zero. None of these checks is a
mesh-convergence or physical-validation substitute.

Assembly returns a separate `derived_frequency_assembly` report. Each selected
frequency points to its original arrays and hashes, and the report retains every
source evaluation's status and overlap results. It does not fabricate a completed
native manifest, rewrite a failed search as successful, choose a new DSP setting,
or produce a print-qualified design. The original evaluation directories remain
required. `verify_frequency_assembly` rechecks their hashes and row bindings
before a caller consumes the report.

The [15-frequency vocal-band experiment](wide-vocal-completion.md) demonstrates
this path with an actual timeout and a separate three-frequency continuation.
The repeated sample is identical, the full grid is verified, and the candidate's
failed response screen remains explicit.
