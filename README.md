# MEH Design Studio

Design, optimise and manufacture affordable, efficient, high-fidelity multiple entry horn speakers from a curated driver database and a set of acoustic, budget and printing constraints.

**Status: experimental foundation tools. There is no complete design application or validated speaker design yet.** The feasibility study has explicit gates before the full product can be qualified.

## Try the foundation tools

Requires Python 3.11 or newer. From the repository root:

```sh
python -m venv .venv
# Activate .venv using your shell's standard activation command.
python -m pip install -e ".[dev]"
meh validate-brief examples/reference-brief.json
meh cavity-reference --lengths-m 0.47 0.33 0.22 --max-hz 1000
python -m pytest
```

The command-line tools validate an explicit design brief, manage immutable private driver imports in SQLite, and generate analytic cavity reference data. The Python API also provides an independent coupled electromechanical circuit reference using RMS amplitudes and `exp(-i omega t)`.

A [Boundary Lab adapter](docs/boundary-lab-adapter.md) also runs existing projects using a separately installed pinned solver; its interior-FEM integration smoke test has been executed. The independent references do not simulate a 3D horn, and a syntactically valid brief is not evidence of an achievable speaker. The example brief remains a proposed challenge. See [implementation status and next steps](docs/implementation-status.md).

Experimental horn CAD and tagged air meshing are available through [the geometry generator](docs/geometry-generator.md). These exports remain unverified for printing and acoustic performance.

## Documents

| Document | Purpose |
| --- | --- |
| [Product requirements](docs/product-requirements.md) · [original Word edition](docs/MEH_Design_Studio_PRD.docx) | Product scope, architecture, optimisation, catalogue and printable outputs |
| [Feasibility report](docs/feasibility-report.md) | Evidence, critical unknowns, cost and compute sensitivity, proceed/narrow/stop decisions |
| [Implementation plan](docs/implementation-plan.md) | Work packages, dependencies, deliverables and acceptance gates |
| [Validation strategy](docs/validation-strategy.md) | Numerical verification, independent comparisons, physical tests and optimisation evaluation |
| [Validation data plan](docs/validation-data-plan.md) | Available evidence, data acquisition, qualification, rights and holdout policy |
| [Upstream evidence review](docs/research/upstream-review.md) | Pinned Boundary Lab revision and inspected fixture limitations |
| [Dataset registry](validation/dataset-registry.json) | Machine-readable list of planned and externally available evidence |
| [Measurement record template](validation/measurement-template.json) | Fields to complete before measurements become qualifying evidence |
| [Decision log](docs/decisions.md) | Proposed defaults, unresolved decisions and change policy |

The proposed system uses one parametric design to generate acoustic domains and printable solids. A versioned Boundary Lab adapter performs coupled simulations; a budgeted mixed-variable search selects driver models, supported counts, geometry, entry positions and active crossover settings. Finalists undergo common-fidelity numerical checks and manufacturing verification.

Validation is the critical path. Catalogue specifications alone cannot establish loaded high-frequency source behaviour, distortion, print leakage or wall motion. The evidence programme must establish where the predictions are trustworthy before broad optimisation is useful.

## Reading and evidence conventions

The PRD describes the product vision. The implementation and validation documents refine its delivery sequence; where they tighten a test procedure, use the newer procedure. All acceptance thresholds, prices and schedules are proposed planning assumptions, not demonstrated outcomes. The original planning reports did not execute the solver. Subsequent [integration evidence](docs/boundary-lab-adapter.md) records real interior-FEM runs. No physical measurement data has been collected by this project.

The registry currently contains **references and acquisition plans**, not a bundled driver database or a completed validation corpus. No third-party meshes, measurement curves or driver scans are redistributed here. The original Word PRD is retained as an archival edition; subsequent planning refinements are in Markdown.

## Licensing

Repository visibility is private. A distribution licence has not yet been selected. The proposed application direction is GPL-compatible, with driver data licensed separately. See [decisions](docs/decisions.md). References to external software or data do not grant permission to redistribute them.

Experimental single-trace measurement import is available through `meh-measurements`; see [formats, preserved evidence and limits](docs/measurement-import.md). The bundled example is synthetic and importing data does not qualify it.
