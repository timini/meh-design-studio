# Experimental end-to-end search

`meh optimise` runs a finite, seeded search over catalogue driver choices, symmetric
entry-pair count, horn length, mouth radius and entry fractions. Every candidate
that reaches scoring has generated CAD, tagged volume meshes, a conformed exterior,
and a real Boundary Lab FEM/BEM voltage-basis evaluation. Relative side-driver gain
is selected by complex superposition of that basis. Drivers stay coupled, including
sources with zero excitation in the individual basis solves.

This is a numerical pipeline demonstrator, not a qualified speaker designer. The
included search records and prices are invented synthetic fixtures, not products
or procurement advice. The current family supports three or five ideal drivers
and straight conical paths. Driver count and driver-only cost are hard constraints.
The objective is on-axis peak-to-peak response ripple plus an explicitly weighted
cost term. It does not claim acoustic efficiency, calibrated SPL, a global optimum,
nonlinear headroom, structural performance or print qualification.

The search saves its brief, catalogue records, candidate parameters, solver outputs,
failed attempts and scores. `search.json` identifies the winning completed trial;
`winner-geometry` contains its original STEP/STL export and geometry manifest.
The geometry remains subject to the limitations in that manifest. A completed search
is separate from `numerical_consistency_passed` and physical qualification.
Complex64 results cannot pass the strict complex128-only electrical check; scoring
can inspect them experimentally, retaining that unsupported-precision outcome.

Example (use the external runtime paths from the adapter guide):

```sh
meh optimise examples/synthetic-search-brief.json \
  --geometry examples/three-driver-geometry.json --database drivers.sqlite \
  --checkout /path/to/boundary-lab --python /path/to/blab-env/bin/python \
  --julia /path/to/julia --output runs/search
```

Populate the private catalogue with the records in
`examples/synthetic-search-drivers.json` using the catalogue API. Prices in the
brief are all in its declared currency and exclude material, electronics and labour.
Set `JULIA_DEPOT_PATH` to an absolute path when using a separate Julia depot.

Validation must use fresh generated reference fixtures, repeat the finalist with
fixed drive settings on a denser frequency grid and at multiple mesh resolutions,
and retain failing results. Passing software tests alone does not validate acoustics.
Current executed evidence will be recorded separately after those runs finish.

## Reproduce the denser validation experiment

The original three-point search can miss response peaks between samples. Use
`examples/synthetic-dense-search-brief.json` for 17 whole-hertz frequencies from
500 to 2000 Hz. These remain a finite experimental grid, not a guarantee of
continuous-band performance. After the search completes, freeze its winner:

```sh
python validation/fixtures/validate_search_finalist.py runs/search runs/finalist \
  --checkout /path/to/boundary-lab --python /path/to/blab-env/bin/python \
  --julia /path/to/julia
```

This repeats the selected horn at 8, 6 and 4 mm interior mesh sizes (when the base
size is 8 mm), using the search frequencies and rounded geometric midpoints.
The selected side gain remains fixed. Native frequency result labels lose
precision for irrational midpoint frequencies, so this experiment requests
explicit whole-hertz midpoints and retains exact request/result label checks.
The original failed noninteger-frequency evaluation is retained in the run evidence.

Successive **raw complex pressure** differences must stay within 0.5 dB and
5 degrees at every sampled frequency. There is no gain or phase fit between
mesh levels. The rigid-exterior target size is fixed, but the conforming BEM mouth interface
changes with the FEM mesh. This tests combined interior/interface sensitivity,
not independent full exterior convergence. Canonical CAD identity is held fixed. The report separately records electrical validation,
independent closed-edge/orientation/volume checks of the exported STL parts,
and the absence of physical or print qualification. A completed validation
command can still contain failed acceptance gates; read `validation.json`.
