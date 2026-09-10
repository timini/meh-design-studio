# Pressure, excursion and amplifier current at a stated voltage

Run `meh operating-report SEARCH --input-rms-v 1 --output operating.json` after a
completed search with acoustic objectives. The report uses the verified winner,
its frozen crossover/gain/polarity/delay and the original complete voltage basis.
It does not invoke the solver again or change the winner's ranking.

The input is an RMS reference voltage **before** the DSP. Actual mid-bank and HF
terminal voltages therefore vary with frequency. Every mid receives the same
voltage; the amplifier current includes the sum of all induced mid currents.
Negative real channel power is preserved when energy returns to an ideal source.

The native pressure, current and velocity responses are divided by the explicit
2.83 V excitation. These transfer ratios are independent of whether the native
phasor amplitude is called RMS or peak: using the same convention in numerator
and denominator cancels that distinction. Applying an explicit RMS voltage gives
RMS pressure/current/velocity. Peak sinusoidal displacement is
`sqrt(2) * abs(velocity_rms) / (2*pi*f)`; coil Joule loss is `Re*abs(current_rms)^2`.
Pressure level uses the saved observation coordinates and 20 microPa reference.
There is no inferred distance scaling or far-field qualification.

These are linear single-tone predictions, not safe drive recommendations or
maximum-SPL ratings. Manufacturer AES power is not silently substituted for a
coil thermal limit. The report supplies no amplifier clipping, thermal compression,
breakup, excursion/distortion thresholds or broadband programme-power model.
It preserves the electrical validation result, including unsupported precision
or failed consistency, and does not qualify synthetic/commercial source data.

The analytical sphere experiment checks exterior pressure normalisation for a
prescribed velocity; it does not calibrate a purchased compression driver. A
synthetic HF circuit in a search remains synthetic in its operating report.
Actual driver/chamber measurements and amplifier limits are needed before using
these predictions to set physical limiters or claim available output.
