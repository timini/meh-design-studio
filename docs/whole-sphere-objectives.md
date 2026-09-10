# Whole-sphere scoring for irregular horns

An irregular horn can have lobes between its horizontal and vertical polar cuts.
New irregular-horn searches should enable `acoustic_objectives.sphere`:

```json
"sphere": {
  "angle_precision_deg": 10.0,
  "control_from_hz": 1000.0,
  "rear_attenuation_db": 30.0
}
```

These are design preferences, not measured Solana targets. The 350 Hz high-pass
and upper crossover choices remain separate acoustic objectives. Coverage
control starts at 1 kHz in this example because demanding a narrow beam at 350 Hz
from a small mouth can be impractical. The optimiser still scores low-frequency
response and both principal cuts over the complete supplied frequency grid.

The compiler enables native spherical observations before hashing the project.
The pinned Boundary Lab runtime evaluates the same solved coupled pressure field
at `round(41253 / angle_precision_deg²)` Fibonacci directions: 413 at 10 degrees.
All physical driver voltage bases are retained, so the same common mid-bank
voltage, crossover, polarity and HF delay combine the sphere and principal-cut
responses. Missing sphere data is an error; no missing directions are interpolated
from the two cuts. The saved coordinate grid and its order must match the pinned
native formula and the declared sampling precision.

Each sphere direction receives solid-angle weight `4π/N`. In the forward
hemisphere, the target in dB is
`max(-rear_attenuation_db, -6*((azimuth/(H/2))²+(elevation/(V/2))²))`, where
`azimuth=atan2(x,z)` and `elevation=atan2(y,z)`. The rear hemisphere target is the
declared attenuation. Each complex pressure is normalised to the same-frequency
on-axis pressure; the dB calculation has the existing -120 dB floor. The scorer
computes RMS target error over all directions and the frequencies at or above
`control_from_hz`. Directivity error is the average of the horizontal, vertical
and sphere RMS errors. The existing response-ripple and directivity weight then
form the acoustic objective. This is an explicit heuristic, not an efficiency or
maximum-output objective.

The score also retains whole-sphere mean-square pressure relative to the axis and
its decibel ratio. These are sampled pressure metrics at the saved radius. They
are **not qualified radiated power, efficiency or far-field directivity index**.
Equal-area quadrature is approximate; a single grid is not an angular convergence
proof. The selectable spacing is 2.5–15 degrees, bounded for local workloads.

Finalist validation freezes all DSP settings and halves the sampling spacing,
then compares raw complex pressure at every direction on that denser grid over
three FEM mesh sizes and additional frequency samples. The 0.5 dB / 5 degree
limits are unchanged. This adds previously unscored directions, but does not
establish angular quadrature convergence or independent full-exterior mesh
convergence. Searches finer than 5 degrees must use a separately supported
validation strategy: the current runner explicitly rejects refinement below its
2.5-degree limit before starting a run.

Omitting `sphere` preserves historical controls and scores byte-for-byte at the
model-serialization level. Existing two-cut search evidence remains labelled as
such; it is not retroactively promoted to whole-sphere evidence. The analytical
pulsating-sphere fixture accepts `--sphere-angle-deg 10` to check native complex
pressure at these additional directions against its unchanged 2% error limit.

Executed native reference: frozen application source `952e0e6`, with 413 sphere
directions plus both 73-point polar cuts, passes at 350, 2,000, 5,000 and 7,500 Hz.
Maximum relative complex-pressure error is 0.708%, with no gain/phase/delay fit.
The [comparison report](../validation/evidence/whole-sphere-reference/report.json)
and [raw archive](../validation/evidence/whole-sphere-reference/raw-run.zip)
preserve the source identity, exact runners and all native inputs/results. This
checks spherical observation evaluation for the analytical exterior reference;
it does not establish accuracy of a coupled horn or commercial driver model.
