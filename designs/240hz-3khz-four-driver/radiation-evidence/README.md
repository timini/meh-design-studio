# Historical R1 exterior radiation smoke

The retained R1 front mesh now completes an actual coupled FEM/BEM solve at
240 Hz with four independent prescribed uniform normal-velocity sources.
The throat remains rigid. This establishes that the actual R1 mesh can be
connected to exterior radiation; it does not establish its acoustic band,
commercial-driver performance, print qualification or optimality.

The exterior is a sealed rigid approximation of the horn and rear mounting
packages. Fastener holes are filled in the acoustic envelope. The default
printable CAD is unchanged. It passes the existing closed/oriented topology,
8,000-triangle budget and 2% CAD-volume checks. Conformance replaces the mouth
with the exact 2,974 FEM mouth triangles: final exterior 7,302 triangles and
3,645 nodes. The front volume has 228,551 tetrahedra and 43,111 nodes.

Boundary Lab at pin `8cb166226e412877d3f71f2845918e479b97aa85` passes preflight
and completes all four excitation columns at 240 Hz. Retained complex fields:

- FEM nodal pressure: 4 × 43,111.
- BEM boundary pressure: 4 × 3,645.
- BEM normal pressure derivative: 4 × 7,302.

The backend reports an interior residual of 1.96e-14, interface flux error of
8.69e-8 and zero interface pressure mismatch. These are solver consistency
checks, not discretisation accuracy. This is float32 CPU, one mesh and one
frequency, with no independent radiation accuracy comparison for R1.

The raw phasor convention is `exp(-i omega t)`. The earlier standalone FEM
curve uses the opposite convention and a different mouth load: do not compare
raw complex values or reuse that curve as an exterior result. No far-field
observation or driver-voltage response is supplied by this smoke run. Unit
normal-velocity basis fields also require explicit sign and source-area
normalisation before any prescribed-flow comparison.

## Reproduce or inspect

[report.json](report.json) summarises the experiment.
[raw-240hz.zip](raw-240hz.zip) retains the original project, both meshes,
preparation reports, upstream compiled system, all complex arrays, logs and
source files from commit `11504fc`. Its `SHA256SUMS.json` covers every other
archive member and was verified after packaging. Original absolute provenance
paths are preserved; the project itself references meshes relatively.

After extracting the archive into a new directory, the `project/project.blab.json`
file is portable with its adjacent `meshes` directory. Use the pinned runtime
and `evaluation/request.json` to rerun, writing to a new output directory.
`original-run/run-r1-radiation-first.py` records the original runtime setup and
600-second per-subprocess limit; adjust its workspace/output paths for a rerun.
Install the project's CAD extra to compile a project from the retained inputs:

```sh
PYTHONPATH=src python designs/240hz-3khz-four-driver/radiation_project.py \
  EXTRACTED/front EXTRACTED/exterior NEW_PROJECT
```

The host slept during the original run. Adapter and upstream assembly timing
counters disagree across the sleep, so neither is offered as a reliable
runtime benchmark. No expensive successful solve was repeated for packaging.

This closes a historical R1 integration question. The current shared ring and
freeform optimisation workflow described in the completion contract remains
the design direction; this prototype has not become a finished speaker.
