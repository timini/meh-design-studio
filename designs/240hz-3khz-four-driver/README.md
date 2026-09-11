# MEH 240–3000 prototype R1

A mechanical prototype for four inexpensive 3-inch mids feeding one horn, with a compression tweeter on its throat. Requested midrange band: 240–3000 Hz; bass bins below 240 Hz; tweeter above 3000 Hz. No maximum cabinet size. Budget assumption: GBP 300 per speaker.

**This is a candidate to test, not a demonstrated 240–3000 Hz loudspeaker.** Its meshes pass geometry checks, but this four-around-one-ring configuration has not undergone coupled acoustic optimisation, physical measurements, crossover tuning or print qualification. The package's earlier numerical demonstrations used a different horn and synthetic driver fixtures; they do not validate this design. The current solver geometry does not yet represent this new ring layout. No predicted frequency-response curve is supplied because it would lack supporting evidence.

## Files and dimensions

Download the tracked [R1 artifact archive](MEH-240-3000-prototype-R1.zip) and extract it first. All `parts/`, `geometry.json` and `mesh-checks.json` paths below are relative to the extracted `MEH-240-3000-prototype-R1/` folder. The archive contains the original generated STL/STEP files and their checksums; regeneration is optional. The adjacent `geometry-R1.json` and `mesh-checks-R1.json` are readable copies of the archived evidence.

- `parts/horn_body.stl`: complete horn body, millimetres; import at 100% scale. STEP also supplied for CAD editing.
- `parts/print/core.stl` plus 24 `band_*_sector_*.stl`: print one of each, already oriented with their base at Z=0.
- `parts/rear_cover_print_four.stl`: print four, closed end on the bed.
- `parts/fit_checks/`: two optional interface coupons; print and check with actual drivers before committing to the horn.
- `geometry.json`: dimensions, assembly transforms, source part hashes, material volumes and limitations.
- `mesh-checks.json`: closed-edge, orientation, positive-volume and CAD-volume checks.

Clear mouth diameter 600 mm; axial horn length 450 mm; exterior mouth ribs span 632 mm. STL body envelope is approximately 632 × 632 × 458 mm; CAD bounding-box tolerances give a slightly larger conservative depth. Rear chambers project behind the throat, so allow additional installation depth. There are 29 assembly prints, plus optional coupons. Largest individual print extent is about 242 mm: nominally compatible with a 250 mm cubical build volume, subject to the printer's usable area and brim. The full body STL is intended for inspection or a larger printer.

Four 60 mm ports occupy one ring 80 mm along the horn. Each has a short transition to a nominal 74.6 mm driver opening. The straight conical wall has 4 mm radial thickness (about 3.37 mm normal thickness). Each rear chamber has about 0.928 L gross cavity, approximately 0.80 L after the catalogue driver displacement, before damping and hardware. The 25 mm throat has four M6 clearance holes on a 76 mm pitch circle.

## Parts and budget

Prices observed 10 September 2026; allowances are not quotations. Budget includes the horn assembly and drivers, and excludes bass bins, amplifiers, DSP, measurement equipment, printer and labour.

| Item | Quantity | Allowance |
|---|---:|---:|
| FaitalPRO 3FE25, 8 ohm | 4 | £48 |
| Celestion CDX1-1445, 8 ohm | 1 | £60 |
| PETG, 1 kg spool | 6 | £96 |
| Fasteners, gaskets, adhesive, damping | allowance | £35 |
| Delivery and printing electricity | allowance | £20 |
| Contingency | allowance | £41 |
| Total ceiling | | £300 |

