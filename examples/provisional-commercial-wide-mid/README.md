# Provisional commercial-driver wide-mid experiment

This runnable input set selects four FaitalPRO 4FE32 16-ohm mid circuits sharing
one amplifier voltage and a separately driven, derived Peerless DFM-2535R00-08
ideal-outlet approximation. Neither source is qualified in this horn. The
Peerless approximation fails the retained conditional 3 dB tube-response screen;
see the [source audit](../../docs/research/commercial-hf-source-audit.md).

The seed is a 300 mm long, 440 mm nominal-mouth freeform horn with a four-driver
ring, periodic cubic profiles and linked quarter-turn profile mutations. The
four-proposal search allows profile scales from 0.65 to 1.5 and varies geometry,
port and cavity controls within the declared bounds. It evaluates 15 frequencies
from 350 to 7500 Hz, two polar cuts and a sphere at 20 m. The 3–5 kHz acoustic
handover and 2-ohm sampled parallel-bank screen remain enabled. The nominal
parallel bank is 4 ohms; this does not qualify a specific amplifier.

The £300 planning ceiling includes four £30 mid allowances, a £60 HF allowance,
material and £55 other costs. These are not supplier quotes. The seed's idealised
source disks and cavities do not supply real cone, phase-plug, motor, gasket or
bolt interfaces. This input set has passed catalogue/candidate/bounds validation;
**its commercial-source native search has not yet been executed**. Historical
synthetic-HF results are not predictions of this new circuit.

For substantially different axial and cross-section shapes, the
[curved starting inputs](curved/README.md) provide separate exponential-round
and quadratic rounded-square cases with two-proposal briefs. These are
unqualified starting points whose generated solver geometry has been checked.

From the repository root, after installing the package with its CAD dependencies
and the [pinned native runtime](../../docs/boundary-lab-adapter.md):

```sh
meh catalogue init runs/commercial-wide-mid.sqlite
meh catalogue add runs/commercial-wide-mid.sqlite examples/reported-drivers/faitalpro-4fe32-16.json
meh catalogue add runs/commercial-wide-mid.sqlite examples/reported-drivers/peerless-dfm2535-8-ideal-outlet.json
meh optimise examples/provisional-commercial-wide-mid/brief.json \
  --geometry examples/provisional-commercial-wide-mid/geometry.json \
  --database runs/commercial-wide-mid.sqlite \
  --output runs/commercial-wide-mid \
  --checkout runs/runtime/boundary-lab \
  --python runs/runtime/blab-env/bin/python \
  --julia runs/runtime/julia-1.12.6/bin/julia \
  --backend coupled_reference --julia-threads 2 \
  --timeout-per-solver-stage-s 7200
```

Use the native runtime's configured Julia depot. These are full-size native
experiments and may take hours; the timeout is per solver stage. Preserve failed
trials. A completed search selects its best feasible sampled result, even when
that result misses the separate 6 dB response-variation screen. Completion is
not acoustic acceptance.

Only after a search completes successfully:

```sh
meh operating-report runs/commercial-wide-mid --input-rms-v 1 \
  --output runs/commercial-wide-mid-1vrms.json
meh export-search runs/commercial-wide-mid --output runs/commercial-wide-mid.zip
```

These commands verify source and result identities and retain the selected DSP.
Operating reports distinguish outlet air motion from physical HF diaphragm
motion. The ZIP is an experimental geometry/BOM/DSP bundle, not a print-qualified
or Solana-equivalent design. Physical-source validation, held-out frequency and
mesh checks, manufacturing interfaces and assembled-speaker measurements remain
required before accepting the final horn.
