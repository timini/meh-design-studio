# Coverage at a declared distance

Optimisation can evaluate the horizontal and vertical cuts and the complete sphere
at a declared radius about the horn throat origin. Set
`acoustic_objectives.observation_distance_m` in the search brief, for example:

```json
"acoustic_objectives": {
  "observation_distance_m": 20.0,
  "sphere": {"angle_precision_deg": 10.0}
}
```

This is a finite-distance pressure calculation at 20 metres from `(0, 0, 0)`,
not a far-field transformation or a 1-metre sensitivity measurement. The same
radius applies to both polar cuts and the sphere. The value is recorded in the
compiled Boundary Lab project and checked against native observation coordinates
before scoring. Scoring, completed-search replay, recovery and finalist validation
retain the declared distance; a 1-metre result cannot be scored as a 20-metre run.
The geometry export contains the original brief and project.

The default remains 1 metre. Default-valued objectives omit the new field in
serialisation to preserve historical control hashes. Existing experiments stay at
their original distance and do not become audience-distance predictions.

For compilation outside an optimisation, use
`meh compile-radiating ... --observation-distance-m 20`. The radius must
be positive and finite and must enclose the complete exterior mesh about the
throat origin. This conservative bound keeps all polar and spherical observation
points outside the model, including for asymmetric geometry.

Changing observation distance can change the relative response and directivity of
an extended source, so do not extrapolate these from 1 metre with an inverse-square
level correction alone. Keep the geometry and DSP fixed and compare calculations
at increasing radii before describing a result as far-field stable. Absolute
pressure remains dependent on the declared drive voltage and source model;
distance selection does not establish source calibration, maximum SPL, room or
outdoor propagation, or agreement with a physical loudspeaker.
