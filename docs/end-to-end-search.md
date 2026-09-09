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
python validation/fixtures/create_synthetic_catalogue.py drivers.sqlite
meh optimise examples/synthetic-dense-search-brief.json \
  --geometry examples/three-driver-geometry.json --database drivers.sqlite \
  --checkout /path/to/boundary-lab --python /path/to/blab-env/bin/python \
  --julia /path/to/julia --output runs/search
```

The catalogue helper creates a new database from the records in
`examples/synthetic-search-drivers.json` and refuses to overwrite an existing database. Prices in the
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

The finalist runner allows up to two hours per native solve by default; use
`--solve-timeout-s` to set a shorter explicit limit. Fine conforming meshes can
be much more expensive than the search mesh. A timeout remains a failed run.

Finalist validation defaults to `--julia-threads 1` to reduce resource contention
on a desktop. The thread setting is recorded in each runtime identity and held
constant across validation levels. The search runtime may use the upstream
thread default; the validation repeats the coarse mesh with its own fixed setting.

## Opt-in native GitHub validation

The `Native horn end-to-end validation` workflow runs on Ubuntu when a maintainer
adds the `run-native-e2e` label to a pull request. Once merged, it can also be
started manually. It runs a fresh analytic tube comparison, the 17-frequency
horn search, an equal-gain baseline on the validation grid, and the frozen winner
at 33 frequencies and three mesh levels. This is separate from the fast platform
unit/CAD checks and is intentionally not triggered by every code push.

`validation/fixtures/run_native_e2e.py` runs the same experiment locally with
explicit checkout, Python and Julia paths. Its report separates pipeline success
from coupled electrical and physical qualification. Native errors or the declared
0.5 dB/5-degree mesh stability gate failing cause the job to fail. This particular
synthetic benchmark also requires at least 1 dB less ripple than the equal-gain
baseline on the held-out frequencies; this is an experiment criterion, not a
claim of hi-fi flatness. Partial outputs
are uploaded too, with seven-day artifact retention; archive important evidence
before it expires. A successfully completed numerical job never marks the
synthetic drivers or printed speaker as physically qualified.

New searches bind saved controls and the selected candidate in `search.json`.
The current finalist validator rejects older, unbound searches; reproduce them
with a fresh search to obtain evidence under the current integrity contract.
