# Validation data and acquisition plan

7 September 2026 · No project-owned physical dataset acquired yet

## What exists today

The [registry](../validation/dataset-registry.json) contains references and planned acquisitions with explicit status. The Boundary Lab revision is pinned in the [upstream review](research/upstream-review.md). Public examples and manufacturer downloads are candidate evidence sources, not a ready-to-ship driver catalogue.

| Dataset | Available evidence | Intended use | Gap before qualification |
| --- | --- | --- | --- |
| Noncubic cavity | Upstream geometry family, analytical description, mesh-density study notes | Modal and mesh-dispersion regression | Independently regenerate reference values; execute at pinned revision; audit fixture rights |
| Interface/symmetry fixtures | Upstream meshes and fixture inventory | Mesh compiler and symmetry regression | Independent full/symmetric comparisons; no implied physical accuracy |
| Compression-driver example | Front/rear FEM model and one-frequency request | Coupling and headless integration smoke test | Broadband independent oracle and loaded source measurements |
| CRAM on-axis measurement | Public measured trace and setup notes | Exploratory response-shape comparison | No voltage calibration; not absolute efficiency, full polar or MEH release evidence |
| Dayton ND91-4 assets | Manufacturer specs and linked acoustic/nonlinear/geometry downloads | Catalogue discovery and discrepancy checklist | Permission, exact revision, sample measurements, source model and provenance |
| Owned source/load campaign | Planned | Calibrate and independently test driver loading | Purchase, fixture, calibration, lab time and measurements |
| Owned printed MEH campaign | Planned | Physical model, assembly repeatability and optimisation validation | Build and measure baseline, family replicates and nominated improvement |

A public plot with no phase, drive level, geometry or measurement window is useful context but cannot become a calibrated transfer function. Manufacturer measurements on different baffles cannot be pooled as equivalent training samples. Store original conditions and reject unsupported transformations.

## Acquisition sequence and minimum scope

**Weeks 1–2:** reserve measurement access; choose one affordable midrange and one HF source, plus an alternate midrange if practical. Obtain at least three samples per first source model for an initial variation check. Obtain datasheet revision, dimensions and a written rights decision for any intended bundled material. Characterise electrical impedance and build two known load fixtures. Gate geometry before paying for full directivity acquisition.

**Weeks 2–4:** calibrate the source model on load A; freeze it; predict load B. Acquire one fully documented baseline MEH at low level and a small level sweep. Freeze a first complete input-to-result record. If procurement or laboratory scheduling prevents this, mark G0 pending and revise elapsed time; documentation alone cannot substitute.

**Vertical slice and search phases:** add alternate entry position/duct dimensions and known perturbations to challenge prediction. Grow records by qualification value, not spreadsheet row count. Identify two families for the beta programme and retain calibration designs separately from evaluation designs.

**Beta:** minimum two independently printed samples in each of two families, including the least-expensive qualified driver set. Measure at least one baseline and one optimiser-proposed improvement blind to predictions; plan an additional design/build beyond the four-unit minimum when the chosen finalist differs. Budget spare drivers and failed prints. Cover fit, leakage, reassembly, low-level response/polars and level behaviour.

**Catalogue release:** proposed minimum 30 real model identities, at least six band-qualified source records sufficient for two useful families, each with rights and provenance. Count by immutable physical model/variant, not duplicate retailer offers. A full installed reference search must work offline. Missing rights or qualifying records blocks PR02 even if the importer works perfectly.

## Calibration, development and holdout split

Split by physical design family, driver batch and measurement session where feasible, not by individual frequency bins. Adjacent frequencies, angles from one sweep and two copies of the same build are correlated evidence. They must not be presented as thousands of independent examples.

Use calibration data for source and loss fitting. Use development data for geometry and solver debugging. Reserve a blind holdout design/load for each initial family, plus a nominated optimisation candidate measured only after its prediction is frozen. A second unit of a calibration design tests repeatability; it does not by itself test geometry generalisation.

The dataset steward owns holdout labels and release of measurements. With a tiny team, timestamped hashes and an independently witnessed measurement freeze provide a practical separation. After a failure is inspected and used to tune the model, that case becomes development data; preserve its failed original result and commission a fresh holdout before claiming unbiased evaluation.

Never train surrogate performance estimates on final holdout responses. Uncertainty calibration also consumes data; reserve independent checks of interval coverage and avoid declaring nominal coverage from the same samples used to fit it.

## Record contract and storage

Use the [measurement template](../validation/measurement-template.json) as a human-fillable contract draft, not an implemented schema validator. `null` means missing; it is never equivalent to zero, a default or a passing result. A qualifying ingestion service must reject missing claim-critical fields.

Each acquisition package shall contain:

- A manifest with stable dataset/design/sample IDs, state, protocol, operator/reviewer, timestamps, validity band/level, split, rights and provenance.
- Exact CAD and acoustic geometry revisions, as-built deviations, driver serials/batches, print material/profile, assembly/repair log and photos where rights permit.
- Raw time signals or original instrument exports; complex impedance and pressure arrays with axes, units, RMS/peak convention, voltage basis, timing reference, angular coordinates and termination states.
- Instrument serial/calibration IDs, calibration files/hashes, microphone position/orientation, amplifier and interface settings, air conditions, window/noise information and preconditioning history.
- Processing recipe/version, exclusions with reasons, uncertainty budget, derived metrics and a signed review decision. Preserve all raw originals.

CSV is suitable for exchange; complex arrays in versioned HDF5 or an equivalent documented array format are authoritative once ingested. Use explicit frequency × excitation × observation dimensions with real/imaginary fields or a specified complex encoding. Distinguish instrument calibration from DUT model fitting.

Store small manifests and protocols in Git. Store large raw datasets in versioned object storage or managed large-file storage, with SHA-256 digests, size and retrieval instructions in the manifest. Select the storage provider only after ownership, access and backup needs are known. Never commit expiring signed access URLs or credentials. Retain raw evidence for all released qualification claims and archive derived versions instead of overwriting them.

## Ingestion quality gates

Check finite values, monotonic frequency arrays, duplicate bins, explicit units, sample count/shape, response reference, geometry identity and checksum integrity. Do not require every trace to be passive if it describes an actively processed transfer; apply impedance/passivity checks only to the declared physical domain.

Review clipping, noise floor, repeated-run drift, voltage calibration, angular registration, timing consistency and the valid band. Flag physically inconsistent catalogue relationships such as Sd × Xmax versus displacement volume, mass convention mismatch and revision-dependent mounting dimensions. Preserve conflicting original values and their sources; a reviewer resolves the model, rather than a parser silently choosing one.

Qualification additionally needs a documented claim, suitable independent comparison, allowable uncertainty, test report and reviewer. Rights clearance and acoustic qualification are separate fields. An excellent private measurement can qualify a user's private model while remaining ineligible for the public pack.

## Ownership and effort

| Role | Accountable work |
| --- | --- |
| Acoustics lead | Source identification, validity bands, reference equations, model discrepancy |
| Measurement lead | Calibration, acquisition, raw evidence, repeatability and holdout handling |
| CAD lead | Geometry truth, as-built dimensions, print and assembly records |
| Data/application lead | Ingestion, immutable versions, catalogue release and checksums |
| Product owner | Scope, test levels, cost assumptions and rights decisions |

One person may hold multiple roles, but holdout evaluation and final qualification should receive a second review. The first feasible data milestone is one calibrated source pair and one reproducible MEH record, not a large unqualified web scrape.
