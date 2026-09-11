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
