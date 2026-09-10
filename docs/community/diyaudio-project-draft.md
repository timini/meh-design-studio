# Draft — not posted

Publication remains conditional on the project/design evidence being ready.
Update the results and links after the current larger-horn search and validation.
Do not post this internal status line.

Suggested title: **Open-source MEH shape optimisation with inexpensive mids — seeking modelling and design feedback**

I'm developing [MEH Design Studio](https://github.com/timini/meh-design-studio),
an open-source workflow for designing a shared multi-entry horn with several
inexpensive mid drivers and a separate HF driver. The practical goal is a
mid/high top meeting an X1/HD15 system around 350 Hz, with the mid bank covering
as much of the vocal range as it can cleanly manage. I'm exploring roughly
3–5 kHz upper crossovers and a GBP 300 horn/driver/hardware budget, excluding
amplification and the bass system.

JW Sound's Solana work is an important functional reference, particularly the
attention to coverage and the interaction between profile and entry geometry.
Credit to JW Sound and the contributors to the
[Solana project thread](https://www.diyaudio.com/community/threads/solana-project-thread.439795/).
This is a separate software/design experiment, not a claim to have reproduced
Solana or matched its measured performance.

The workflow generates one consistent CAD model for horn air, entry ducts,
front chambers, rear loads and material parts. It supports four mids around one
ring, plus the HF throat, and smooth noncircular/asymmetric profiles. Each
candidate goes through mesh generation and a full coupled FEM/BEM calculation
using the pinned [Boundary Lab](https://github.com/JWSound/boundary-lab)
solver by JW Sound. The project builds on that solver rather than claiming a
new acoustic formulation.

Each driver is an electromechanical source with induced motion retained when
another driver is excited. The optimiser mutates profiles and dimensions,
selects using simulated response and H/V coverage, and periodically tries a
random candidate. Saved results include failures, parentage, meshes, complex
pressure/current/velocity bases and the selected geometry export. Four parallel
mids share one voltage and one amplifier channel; their input load includes
mutual coupling. HF crossover, polarity and delay are evaluated from the full
basis and frozen for subsequent checks.

There is some useful numerical evidence, but the limits matter. An analytical
pulsating-sphere check passed a predeclared 2% complex-pressure criterion across
four samples from 350 to 7,500 Hz, with a maximum discrepancy of 0.708%. An early
four-proposal target-band shape search reduced response variation from 13.17 to
11.81 dB, which is still unacceptable as a finished design. The wider search is
using reported FaitalPRO mid parameters; its HF circuit remains an explicitly
synthetic placeholder. No purchased-driver calibration or physical horn
measurements have been completed. A strict electrical reciprocity check also
remains unresolved, and the experimental print geometry still uses ideal driver
interfaces rather than qualified baskets, cone clearances, seals and mounts.

The present software can report predicted pressure, excursion, coil loss and
amplifier current at a stated RMS input. Those reports are linear single-tone
predictions, not maximum-SPL ratings or limiter recommendations.

I'd particularly value feedback on:

- A practical measurement method for deriving the HF driver's loaded source
  model at its exit, including source impedance and phase, without pretending
  that a datasheet SPL curve fully characterises a compression driver.
- How best to represent inexpensive cone drivers and their front chambers near
  a 3–5 kHz crossover, and where rigid-piston assumptions become misleading.
- Useful acceptance tests for port resonances, coverage and mesh convergence,
  and comparison measurements that would make results credible and repeatable.
- Commercial mid/HF combinations worth investigating within this budget.

The intent is to make both successful and failed experiments reproducible, and
to turn community feedback into better modelling and a build that can be tested.

<!-- Internal publication note: the in-app browser reached diyAudio on
10 September 2026 and showed Log in/Register, with no authenticated session.
Posting will need the maintainer's signed-in session when the write-up is ready.
No forum message, account creation or upload has been submitted. -->
