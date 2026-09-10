# Independent exterior radiation reference

The exterior BEM solver passes a predeclared 2% complex-pressure error screen
against a uniformly pulsating sphere at 350, 2000, 5000 and 7500 Hz. Maximum error
across both 73-angle polar cuts is 0.708%; no gain, delay or phase is fitted.
The [comparison report](../validation/evidence/pulsating-sphere/report.json) and
[raw archive](../validation/evidence/pulsating-sphere/raw-run.zip) retain native
inputs/results and exact original generation/launch/comparison scripts. The native
adapter ran from the clean detached application source `a0a604e`; the reusable
comparison script is separately identified by its content hash.

For `exp(-i omega t)`, the outgoing spherical solution is `p=C exp(ikr)/r`.
Its radial derivative satisfies `dp/dr=i omega rho v` at radius `a`, giving

```
p(r) = rho*c*(-i*k*a)/(1-i*k*a) * (a/r) * exp(i*k*(r-a)) * v
```

The fixture uses `a=0.02 m`, `rho=1.21 kg/m³`, `c=343 m/s`, and unit outward normal
velocity coefficient. A 3 mm target triangular mesh approximates the sphere.
The native prescribed normal-velocity basis is unit amplitude. The comparison
uses each saved observation coordinate, the explicit native phasor convention,
and the complete complex pressure. Reference parameters are hashed into the
project; raw domains and arrays are verified through the normal adapter contract.

| Frequency | Maximum relative complex error |
|---|---:|
| 350 Hz | 0.443% |
| 2000 Hz | 0.360% |
| 5000 Hz | 0.452% |
| 7500 Hz | 0.708% |

Reproduce with `validation/fixtures/generate_pulsating_sphere.py OUTPUT`, solve its
project using `meh solve-project` and a request retaining project observations
and BEM traces at the four listed frequencies, then run
`validation/fixtures/compare_pulsating_sphere.py FIXTURE EVALUATION --output REPORT`.
Generators and comparison reports refuse to replace existing output.

This is an independent analytical acoustic reference for exterior radiation and
its phase/normalization, complementing the existing uniform-tube interior test.
It does not validate the coupled horn discretisation, voltage-driven commercial
sources, nonlinear performance or manufacturing. In particular, it does not
cancel the separately recorded strict electrical reciprocity failures. No RMS or
loudspeaker SPL interpretation is inferred from the unit-velocity coefficient.
