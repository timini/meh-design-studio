# Wide-mid, directivity and shared amplifier objectives

Optional `SearchBrief.acoustic_objectives` enables a common-voltage parallel mid
bank and a separate HF amplifier channel. The default desired low crossover is
350 Hz; upper crossover choices are 3/4/5 kHz, with selectable mid polarity and HF
delay. These are desired ranges, not evidence that a chosen driver works there.
The search grid must cover the low crossover and extend at least 50% above every
upper crossover, so a crossover cannot be selected outside the evaluated band.

DSP uses analogue fourth-order Linkwitz–Riley filters with the native
`exp(-i omega t)` convention. Every mid receives the same complex voltage.
HF delay has positive complex phase in that convention. The filters are applied
to preserved full voltage bases, so no acoustic remesh is needed for DSP changes.
Finalists freeze gain, crossover, polarity and delay before new solves. Exported
settings describe two amplifier channels and the wiring; conversion to a hardware
DSP preset and level calibration are still required.

The objective combines response ripple about the intended 350 Hz roll-off with
horizontal and vertical directivity errors and the existing driver cost term.
Each forward polar plane is compared to a smooth target of -6 dB at the requested
coverage edge, with both forward wings included. Default coverage is 90° × 90°.
The target is an explicit design preference, not a Solana measurement or an
acoustic efficiency metric. Relative response scoring cannot establish absolute
sensitivity, maximum output, distortion or a commercial-driver qualification.

Parallel input impedance sums **all** receiving mid currents from every driven
mid basis, including mutual terms. The HF channel is held at zero volts for that
input-impedance test. The result also retains mid-bank and HF current under the
selected simultaneous drive. An optional hard minimum impedance constraint
rejects loads below the declared value; default 2 ohms is a conservative numeric
minimum, not a manufacturer-specific interpretation of a nominal 2-ohm rating.
`null` disables that screen for explicitly labelled numerical diagnostics.

The same source normalisation is verified before combining currents and pressures.
Voltage/current impedance ratios do not depend on RMS versus peak convention;
absolute current/power/SPL claims do. The pinned runtime's basis is explicitly
2.83 V but is not yet qualified for absolute acoustic sensitivity. Select and
verify an actual Sinbosen module before setting real voltage/current limits.

Sequential finalist validation supports frozen crossovers. The older partitioned
fixed-gain benchmark explicitly rejects crossover searches rather than silently
replacing their DSP. Its existing conical benchmark remains supported.

For crossover searches, sequential finalist mesh checks compare the frozen raw
complex response at **every sampled point inside both requested coverage sectors**,
using the existing 0.5 dB / 5° limits. On-axis curves remain in the report as well.
This adds sampled angular sensitivity to the existing frequency holdout checks;
it does not establish continuous-angle convergence or independent full-exterior
mesh convergence.

Executed diagnostic: applying this scorer to the preserved freeform 1/2/3 kHz
basis selected a 1.5 kHz crossover and 0.4 relative mid gain from the supplied test
choices, with 6.01 dB RMS polar-target error. Its parallel bank reached 1.521 ohms,
so the enabled 2-ohm constraint correctly rejects it. This is resynthesis of the
original synthetic solve, not a new solve, a 350 Hz–5 kHz design or an improved
speaker. The diagnostic disables the load screen only to inspect all metrics;
it is not an accepted candidate under the 2-ohm challenge.

For new irregular-horn searches, enable the optional
[whole-sphere objective](whole-sphere-objectives.md). It detects off-plane lobes
using native pressure samples, adds a third directivity error term, and extends
finalist mesh checks to a denser spherical grid. Historical searches without
that option retain their original two-cut scoring.

## Acoustic handover constraint

The electrical LR4 setting alone does not establish which channel carries the
vocal band. For a declared acoustic handover between 3 and 5 kHz, set
`acoustic_handover_hz: [3000.0, 5000.0]` inside `acoustic_objectives`.
The search then requires the coherent mid-bank on-axis pressure contribution to
be at least the HF-channel contribution at every solved sample from the mid
high-pass through 3 kHz, and the HF contribution to be at least the mid-bank
contribution from 5 kHz upward. Both channels may contribute in between. Explicit
samples at the mid high-pass and both handover boundaries are required; no
interpolated crossover substitutes for those samples.

Contributions are grouped by excitation channel using the full coupled voltage
basis, retaining mutually induced motion in every driver. They are complex
pressure contributions, not independent diaphragm powers or energy fractions.
A passing score records the sampled channel ratio, nulls and checked frequency
bounds. Ratios shown in dB are clipped to ±120 dB for finite display; pass/fail
uses the actual amplitudes, so two zero contributions do not pass a dominance
check. Mid contributions are summed coherently before comparison.

This is an additional constraint on DSP selection. It does not replace response,
coverage, impedance or numerical checks, and it cannot establish off-axis
handover, an exact crossing between samples, breakup, or physical performance.
Frozen-DSP finalist runs retain the constraint on their denser frequency grids.
If no defined DSP response meets it, the candidate fails scoring and its raw
native evaluation remains available. An absent constraint preserves historical
brief identities and scores; old filter-only results do not gain this validation.

A [native-basis reanalysis](../validation/evidence/acoustic-handover/report.json)
from source `e1a7a42` demonstrates why this distinction matters. The larger search's
trial 7 selected a 3 kHz electrical crossover, but its HF-channel contribution
exceeded the mid bank by 1.71 dB at 2 kHz and 4.61 dB at 3 kHz. Applying the new
3–5 kHz constraint to the unchanged voltage basis and original DSP choices
selected a 4 kHz electrical crossover instead. Mid gain 0.2, positive polarity
and 0.75 ms HF delay remained unchanged. Its sampled channel-dominance check
passes, while target-relative response variation worsens from 7.3464 to
10.5264 dB. The geometry therefore still misses the response target.

This is DSP reanalysis of the original `a0a604e` native solve, not a new geometry
solve or an independently validated acoustic improvement. Original search
scores remain unchanged. The report preserves both scores, the old failed
handover check, new settings, exact runner and links/hashes for the original raw
evidence. Synthetic HF, strict electrical-storage failure and missing physical
and mesh qualification remain explicit.
