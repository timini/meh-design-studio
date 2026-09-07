# MEH Design Studio

Design, optimise and manufacture affordable, efficient, high-fidelity multiple entry horn speakers from a curated driver database and a set of acoustic, budget and printing constraints.

**Status: research and implementation planning. There is no working application or validated speaker design in this repository yet.** The recommended next step is a four-week feasibility study, with explicit gates before funding the full product.

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

The PRD describes the product vision. The implementation and validation documents refine its delivery sequence; where they tighten a test procedure, use the newer procedure. All acceptance thresholds, prices and schedules are proposed planning assumptions, not demonstrated outcomes. No upstream acoustic solver was executed for these reports, and no physical measurement data has been collected by this project.

The registry currently contains **references and acquisition plans**, not a bundled driver database or a completed validation corpus. No third-party meshes, measurement curves or driver scans are redistributed here. The original Word PRD is retained as an archival edition; subsequent planning refinements are in Markdown.

## Licensing

Repository visibility is private. A distribution licence has not yet been selected. The proposed application direction is GPL-compatible, with driver data licensed separately. See [decisions](docs/decisions.md). References to external software or data do not grant permission to redistribute them.
