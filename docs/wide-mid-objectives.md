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
