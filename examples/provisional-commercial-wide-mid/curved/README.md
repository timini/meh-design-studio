# Curved commercial-circuit starting shapes

These two input sets use the same four-mid, shared-horn topology and provisional
Peerless HF circuit as the parent example. Both horns are 300 mm long:

| Input directory | Axial radius controls | Sections | Nominal reference mouth diameter |
| --- | --- | --- | ---: |
| `exponential-round` | Exponential | Circular | 320 mm |
| `quadratic-rounded-square` | Quadratic | Rounded square | 300 mm |

The surfaces are periodic cubic spline lofts through these controls, not exact
analytic flares between stations. Nominal reference diameter is a geometry
parameter, not the actual width of every noncircular mouth.

Both designs have completed CAD, tagged-air meshing and coupled-solver input
preparation. The exponential seed's native search is underway; these files are
**starting points, not acoustically accepted designs**. The original preparation
failures and corrected geometry are preserved in
[the preparation study](../../../docs/curved-mouth-preparation.md).

Each brief permits two proposals: the declared seed followed by a fitness-driven
mutation when eligible, or the existing random fallback. It retains 15 native
frequencies, 20 m H/V and spherical observations, 3–5 kHz acoustic handover,
the 2-ohm bank constraint and £300 planning ceiling. Profile scales span 0.5–1.7;
mouth-reference radius bounds are 140–180 mm. Exterior mesh size is 10 mm.
No response, convergence or physical acceptance threshold is relaxed.

From the repository root, initialise a catalogue once and add both source records:

```sh
meh catalogue init runs/curved-commercial.sqlite
meh catalogue add runs/curved-commercial.sqlite examples/reported-drivers/faitalpro-4fe32-16.json
meh catalogue add runs/curved-commercial.sqlite examples/reported-drivers/peerless-dfm2535-8-ideal-outlet.json
```

After installing CAD dependencies and the
[pinned native runtime](../../../docs/boundary-lab-adapter.md), run one case:

```sh
meh optimise examples/provisional-commercial-wide-mid/curved/exponential-round/brief.json \
  --geometry examples/provisional-commercial-wide-mid/curved/exponential-round/geometry.json \
  --database runs/curved-commercial.sqlite \
  --output runs/my-exponential-search \
  --checkout runs/runtime/boundary-lab \
  --python runs/runtime/blab-env/bin/python \
  --julia runs/runtime/julia-1.12.6/bin/julia \
  --backend beat_cpu --julia-threads 4 \
  --timeout-per-solver-stage-s 7200
```

Use the configured Julia depot. Substitute `quadratic-rounded-square` for both
input paths and choose a new output directory to run the other case. Run the
full-size cases sequentially on a memory-limited machine. These are expensive
exploratory solves; `beat_cpu` stores complex64 fields and cannot establish the
separate strict electrical qualification gate. `coupled_reference` is available
for FP64 studies, with different compute and memory requirements.

After successful completion, use `meh operating-report` and `meh export-search`
as shown in the [parent example](../README.md). Search completion does not imply
the 6 dB response screen passed. Source calibration, physical driver interfaces,
output limits, held-out frequencies, mesh refinement and actual build/measurement
qualification remain required before accepting a horn.
