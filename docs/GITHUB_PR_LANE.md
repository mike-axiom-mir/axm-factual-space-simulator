# Deterministic GitHub pull-request lane

This repository includes a fixed local publisher so routine Git inventory, hashing, verification, committing, pushing and draft-PR creation do not require an AI to reason through every command again.

## Safety model

The publisher:

- works only in this exact Git repository;
- requires a credential-free `github.com` origin URL;
- derives a dedicated `automation/package-<manifest-hash>` branch;
- refuses direct `main` publication;
- refuses deletions and rename/copy status;
- refuses changed files over GitHub's 100 MB file limit;
- scans changed text for common credential and private-key forms;
- checks the deterministic package seal before producing a plan;
- binds the plan to Git HEAD, the manifest hash and every changed file hash;
- requires the exact reviewed plan digest and confirmation phrase;
- reruns full local acceptance before committing;
- opens a draft pull request and never merges it.

Git authentication remains in GitHub CLI or the operating system credential manager. AXM does not write a token into the repository.

## Routine flow

After making and resealing an improvement, build a read-only plan:

```text
run_github_pr_plan.bat
```

Review the reported paths and copy the 64-character `planDigest`. Publish that exact state:

```text
run_github_pr_publish.bat <planDigest>
```

On POSIX, invoke the PowerShell script with `pwsh` if available:

```text
pwsh -File tools/New-VerifiedPullRequest.ps1
pwsh -File tools/New-VerifiedPullRequest.ps1 -Publish -PlanDigest <planDigest> -Confirmation "PUSH VERIFIED FACTUAL SPACE PR"
```

If any file, manifest, Git HEAD, remote or verification result changes between planning and publication, the digest becomes stale and publication stops. Build and review a new plan.

After a pull request is reviewed and merged, return the local working copy to the new baseline before beginning another change:

```text
git switch main
git pull --ff-only
```

## First repository import

The first verified baseline is committed directly to `main` only while creating the empty repository. Every later improvement uses the pull-request lane above.
