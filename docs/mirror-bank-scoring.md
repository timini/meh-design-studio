# Physical driver counts in scoring and operating predictions

11 September 2026

Acoustic scoring now uses every physical mid coil when checking the parallel
bank's impedance and reporting amplifier current. Previously, a symmetry-reduced
model could appear to have too high an impedance because only its representative
coil currents were summed. That could incorrectly pass the amplifier-load
constraint. Full models retain their previous results.

The scorer resolves physical orbit counts from hashed moving-surface meshes and
checks response metadata against those counts, including for exploratory FP32
results that cannot pass the separate strict electrical-validation gate. Native
pressure already includes the complete group excitation: pressure and excitation
weights are not multiplied again. Receiving coil currents are multiplied by the
number of represented physical drivers.

Operating reports preserve current, velocity, excursion and resistive loss for
one physical driver per representative. Group current and group coil loss are
reported separately; amplifier current and total input power include the whole
physical bank. With RMS quantities:

```text
Igroup[j] = n[j] Icoil[j]
Pinput = sum(n[j] real(V[j] conj(Icoil[j])))
Pcoil_group[j] = n[j] R[j] abs(Icoil[j])²
```

Diaphragm completion factors do not multiply these electrical quantities.
Excursion remains the excursion of one physical driver. The independent
three-driver circuit test verifies reduced/full power equivalence; the five-port
network test verifies a four-mid bank's impedance, selected DSP currents and
rejection below the unchanged 2-ohm constraint.

## Native verification

The retained 3 mm quarter model has three voltage ports representing one HF
driver and four physical mids. Its minimum parallel-bank impedance is
**1.5212129214 ohms**. The corrected scorer agrees with the independently summed
native currents to `1e-13` relative tolerance and rejects the bank when the
2-ohm constraint is enabled. This is a synthetic-source diagnostic, not a
recommendation for the commercial driver bank.

Selected DSP amplifier currents and an explicit 2 V RMS operating calculation
also agree with independent physical-coil sums. Both original unreduced tilted
trials reproduce every original acoustic score field exactly. All 826 non-CAD
tests pass, with three platform/version skips and 30 CAD tests deselected. One
bounded material review found no actionable issues.

The additional 3/8 mm interior/exterior mesh contains 224,591 tetrahedra and
4,372 exterior triangles. The four-frequency FP64 solve completed using source
commit `25e69a8575077df2c533ccab6db13ee4a823cc53`. Its fields differ from the
4/8 mm quarter model by at most **1.55464%**, passing the original 2% comparison
limit. The maximum difference from the older full model is **8.69550%**, which
still fails. Adjacent bank-impedance difference is 0.05619%, also passing 2%.

Passing one adjacent mesh pair does not establish physical accuracy or qualify
the current full model. The prior failed comparisons in the
[four-level study](mirror-driver-validation.md#four-level-mesh-refinement)
remain unchanged. A comparison that separates symmetry reduction from differing
full-model discretisation is still needed.

The [evidence report](../validation/evidence/mirror-bank-scoring/report.json)
indexes the new raw native solve, frozen controls, comparisons, scoring checks,
2-ohm rejection and exact postprocessor source snapshots. Earlier native fields
retain their original source commits. Source data, frequency coverage and
manufacturing qualification have not changed.

This fixes scoring and operating calculations for valid reduced projects. The
production generated-geometry compiler still uses the full model, and fixed-CAD
circuit replacement still rejects reduced driver orbits. The additional
geometry/search integration must preserve source assignments, mirror symmetry
and numerical evidence before reduced models can accelerate production search.
