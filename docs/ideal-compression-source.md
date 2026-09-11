# Explicit diaphragm-to-outlet area transformation

A throat source can now declare `ideal_outlet_area_m2` separately from its
physical diaphragm area `sd_m2`. Search geometry uses the outlet area. The
compiler transforms the physical circuit into the outlet-velocity coordinate
used by the native moving boundary. Operating reports convert that velocity
back before reporting diaphragm excursion, and retain outlet velocity separately.

This is an **ideal, lossless, zero-length area transformer**. It supplies no
phase-plug propagation, internal cavity/rear load, losses, diaphragm breakup or
commercial-driver calibration. It is a useful explicit approximation, not a
qualified replacement for the current synthetic HF source. The
[commercial HF audit](research/commercial-hf-source-audit.md) remains unresolved.

## Circuit and motion coordinates

Let `n = Sd / So`, where `So` is the declared outlet area. Conservation of
volume flow gives `vo = n vd`. Conservation of mechanical power gives
`Fo = Fd / n`. In the outlet coordinate the equivalent parameters are:

| Quantity | Outlet-coordinate value |
| --- | --- |
| Coil resistance and inductance | unchanged |
| Force factor | `Bl / n` |
| Dry moving mass | `Mmd / n²` |
| Mechanical resistance | `Rms / n²` |
| Mechanical compliance | `Cms × n²` |
| Moving boundary area | `So` |

The original `SourceModel`, driver revision and provenance remain physical
diaphragm records. `sources.json` retains them unchanged. The compiled system
stores the transformation, physical source hash and both areas alongside its
equivalent circuit. Native velocity arrays describe the outlet coordinate;
native current arrays still describe actual coil current. Electrical consistency
checks use the equivalent circuit in its matching native coordinate.

`meh` operating reports verify the transformation against `sources.json` and
the compiled parameters. `component_velocity_rms_m_s` and
`component_peak_excursion_m` refer to physical diaphragms.
`component_outlet_velocity_rms_m_s` reports the separate outlet coordinate when
an explicit transformer exists. Pressure, current and coil heating need no
coordinate correction. No maximum output or safe operating limit is inferred.

The independent circuit reference continues to accept physical diaphragm
parameters and mechanical loads expressed in that coordinate. A reciprocal
two-driver load test separately transforms the whole load matrix and checks
current, induced motion, volume flow and each power term across four frequencies.
It therefore checks the coupled equations, not just parameter assignment.

## Scope and compatibility

Omitting `ideal_outlet_area_m2` retains the previous direct-piston model and
canonical serialization. Existing source, geometry and search identities remain
unchanged. Effective area mismatches are still rejected unless the outlet model
is explicitly declared. Nonfinite/underflowing transformed circuits are rejected.

Only the throat supports this approximation. Mid drivers retain their explicit
front and rear acoustic regions; the compiler rejects an outlet declaration on
the mid source rather than silently transforming both sides. A real compression
driver may require a substantially richer source model and independent complex
load measurements. Adding a manufacturer name or an outlet area does not supply
that evidence.

## Completed native reference

A fresh one-candidate search from source `b7255b0` compiled and solved an
equivalent synthetic circuit, then replayed and exported it. The physical throat
area was doubled and its physical circuit changed so that its outlet circuit
exactly matched the earlier periodic-profile seed (`ab6714f`). All native mesh
hashes matched. Every retained complex quantity at 350, 1000, 2000 and 3000 Hz
matched the earlier run exactly: maximum relative complex L2 difference **0**,
against the predeclared 1e-8 limit. The electrical checks also passed their
unchanged 1e-8 limits (maximum reciprocity residual 4.92199e-9).

The 1 V RMS operating report correctly gives physical HF velocity and excursion
using half the outlet velocity. Search replay and the exported bundle verify.
The [raw evidence, controls, runners and archive hashes](../validation/evidence/compression-outlet/report.json)
retain these checks. Relevant unit verification: 730 non-CAD tests passed; one
bounded review found no material issue.

This is coordinate equivalence in a small synthetic five-source reference, not
commercial-source accuracy. Its response variation remains 14.56982 dB, and its
historical synthetic 2-ohm screen is explicitly disabled. It does not establish
the target horn's performance, mesh convergence, physical or print qualification.
