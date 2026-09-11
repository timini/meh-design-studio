# Simulation-driven freeform mutation

Set `SearchBrief.evolution` to enable a seeded `(mu+1)` evolutionary strategy.
The first declared feasible candidate is the baseline. Following each completed
native FEM/BEM evaluation, the search ranks successful trials by the declared
objective and mutates one of the retained elites. Every fourth proposal by default
explores randomly. Failures are excluded from elite selection and remain recorded.

Each profile has eight radial controls per axial section. Mutations can also
change declared bounds on horn length, mouth radius, port radius/length,
front/rear cavity depth and axial entry fractions. Catalogue alternatives can
change the driver source circuits, with disk areas and total driver cost recomputed.
A candidate without a freeform profile acquires three controlled sections when
mutated. Source circuits remain present in every voltage-basis solve.

`evolution` controls: `elite_size`, `explore_every`, `mutation_fraction`,
`sigma_fraction`, `profile_scale_bounds` and `geometry_bounds`. Bounds are hard
limits for seeds and offspring. Each generation uses a seed derived from the
saved search seed and trial index. New proposals depend on **preceding simulated
fitness**; this is not a preshuffled list of predetermined cones.

`search.json` retains parent indices, actual control changes and rejected invalid
proposals. Each accepted candidate has its own CAD, meshes, solver fields, score
and source identities. The solver trial budget counts failed trials as well as
successful ones; up to 64 cheap parameter proposals are attempted per slot, with
all rejected parameter records retained. This is a bounded heuristic search and
has no global-optimum guarantee.

Export and finalist validation reconstruct the winner from the saved fitness and
proposal history and verify its candidate identity. Resume reuses verified whole
completed trials and preserves earlier failed trials unchanged, because retrying
them could alter every later proposal. It retries the interrupted trial and
continues the remaining budget in a new directory. The original search remains
required evidence. Resume rejects changed runtime, controls or proposal history.

The current objective remains the existing relative on-axis ripple/cost metric;
this increment establishes adaptive geometry search. Explicit horizontal/vertical
coverage, crossover filters and common-amplifier load scoring are next. Numerical
holdouts and mesh refinement remain required before accepting a winner. Synthetic
experiments do not qualify commercial drivers or measured loudspeaker performance.
