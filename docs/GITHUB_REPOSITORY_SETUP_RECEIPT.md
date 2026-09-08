# GitHub repository setup receipt

Date: 2026-08-02

Repository: `mike-axiom-mir/axm-factual-space-simulator`  
Visibility: public  
Default branch: `main`  
Initial verified commit: `f7939f24faf970e32d65b561ec5b2f8eb1e41d70`

## Baseline evidence

Before the first public push:

- the package was scanned for common private-key and provider-token forms with zero findings;
- the largest canonical file was approximately 2 MB, below GitHub's 100 MB single-file refusal boundary;
- 272 canonical files and 168 generated outputs passed strict checksum verification;
- 226 tests completed with 225 passing and one Windows symlink fixture skipped for unavailable local privilege;
- the full local handoff audit passed;
- Git line endings were pinned so a Windows or POSIX checkout cannot silently invalidate package hashes.

## Future change route

The `main` branch is the reviewed baseline. Future builders make bounded changes locally, reseal the package, run the deterministic plan, and publish only to a digest-derived `automation/` branch. The fixed publisher reruns acceptance and opens a draft pull request. It cannot merge, promote or grant CANON authority.

This receipt is intentionally being delivered through the first draft pull request so the publication lane proves its own end-to-end behavior instead of merely claiming that it works.
