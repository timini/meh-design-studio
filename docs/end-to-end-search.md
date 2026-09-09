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
Each midpoint must lie strictly inside its search interval. Closely spaced grids
that collapse after rounding are rejected before native E2E work or finalist validation,
so every interval contributes a distinct held-out sample.
The original failed noninteger-frequency evaluation is retained in the run evidence.

Successive **raw complex pressure** differences must stay within 0.5 dB and
5 degrees at every sampled frequency. There is no gain or phase fit between
mesh levels. The rigid-exterior target size is fixed, but the conforming BEM mouth interface
changes with the FEM mesh. This tests combined interior/interface sensitivity,
not independent full exterior convergence. Canonical CAD identity is held fixed. The report separately records electrical validation,
independent closed-edge/orientation/volume checks of the exported STL parts,
and the absence of physical or print qualification. A failed mesh comparison stops the remaining levels and returns a failure, while
preserving the completed levels and their differences in `validation.json`.
Electrical consistency remains a separate reported gate.

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
Replay verifies the winning evaluation digest and the original referenced solver
artifacts before accepting its frozen gain, and checks them again at completion.
The current finalist validator rejects older, unbound searches; reproduce them
with a fresh search to obtain evidence under the current integrity contract.

### Partitioned native CI

CI first runs the independent tube reference and the complete 17-frequency search.
Search-only mode rejects grids with fewer than 17 validation frequencies before
starting native work, because every partition must contain a sample. Unrelated PR
labels have separate concurrency groups and cannot cancel a requested native run.
It then evaluates the baseline and three frozen-winner meshes in seventeen frequency
partitions each (68 jobs, at most two frequencies per solve). A final job reads
and verifies every raw result, requires exact frequency coverage and identical
mesh hashes within each level, and combines raw complex pressures before scoring.
It never normalises individual partitions. The 33 frequencies, 8/6/4 mm meshes,
0.5 dB / 5-degree limits and 1 dB held-out improvement requirement are unchanged.

This avoids placing every fine-mesh frequency into one long CI job. The search
stage permits two hours for each native solver stage, and each partition uses the same stage limit;
a timeout remains a failure. The general CLI defaults to 30 minutes per solver stage;
`--timeout-per-solver-stage-s` accepts an explicit limit up to 7200 seconds.
The `native-search`, `native-partition-*` and `native-assembled` artifacts retain
the separate stages. An assembled success requires all partitions to succeed.
Artifact paths are restored under the same runner temporary directory because
the pinned solver records absolute mesh paths; raw files are never rewritten to
change those identities. The sequential local runner remains available.

The evidence runners require a clean checkout and the same source commit across
search, partition workers and assembly. Dirty or changed sources are rejected.

### Compact benchmark

The label-triggered native workflow uses `synthetic-compact-search-brief.json` and
`compact-three-driver-geometry.json`: four candidates with 120/125 mm paths,
100 mm mouth diameter, and 17 search frequencies from 1000 to 4000 Hz. Validation
uses 33 frequencies and the same 8/6/4 mm maximum mesh sizes and acceptance limits.
It uses the same synthetic driver catalogue. This is a separate, smaller numerical
benchmark, not a successful result for the larger 500–2000 Hz experiment.
Manual workflow dispatch offers `full-size` for the larger benchmark. The local
runner accepts `--brief` and `--geometry`; omitting them retains the original
full-size defaults. The smaller case reduces the cost of complete pipeline testing.

Solver timeouts apply separately to preflight and the native solve. They do not
bound CAD generation, meshing, or total candidate wall time; CI job timeouts
provide an outer bound. The compact benchmark uses a 10 mm exterior target after
the initial 20 mm target failed the unchanged 2% CAD-volume agreement gate.

### Recover completed native solves after a runner setup failure

`Replay retained native horn evidence` downloads the original search and all
partitions and runs only assembly. Supply the source run ID and the exact
`source_commit` from its experiment report. It checks out that original source,
restores the original runner paths and applies the original integrity and numerical
gates. It does not rerun, rewrite or rescore the optimisation with new settings.
The replay run and original run must both be cited when reporting the result.
The initial replay defaults recover run 34370258164, whose assembly setup failed
on an unrelated Chrome repository checksum mismatch after all solves completed.
