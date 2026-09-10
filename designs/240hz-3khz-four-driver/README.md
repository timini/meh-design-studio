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
