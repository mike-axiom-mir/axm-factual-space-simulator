from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GitHubPullRequestLaneTests(unittest.TestCase):
    def test_publisher_keeps_review_and_merge_authority_human(self) -> None:
        source = (ROOT / "tools" / "New-VerifiedPullRequest.ps1").read_text(encoding="utf-8")
        self.assertIn("PUSH VERIFIED FACTUAL SPACE PR", source)
        self.assertIn("$PlanDigest -ne $plan.planDigest", source)
        self.assertIn("Deletion, rename and copy status", source)
        self.assertIn("run_local_acceptance.bat", source)
        self.assertIn("'--draft'", source)
        self.assertIn("directMainPush = $false", source)
        self.assertIn("mergeAuthority = $false", source)
        self.assertNotIn("gh pr merge", source.lower())
        self.assertNotIn("git push origin main", source.lower())

    def test_ci_is_read_only_and_cross_platform(self) -> None:
        source = (ROOT / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", source)
        self.assertIn("contents: read", source)
        self.assertIn("windows-latest", source)
        self.assertIn("ubuntu-latest", source)
        self.assertIn("tools/reseal_package.py --check", source)
        self.assertIn("unittest discover", source)


if __name__ == "__main__":
    unittest.main()
