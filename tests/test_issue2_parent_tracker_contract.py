import unittest
from pathlib import Path


MECHANICAL = Path("docs/specs/xauusd-s1-s4-mechanical-v1.md")
HANDOFF = Path("docs/specs/xauusd-s1-s4-research-handoff-v1.md")
AUDIT = Path("docs/handoff/2026-09-16-issues-3-4-local-acceptance-audit.md")
CLOSE_READY = Path("docs/handoff/2026-09-16-github-close-ready.md")


class Issue2ParentTrackerContractTests(unittest.TestCase):
    def test_mechanical_and_handoff_link_parent_issue_two(self):
        self.assertTrue(MECHANICAL.is_file())
        self.assertTrue(HANDOFF.is_file())
        mech = MECHANICAL.read_text()
        hand = HANDOFF.read_text()
        self.assertIn("issues/2", mech)
        self.assertIn("issues/3", mech)
        self.assertIn("issues/2", hand)
        self.assertIn("issues/4", hand)

    def test_local_audit_defines_parent_close_order(self):
        self.assertTrue(AUDIT.is_file())
        text = AUDIT.read_text()
        self.assertIn("Issue #2 parent", text)
        self.assertIn("#3", text)
        self.assertIn("#4", text)
        self.assertIn("Close on tracker **only after** #3 and #4", text)

    def test_close_ready_documents_github_close_sequence(self):
        self.assertTrue(CLOSE_READY.is_file())
        text = CLOSE_READY.read_text()
        self.assertIn("Issue #3", text)
        self.assertIn("Issue #4", text)
        self.assertIn("Issue #2", text)
        self.assertIn("Do NOT close yet", text)  # #1


if __name__ == "__main__":
    unittest.main()
