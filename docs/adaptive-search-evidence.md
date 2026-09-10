# Native adaptive freeform search

The [search report](../validation/evidence/adaptive-freeform/report.json) records
four proposals from the clean detached application source `2b21d93`, using
Boundary Lab's pinned coupled FEM/BEM solver. Every successful candidate was
exported, meshed and simulated at 1000, 2000 and 3000 Hz. Trial 0 is the declared
baseline; trial 1 mutates its profile/geometry; trial 2 mutates trial 1 after its
fitness improves. Trial 3 is seeded random exploration and fails the native
mouth-perimeter conformity check. The failed geometry and solver log remain in
its archive. No candidate was discarded from the recorded history.

| Trial | Selection | Sampled ripple | Outcome |
|---|---|---:|---|
| 0 | Declared baseline | 1.7380 dB | Complete |
| 1 | Mutate baseline | 1.6144 dB | Complete |
| 2 | Mutate trial 1 | 1.3303 dB | Selected |
| 3 | Random exploration | — | Interface meshing failed |

The objective includes an unchanged 0.4 cost penalty for the synthetic five-driver
bill. It is the earlier ripple/cost fitness, not the later wide-mid crossover and
directivity objective. These three samples demonstrate an actual geometry →
simulation → selection → mutation loop, not full-band superiority or a Solana
comparison. The synthetic models are not purchasable drivers.

Each trial archive preserves its CAD, meshes, source circuits, raw complex fields,
metadata, preflight and score/failure evidence. The controls archive contains the
brief, catalogue snapshot, full search/proposal history, launch script and the
successfully exported winner bundle. Export replays the adaptive history and
verifies every completed fitness ancestor before binding the selected CAD and BOM.

Strict electrical consistency remains unsupported by the production complex64
storage. The separate held-out-frequency/mesh-refinement experiment is not
reported here as passed. There is no physical, commercial-source or print
qualification. Archive hashes and exact sizes are recorded in the report.
