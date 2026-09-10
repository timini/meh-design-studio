# Reported commercial midrange circuits

These catalogue records contain a small set of manufacturer-reported facts,
converted to SI, retrieved 10 September 2026. They are **unqualified provisional
piston models**, not measured horn-loaded sources. No response curves, images or
datasheets are redistributed; provenance retains the original URLs and leaves
redistribution permission unknown. Physical source qualification remains null.

| Record | Manufacturer source | Nominal bank, four parallel |
|---|---|---:|
| `faitalpro-3fe25-8.json` | [3FE25 8Ω](https://faitalpro.com/en/products/LF_Loudspeakers/product_details/index.php?id=401000150) | 2Ω |
| `faitalpro-3fe25-16.json` | [3FE25 16Ω](https://faitalpro.com/en/products/LF_Loudspeakers/product_details/index.php?id=401000152) | 4Ω |
| `faitalpro-4fe32-16.json` | [4FE32 16Ω](https://faitalpro.com/en/products/LF_Loudspeakers/product_details/index.php?id=401005102) | 4Ω |

The source uses published **Mmd**, not Mms, to avoid counting the free-air acoustic
mass a second time when modelling the surrounding air. Unit conversions are
mH → H, g → kg, mm/N → m/N, and cm² → m². Manufacturer rounding and variation
remain uncertainties; no parameter tolerances or valid upper piston band are
invented. Cone breakup, cone/cavity shape, suspension nonlinearity, losses and
thermal compression require additional model/data validation. A listed broad
frequency range is not a qualification of the piston approximation up to 5 kHz.

The outer-diameter field conservatively uses the largest frame span/diagonal from
the manufacturer's two listed dimensions. It does not define the noncircular
frame, bolt pattern, gasket, cone clearance or an installation-ready mounting.
The current general geometry uses the equivalent moving-area disk and ideal
package; exported parts still require these manufacturing interfaces.

Nominal impedance is not a hard minimum. Four 8-ohm drivers can fall below 2 ohms;
use the coupled complex bank current/impedance calculation and an exact amplifier
rating. The 16-ohm alternatives retain a single shared mid amplifier channel and
provide more load margin, at the cost of requiring more voltage for a given power.
Prices are intentionally absent: use dated supplier quotes/allowances in a brief.

Import each JSON with `meh catalogue add DATABASE RECORD`. Experimental search
can evaluate reported circuits while retaining unqualified status; the separate
qualified-design eligibility gate continues to reject these records.

The intended Celestion CDX1-1445 HF remains an unresolved source-model input.
Its [manufacturer page](https://celestion.com/product/cdx1-1445/) provides nominal
response/impedance plots, dimensions and a recommended crossover, but not the
complete dry-mass circuit or complex loaded source required by this solver.
Do not label a synthetic throat piston as a model of that compression driver.
