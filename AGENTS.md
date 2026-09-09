# Working on MEH Design Studio

## Priorities

Deliver a working end-to-end horn design workflow: driver catalogue and constraints,
optimisation, generated geometry, real solver evaluation, numerical validation,
and usable geometry exports. Prioritise integration failures and evidence that
this workflow works over cosmetic changes, speculative edge cases, or expanding
process infrastructure.

Keep numerical claims honest. Preserve failed experiments, provenance and declared
acceptance limits. Distinguish a working numerical pipeline from acoustic accuracy,
physical measurements and print qualification. Do not weaken validation criteria
or present synthetic driver data as qualified commercial data to obtain a pass.

## Bounded pull-request review

- Request one review round per meaningful implementation increment, not per commit.
- Address material findings from that round: incorrect results, broken workflows,
  data loss, security issues, invalid evidence, or violations of agreed requirements.
- Check the fixes with relevant tests and direct inspection. Do not routinely request
  another review after fixes, documentation changes, or evidence updates.
- Defer cosmetic preferences, speculative hardening and unrelated improvements to
  follow-up work when they do not prevent the intended workflow from working.
- A further review is warranted only for a substantial change in scope or a newly
  identified serious risk. Explain the concrete reason before requesting it.
- An unavailable automated reviewer is not a reason for repeated review requests
  or an indefinite merge block. Record the limitation and inspect the change directly.
- With the maintainer's standing authorisation, merge after material findings are
  addressed and relevant checks pass. A fresh approval on every revised commit is
  not required. Never bypass a failing relevant check or a GitHub-enforced rule.

The maintainer has authorised autonomous implementation, pull requests and merges.
The one-round policy supersedes the earlier instruction to obtain repeated
current-head approval. Do not create a review loop for changes to these instructions.

## Execution and communication

Use the smallest meaningful checks for the change. Run expensive native experiments
when needed to establish numerical behaviour; preserve useful running experiments
when later changes do not affect their inputs or solver behaviour. Record the exact
source used rather than relabelling old results as runs of newer code.

Judge completion by the requested workflow and its evidence, not by the number of
reviews, tests or commits. Report concrete outcomes, remaining limitations and the
next material obstacle. Avoid repetitive progress messages that add no new information.
