# Explicit double-precision coupled backend

`solve-project`, `optimise` and `resume-optimise` accept
`--backend coupled_reference`. This selects the pinned upstream CPU FP64
FEM/BEM backend through the packaged `native_reference.py` runner. The default
remains `beat_cpu`. The reference requires a coupled interior/exterior project;
it is not an alternative exterior-only or interior-only backend.

For an existing generated coupled project:

```sh
meh solve-project PROJECT/system/project.blab.json \
  --request REQUEST.json --output NEW_REFERENCE_EVALUATION \
  --checkout BOUNDARY_LAB_CHECKOUT --python BOUNDARY_LAB_PYTHON \
  --julia JULIA_EXECUTABLE --backend coupled_reference --julia-threads 4
```

Use the same backend flag with `meh optimise` to generate, mesh, solve, score and
export a search using FP64 results. Resume requires the original backend, thread
count, runner hash and application/runtime identities. It cannot silently switch
a partially completed FP32 campaign to FP64. Start a separate study for that
comparison and preserve both sets of evidence.

The finalist and partitioned-validation scripts inherit the saved search backend
and thread setting by default. Both accept explicit `--backend` and
`--julia-threads` options. The partitioned validator still requires the complete
runtime identity to match the search. An explicit backend override in the
standalone finalist validator creates a separate numerical comparison, with its
own recorded runtime; no existing results are relabelled.

The adapter runs the upstream CPU preflight, then the explicit reference runner.
It holds static condensation enabled, matching the existing precision-reference
study. Runtime records identify FP64, the runner SHA256 and effective thread
count (four by default for this backend). Result inspection requires complex128
storage for every quantity and verifies the retained reference-runtime file.
The runner and request identities are checked before accepting the result;
timeouts and cancellations use the same managed subprocess boundary as other
solves. Progress is in `solve.ndjson`; native diagnostics are in
`solve.stderr.log`. The older standalone fixture remains available for replay of
its historical validation workflow.

Double precision makes the existing strict electrical checks applicable; it
does not guarantee that they pass. The
[earlier freeform reference study](freeform-reference-study.md) still fails the
unchanged reciprocity tolerance. Mesh error, physical source accuracy and
manufacturing suitability are separate checks. No physical qualification is
granted by selecting this backend. FP64 also requires more memory and CPU time;
use it deliberately for numerical validation and bounded searches.

The [executed five-driver integration study](reference-backend-evidence.md)
demonstrates a complete FP64 search and verified export, retaining its actual
electrical results and acoustic limitations.
