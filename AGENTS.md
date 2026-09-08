# Builder instructions

This repository is the public branch for the AXM Factual Star Adventure Simulator.

## Preserve the architecture

- Keep deterministic simulation records independent from replaceable visuals.
- Do not rewrite prior expedition history, root commitments, event ledgers or evidence ceilings.
- Do not edit generated files under `output/` as a substitute for changing their source.
- Keep normal local operation free of mandatory cloud, account or AI dependencies.
- Declare missing verification capability; never manufacture a passing receipt.

## Required verification

After an intentional package change:

1. Run `python tools/reseal_package.py --write`.
2. Run `run_local_acceptance.bat` on Windows or `./run_local_acceptance.sh` on POSIX.
3. Run `run_github_pr_plan.bat` and review its exact digest and changed paths.
4. Publish only with `run_github_pr_publish.bat <reviewed-plan-digest>`.

Never push changes directly to `main`. The publisher refuses deletions, credentials, stale plan digests, failed verification and branches outside `automation/`.

## Detail-density and composable capability principle

Quality is often the accumulated result of many small correct details, not one large generic upgrade.

- When improving a system, look for missing small, bounded capabilities, checks, parameters, passes, and repair operations that control specific details or failure modes.
- Prefer many reusable, inspectable, composable capabilities over one opaque "make it better" step when the smaller capabilities create real control or evidence.
- A machine should remain useful without AI: humans, explicit state, recipes, or deterministic logic can invoke the same capabilities directly.
- With AI, the model is primarily an interpretation and orchestration layer: it translates a higher-level goal into selections and combinations of the same underlying capabilities. The AI does not own those capabilities.
- A better reasoning model may improve goal interpretation and composition, while the underlying machine remains portable and usable without that model.
- Judge improvement by accumulated perceptual or functional detail, coherence, failure reduction, and fit to the goal—not by model size, resolution, benchmark score, or one broad upgrade alone.
- For visual, game, asset, animation, and video work, pay attention to small interacting details such as material variation, contact, timing, weight, secondary motion, lighting response, sound layering, asymmetry, wear, scale cues, camera behavior, and continuity.
- Do not fragment working systems merely for ideology. Add granularity where it creates useful control, reuse, diagnosis, repair, or quality.

**Working rule:** thousands of small good details and capabilities in the right places can improve a result more than one simple big upgrade.

## Canonical state and adaptive realization principle

Keep factual/simulation truth separate from the manifestation chosen for a particular machine.

- Deterministic simulation records, expedition history, evidence ceilings, rules, and committed state are authoritative; visual/audio/UI realizations are replaceable expressions.
- Preserve expression intent when useful so scientific/semantic detail, hierarchy, readability, atmosphere, and interaction meaning survive lower rendering budgets.
- Prefer one canonical adventure body with multiple bounded realization contracts over divergent platform-specific truths.
- Choose realization from canonical state + expression intent + measured machine capabilities + user policy, at launch or dynamically when appropriate.
- A weak device should receive cheaper expression, **not weaker factual or simulation truth**.
- Never degrade evidence integrity, historical records, causal meaning, core functionality, privacy, or authoritative state for rendering cost.
- Never let a lossy render/cache overwrite richer canonical records. Projection is not authority.
- Richer realizations may expose more existing state/intent; they may not invent factual/canonical state simply to look better.
- Apply this split only where representation can honestly remain subordinate to canonical records.

**Working rule:** degrade expression, never truth; upgrade expression, never invent truth.