The [midrange supplier](https://www.bluearan.co.uk/index.php?id=FTP3FE25AF&msh=FCB22) listed £7.23 each **excluding VAT**, on clearance. The [tweeter supplier](https://www.thomann.co.uk/celestion_cdx1_1445.htm) listed £47 including VAT, with a 4–5 week wait. [PETG](https://uk.elegoo.com/collections/tiered-bulk-sale-filament/products/rapid-petg-filament-1-75mm-colored-1kg) listed £16/kg. Recheck availability before ordering.

CAD assembly material volume is 3.795 L. Assuming solid PETG at 1.27 kg/L gives 4.82 kg, or about 5.78 kg with 20% process allowance. This is a planning estimate, not a slicer result; supports, infill and failed parts can change consumption. Six spools may not cover repeated prototypes.

Interface dimensions come from the [FaitalPRO specification](https://faitalpro.com/en/products/LF_Loudspeakers/product_details/index.php?id=401000150) and [Celestion specification](https://celestion.com/product/cdx1-1445/). Manufacturer sensitivity and frequency ranges are not predictions for this horn. Nominal frame fit is modelled; the actual cone profile, screw engagement and gasket compression must be checked on hardware.

## Assembly and first checks

1. Print both fit coupons. Verify the mid cutout and four holes on the 92 mm pitch circle, plus the HF throat and bolt pattern. Select screw lengths using actual flange thickness and driver thread depth. Inspect cone-to-transition clearance throughout excursion.
2. Slice the core, 24 sectors and four rear covers. Check overhang support and usable print area in the slicer. Use airtight walls and adequately solid flanges; settings require a material/printer test. Remove internal support and smooth the air path.
3. Build each eight-sector band using its external seam ribs. Join the three bands to the core through the split flanges. The manifest records exact assembly placement. Use M4 hardware through the 4.5 mm holes, washers and a sealing method compatible with PETG. Dry fit before bonding; avoid steps or adhesive inside the horn.
4. Gasket and install all four mids, with their cones facing the horn. Fit the four rear covers and seal the two wire passages in each. Fit and gasket the throat tweeter. Support the mouth and throat externally; the assembly has not been structurally load-tested.
5. Four nominal 8-ohm mids can form two identical series pairs connected in parallel, for a nominal 8-ohm bank. Maintain identical acoustic polarity. Drive the tweeter through its own appropriate filtered amplifier channel.
6. An initial DSP topology to investigate is fourth-order Linkwitz–Riley high-pass at 240 Hz and low-pass at 3000 Hz for mids, with a corresponding 3000 Hz HF high-pass. This is not a tuned preset. Gains, delays, polarity, protection and EQ require measurements; do not apply unfiltered full-range power to the tweeter.

## Validation before calling it successful

Geometry checks passed on R1: valid single CAD solids per print part, reconstruction volume error below 1 ppm, no modelled rear-cover intersections with each other/body/HF envelope, individual build envelopes below 250 mm, and closed oriented positive-volume STL meshes. These checks do not establish print strength, airtightness, real driver clearance or acoustic accuracy.

The next useful milestone is an instrumented prototype. Record the exact driver samples and assembled geometry. Measure each driver impedance free-air and mounted, inspect for leaks, then measure individual mid entries, the combined mid bank and HF separately with a calibrated microphone. Use gated measurements where valid and an appropriate outdoor/ground-plane or merged method at 240 Hz; do not treat a short indoor gate as low-frequency evidence. Measure on-axis response, multiple horizontal/vertical angles, impedance and distortion at declared levels. Save raw data, microphone distance, environment, voltage and calibration. Compare against a coupled model of the actual ring geometry before tuning it.

Before optimisation, declare response, directivity, sensitivity and maximum-output targets with the user. As provisional prototype screening only, investigate whether the combined system can cover 240–3000 Hz within ±3 dB after practical crossover/EQ without narrow cancellation nulls, excessive excursion or distortion. This is a proposed acceptance test, not an achieved result. In particular, port spacing, front cavities, throat reflections and interference at 3 kHz may force a different entry position, smaller ports or another crossover choice. Mesh convergence and comparison to an independent solver are necessary numerical checks; physical data is required to establish acoustic accuracy.

## Reproduce

From the repository with its CAD dependencies installed:

```sh
PYTHONPATH=src python designs/240hz-3khz-four-driver/generate.py --output /path/to/new-output-directory
```

Use a new output directory and retain failed attempts. R1 was generated with CadQuery 2.8 and checked with the repository export validator. `generate.py` is a standalone prototype generator; it does not add this ring configuration to the optimisation CLI.

## Front air domain for analysis

`acoustic_domain.py` now exports the R1 horn interior, including its 8 mm throat flange bore and four wall-normal port transitions. The checked-in `analysis-preparation/front-air.step` and `front-domain.json` retain the first successful run. It is one connected 44.433 L CAD air volume, with zero intersection against the original printed horn material. Six planar interfaces (mouth, throat and four mids) were independently identified by centre, area and outward normal; the saved STEP passed a volume round-trip check. This is a useful input to meshing, not a solved speaker model.

```sh
PYTHONPATH=src python designs/240hz-3khz-four-driver/acoustic_domain.py --output /path/to/new-analysis-directory
```

The mid interfaces terminate at the mounting plane, using the 74.6 mm aperture. This area is larger than the driver's effective piston area: do not connect catalogue Sd directly as if the aperture were the diaphragm. Actual cone/front-cavity geometry or a validated equivalent source coupling is still needed. Rear domains, tagged FEM mesh generation, driver coupling and exterior radiation remain to connect before simulation of this prototype. The existing general `meh` geometry/search CLI remains unchanged.

### Tagged front mesh

`mesh_front.py` converts the saved STEP to metres, identifies all six interfaces by centre and area, and exports a linear tetrahedral mesh with `mouth`, `throat`, `mid_1`–`mid_4`, `rigid_walls` and `front_air` physical groups. It verifies input CAD identity, imported volume, positive saved tetrahedral volumes and interface areas. Failed attempts retain a failure manifest in their new output directory.

```sh
PYTHONPATH=src python designs/240hz-3khz-four-driver/mesh_front.py --source designs/240hz-3khz-four-driver/analysis-preparation --output /path/to/new-mesh-directory --size-m 0.015
```

The original run is in [mesh-15mm.zip](analysis-preparation/mesh-15mm.zip), with a readable [manifest](analysis-preparation/mesh-15mm.json). At a 15 mm maximum size with curvature refinement it contains 228,551 tetrahedra. The integrated mesh volume differs from CAD by 0.0391%; all six interface area errors are below 1%. This establishes mesh construction and tagging only. It is one resolution, with no convergence or acoustic result. The archived manifest binds the exact generator, input STEP and domain manifest hashes. A later prescribed-source solve can investigate transfer behaviour, but must not be described as a validated prediction for the purchased drivers.

The review-fixed mesher additionally records `rigid_walls` in the boundary manifest and rejects estimated workloads over two million tetrahedra before generating the mesh. Its heuristic is `6 * CAD volume / size³ + 250000`, with the final actual-count guard retained; this is not a guaranteed memory bound. The 5 mm setting is rejected before meshing, with a failure manifest and runtime cleanup verified. The [review-fixed archive](analysis-preparation/mesh-15mm-review-fixed.zip) and [manifest](analysis-preparation/mesh-15mm-review-fixed.json) contain the new executed 15 mm run; all seven boundary declarations exactly match the saved mesh physical groups. Use these for subsequent solver integration. The earlier archive is retained unchanged for provenance.

### Prescribed-flow diagnostic (experimental)

`transfer_fem.py` assembles linear tetrahedral Helmholtz FEM directly with NumPy/SciPy (install SciPy in addition to the CAD dependencies). It drives the four mid mounting apertures with equal prescribed inward volume flows, holds the throat rigid, and terminates the mouth with local plane-wave impedance rho*c. Phasors use exp(+i omega t); total RMS flow is 0.0001 m³/s. Output is complex mean pressure at the mouth and transfer per total flow, **not far-field SPL, sensitivity or an actual driver response**. Local mouth impedance omits exterior diffraction/radiation; rear chambers and electrical driver loads are omitted. This intentionally limited diagnostic precedes full coupled FEM/BEM integration.

```sh
PYTHONPATH=src python designs/240hz-3khz-four-driver/check_transfer_tube.py --output /path/to/new-tube-check
PYTHONPATH=src python designs/240hz-3khz-four-driver/transfer_fem.py --source /path/to/extracted-review-fixed-mesh --output /path/to/new-transfer --frequencies 240 1000 3000
```

The independent reference is a 100 mm long uniform tube, with a 20 mm square section and the same impedance termination. Its exact complex mouth pressure is rho*c*Q/area times exp(-ikL). The 4 mm mesh comparison passed a declared 2% complex-error gate at 240, 1000 and 3000 Hz: errors were 0.0013%, 0.0468% and 1.1751%, respectively; linear residuals were below 5e-13. The retained [tube check](analysis-preparation/transfer-tube-validation.json) tests FEM assembly, phasor sign and flow normalization in this elementary case. It does not establish accuracy for the R1 horn or validate the mouth approximation.

The [first R1 diagnostic run](analysis-preparation/transfer-first.json) completed at 240, 1000 and 3000 Hz in about 50 seconds on the retained 228,551-tetrahedron mesh. All solves passed the 1e-7 linear residual gate. These three complex transfer samples demonstrate execution on the actual four-entry air domain; they are insufficient to assess passband ripple, convergence or speaker performance. The next numerical checks are a denser sweep and mesh refinement, followed by a physically appropriate radiation/source coupling model.

The [review-fixed tube check](analysis-preparation/transfer-tube-review-fixed.json) adds exact solver/checker/mesh hashes, geometry, medium, flow convention and the 2% gate. It preserves partial samples and a failed status before raising. The gate uses an unconditional comparison, so Python's optimized mode cannot remove it. A separate injected zero-pressure response was rejected as 100% error under `python -O`, with the failing sample and identities retained. The original bare-list report remains unchanged as historical evidence; use the self-describing report for validation provenance. The R1 solver itself did not change, so its original three-frequency result was not rerun.

### Frequency sweep and refinement screen

The [17-point diagnostic](diagnostics/sweep-summary.json) combines the original endpoints with 15 additional log-spaced samples, preserving both source reports. The magnitude of the **complex mouth-area mean transfer** spans 20.14 dB, with a sampled minimum at 1595.5 Hz. It is not a predicted far-field speaker response; spatial averaging and the approximate termination matter.

A predeclared comparison from 15 mm to 10 mm maximum mesh size required both ≤1 dB magnitude change and ≤10% relative complex change at three samples around that minimum and at 3000 Hz. [The screen failed](diagnostics/refinement-comparison.json): the three mid-band samples passed (2.38–5.68% complex changes), while 3000 Hz changed by 24.10% in complex transfer despite only 0.003 dB magnitude change. Therefore the sampled dip persists in this diagnostic, but the 3 kHz phase cannot yet be treated as mesh-stable. No limits were relaxed. The [10 mm mesh archive](diagnostics/mesh-10mm.zip) and [raw result](diagnostics/transfer-10mm.json) preserve the experiment. The third mesh result below investigates the failed screen; this is still not full radiation or commercial-driver validation.


The [7.5 mm comparison](diagnostics/third-mesh-comparison.json) also **fails** the unchanged 10% complex gate at 3000 Hz: the change from 10 mm is 10.208%, with only 0.0025 dB magnitude change. Its [raw transfer](diagnostics/transfer-7p5mm.json) and [verified mesh archive](diagnostics/mesh-7p5mm.zip) are retained. This is not rounded down to a pass. The decreasing change suggests improvement, but three nonuniform mesh levels and one high-frequency sample do not justify an extrapolated convergence claim.

Further refinement of this simplified termination is deferred while the more material model gaps are addressed: exterior radiation, finite driver/source coupling and rear loads. The next implementation should expose a valid radiation/source model and its assumptions before optimising geometry against this internal-pressure diagnostic. The mechanical STL remains an unqualified prototype.


To reproduce the diagnostic solver and figures in a clean environment, install the declared extras with `pip install -e '.[cad,diagnostics]'`. Then run `diagnostics/summarize_sweep.py`, `diagnostics/compare_refinement.py` and `diagnostics/compare_third_mesh.py` from this design directory. The two-level comparison resolves the original plan's textual selection (three retained samples nearest 1.6 kHz plus 3 kHz) to exact sweep frequencies, records them, and rejects omitted or duplicate samples. The original descriptive rounded frequency list and all raw numerical runs remain unchanged.

### Historical exterior-radiation smoke

The actual R1 meshes subsequently completed a four-source prescribed-velocity
FEM/BEM solve at 240 Hz. [Raw fields and reproduction notes](radiation-evidence/README.md)
are retained separately from the earlier locally terminated FEM curve. This
single-frequency integration result has a rigid throat and no commercial driver
or rear-load model; it does not qualify R1's target band.
