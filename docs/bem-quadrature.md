# Explicit boundary integration controls

`solve-project` requests and optimisation briefs can select fixed BEM integration
rules for the pinned CPU backends. This permits integration-order sensitivity
studies without changing the physical model or mesh:

```json
"solver_options": {
  "quadrature_order": 4,
  "singular_order": 4,
  "regular_quadrature_mode": "fixed"
}
```

Regular order may be **1, 2 or 4**. These are the distinct supported triangle
rules in the pinned implementation; other positive integers can silently fall
back to order 2 upstream, so the adapter rejects them. Singular order is an
integer from 1 to 8. Larger orders can be substantially more expensive.

Explicit controls require `beat_cpu` or `coupled_reference` and an exterior BEM
or coupled FEM/BEM project. Interior-only and accelerator cases are rejected.
The adapter passes the controls through the public native request and requires
the result manifest to report matching integration rules. It retains source,
mesh, field and runtime verification. Arbitrary backend option overrides are
not accepted through this interface.

When omitted, the option is absent from serialized briefs and requests, preserving
existing defaults and content identities. When present in a search brief, it
passes to candidate and finalist solves and is checked during recovery/replay.
Frequency assembly already requires matching effective solver options, so
different integration settings cannot be silently combined into one evaluation.

Increasing integration order is a numerical experiment, not proof of convergence.
Keep electrical reciprocity and field-comparison limits fixed, retain failed
levels, and report the actual rules used. Passing an integration study at one
frequency does not establish mesh convergence, physical source calibration,
absolute SPL accuracy or acceptance of a complete horn.

## Executed fixed-mesh reference

The [CRAM reference](measured-cram-reference.md) was rerun at 125 Hz with four
predeclared integration settings. This frequency was selected because it had the
largest reciprocity residual in the earlier nine-frequency run; it is a diagnostic
selection. The project, physical parameters, meshes and observation coordinates
were byte-identical. All four FP64 native evaluations completed and passed artifact
verification, including the requested integration settings.

| Regular / singular order | Electrical reciprocity residual | Maximum field change from preceding level |
| --- | ---: | ---: |
| 2 / 2 | 8.0960403e-5 | 0; exact repeat of the original reference |
| 4 / 2 | 8.0429885e-5 | 0.01331% |
| 4 / 4 | 7.9139254e-5 | 0.06726% |
| 4 / 8 | 7.9152258e-5 | 0.00553% |

Field change is the largest relative L2 difference across all seven native complex
quantities, separately for each voltage excitation, divided by the finer result's
norm. This includes FEM pressure, BEM traces, both polar cuts, diaphragm velocity
and coil current. The final pair passes the predeclared 1% field-stability screen;
the baseline passes its 1e-10 repeatability limit with exact array equality.

**Every level still fails the unchanged 1e-8 electrical reciprocity limit.** KVL
residuals remain below 2.4e-16 and the Hermitian electrical admittance stays positive.
Finer integration alone therefore has not resolved the reciprocity failure. These
results establish integration sensitivity for this fixed discretisation at one
frequency, not mesh convergence or acoustic accuracy. The earlier conditional
measured-response failure remains unchanged.

The [report and raw archive](../validation/evidence/bem-quadrature/report.json)
retain all four runs, the original reference, exact requests, source identities,
predeclared controls, comparison code and upstream license. Native application
source is `852a5a33af9617ac3a40f9956ca12f744e3d0ba8`; the earlier reference remains
at `c217b86ba76a2c10c6032091bfded518180fa5d4`. Both use the pinned Boundary Lab
revision `8cb166226e412877d3f71f2845918e479b97aa85`.
