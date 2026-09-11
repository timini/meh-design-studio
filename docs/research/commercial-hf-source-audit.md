# Commercial HF source audit

Inspected 11 September 2026. The current native studies still use a synthetic HF
source. This audit identifies a possible replacement; it does not substitute a
commercial name onto that source or qualify a driver.

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
does not attach units to individual numeric fields; mass/compliance conventions
need confirmation before importing a solver record. Its graph labels identify an
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
