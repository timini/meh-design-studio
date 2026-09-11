# Commercial HF source audit

Inspected 11 September 2026. The current target native studies still use a synthetic
HF source. A separate provisional Peerless circuit is now available for future
experiments; it does not relabel those historical sources or qualify a driver.

## Peerless DFM-2535R00-08

The [official catalogue API](https://products.peerless-audio.com/api/driver/438)
reports revision 1 / MP2, database revision 5.000, updated 6 May 2026:

| Parameter | Reported value |
|---|---:|
| Re / Le | 6.3 ohm / 0.043 mH |
| Mms / Mmd | 0.56 / 0.52 g |
| Cms / Bl | 75 micrometre/N / 3.99 T m |
| Sd / Fs / Qms | 10.9 cm² / 780 Hz / 5.32 |

These are reported circuit data, not parameters measured by this project. The API
does not attach units to individual numeric fields. The provisional import below
declares its inferred conversions explicitly. Its graph labels identify an
LTH142 test horn, SPL at 2.83 V / 1 m and impedance at 1.414 V.

The [current manufacturer PDF](https://products.peerless-audio.com/pdf/438), printed
June 2026, specifies a 25.4 mm exit, 35.5 mm voice coil, 25 W IEC rating and a
1.5 kHz minimum recommended crossover. It does not publish the full circuit table.
Its drawing shows a 90 mm body, 50.8 mm depth and four M6 mounting holes on a
76 mm circle. These are useful mounting inputs, not acoustic internals.

## Files inspected and remaining gap

The API's `excelSheet` reference resolves to a manufacturer workbook containing
on-axis/off-axis SPL, impedance magnitude and scalar summaries. There is no
complex pressure or impedance phase table in its worksheets. The API's
`dummyFile3D` reference resolves to a STEP with two solids. A centre section
shows a filled body and a thin front ring: it does not supply a diaphragm,
phase-plug channels or an open internal acoustic passage. Original files remain
local research inputs; redistribution permission is unknown.

The moving area and exit area differ. Feeding the reported physical circuit into
an exit-sized piston would change the electromechanical/acoustic coupling. A
proper replacement needs an explicit internal model or a calibrated source at
the outlet, including its load dependence. An ideal area transformer could be an
explicit provisional approximation, but would require separate validation of
phase, losses and operating limits. The existing synthetic source remains labelled.

The larger DFM-2544R00-08 is not a shortcut: its
[current API](https://products.peerless-audio.com/api/driver/436) has `Mmd: 0`
and differs from the 2017 preliminary datasheet (including Fs and Qms). Zero is
missing/unsuitable source data here, not a massless physical diaphragm. Do not mix
the revisions or relabel its Mms as dry mass.

No price, stock, maximum output, arbitrary-horn calibration or suitability for
this project has been established by this audit.

## Provisional import and retained failed comparison

The separate [ideal-outlet record](../../examples/reported-drivers/peerless-dfm2535-8-ideal-outlet.json)
uses `derived` provenance and null qualification. It retains the reported physical
dry mass and diaphragm area, with an explicit 25.4 mm ideal outlet. Mechanical
resistance is derived from `2π Fs Mms / Qms`; Mms is used only for that derivation
and the resonance cross-check, not substituted for the dry moving mass.

The same manufacturer's [public catalogue unit table](https://products.peerless-audio.com/transducer/28)
labels mass in grams, compliance in micrometres/newton, area in cm² and inductance
in mH. Applying these conventions to the compression-driver API gives
Fs = 776.60 Hz versus the reported 780 Hz, and Qes = 1.08607 versus 1.09. These
consistency checks support the SI interpretation; they are not direct unit
confirmation or evidence of acoustic accuracy. The API's selected facts were
fetched again and matched the earlier revision.

An unfitted comparison against the manufacturer's plane-wave-tube magnitude
data **fails** the predeclared 3 dB absolute-error screen on 33 samples from
3 to 7.5 kHz: maximum error 4.33329 dB and RMS error 1.83615 dB. It assumes a
25.4 mm matched tube, 0.283 V RMS, density 1.21 kg/m³ and sound speed 343 m/s.
The graph labels the voltage but does not establish the exact tube geometry,
termination, complex phase or calibration uncertainty. No gain fit, narrower
screen or replacement acceptance limit has been used.

The [import and conditional-comparison evidence](../../validation/evidence/peerless-ideal-outlet/report.json)
records source hashes, conversions, failed limits and exact runners. Raw
manufacturer graphs, PDFs and STEP files are not redistributed. Catalogue import
and construction of a five-driver candidate passed, with the correct 25.4 mm
throat and original physical source retained. The import itself did not execute
a native solve of this commercial approximation.

[Derived circuit reanalysis](../circuit-reanalysis.md) now permits a separately
verified change of lumped source circuits using a complete independent native
voltage basis, at fixed acoustic geometry, medium and source surfaces. This
capability has been checked against a fresh native reference. It does not relabel
the original driver or qualify its phase plug. New horn geometry still requires
a fresh acoustic solve.

The record enables exploratory sensitivity and design work while this source
gap remains open. Its package dimensions and nominal outlet opening do not
qualify bolt, gasket or other manufacturing interfaces. The inherited £60 HF
allowance used in the candidate check is not a supplier quote.
