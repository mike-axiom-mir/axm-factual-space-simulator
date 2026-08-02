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
