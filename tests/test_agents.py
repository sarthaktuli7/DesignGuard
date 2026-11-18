"""
Unit tests for DesignGuard's agent pipeline.
Run with: python3 -m unittest tests/test_agents.py -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents import TriageAgent, ResolutionAgent, QAAgent, EscalationAgent, POLICY
from app.retrieval import PrecedentRetriever
from app.llm_resolution import llm_available


class TestTriageAgent(unittest.TestCase):
    def setUp(self):
        self.agent = TriageAgent()

    def test_score_returns_expected_shape(self):
        element = {
            "deviation": 0.3, "prior_exceptions_count": 0, "is_high_visibility": 0,
            "violation_type": "non_standard_spacing", "severity": "cosmetic",
        }
        result = self.agent.score(element)
        self.assertIn("merit_score", result)
        self.assertIn("confidence", result)
        self.assertIn("top_factors", result)
        self.assertTrue(0.0 <= result["merit_score"] <= 1.0)
        self.assertTrue(0.0 <= result["confidence"] <= 1.0)
        self.assertEqual(len(result["top_factors"]), 5)

    def test_large_deviation_lowers_merit_score(self):
        base = {"prior_exceptions_count": 0, "is_high_visibility": 0,
                "violation_type": "off_palette_color", "severity": "brand_critical"}
        low_dev = self.agent.score({**base, "deviation": 0.1})
        high_dev = self.agent.score({**base, "deviation": 0.9})
        self.assertLessEqual(high_dev["merit_score"], low_dev["merit_score"] + 0.05)


class TestRetrieval(unittest.TestCase):
    def setUp(self):
        self.retriever = PrecedentRetriever()

    def test_retrieve_returns_list(self):
        results = self.retriever.retrieve(
            "Needed tighter spacing here to fit content on smaller screens.",
            "non_standard_spacing", "cosmetic",
        )
        self.assertIsInstance(results, list)

    def test_similarity_capped_at_one(self):
        results = self.retriever.retrieve(
            "Client asked for this exact brand color for the campaign launch.",
            "off_palette_color", "brand_critical",
        )
        for r in results:
            self.assertLessEqual(r["similarity"], 1.0)

    def test_no_precedent_returns_empty_not_error(self):
        results = self.retriever.retrieve("asdkjfh qwerty nonsense gibberish", "off_palette_color", "cosmetic")
        self.assertIsInstance(results, list)


class TestResolutionAgentFallback(unittest.TestCase):
    """Without ANTHROPIC_API_KEY set, ResolutionAgent must use the deterministic
    path and never raise - the default state for anyone cloning the repo."""

    def setUp(self):
        self.agent = ResolutionAgent()

    def test_falls_back_to_deterministic_without_api_key(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        self.assertFalse(llm_available())

        element = {
            "designer_note": "Needed tighter spacing here to fit content on smaller screens.",
            "violation_type": "non_standard_spacing", "severity": "cosmetic",
        }
        triage_result = {"merit_score": 0.6, "confidence": 0.4}
        result = self.agent.draft(element, triage_result)

        self.assertEqual(result["method"], "deterministic")
        self.assertIn("recommended_action", result)
        self.assertIn("grounded", result)


class TestQAPolicyGate(unittest.TestCase):
    def setUp(self):
        self.qa = QAAgent()

    def test_brand_critical_always_blocked(self):
        element = {"severity": "brand_critical", "is_high_visibility": 0, "prior_exceptions_count": 0}
        triage = {"confidence": 0.99}
        resolution = {"grounded": True}
        result = self.qa.review(element, triage, resolution)
        self.assertTrue(result["policy_blocked"])
        self.assertTrue(any("brand-critical" in r for r in result["block_reasons"]))

    def test_high_visibility_always_blocked(self):
        element = {"severity": "cosmetic", "is_high_visibility": 1, "prior_exceptions_count": 0}
        triage = {"confidence": 0.99}
        resolution = {"grounded": True}
        result = self.qa.review(element, triage, resolution)
        self.assertTrue(result["policy_blocked"])

    def test_low_confidence_blocked(self):
        element = {"severity": "cosmetic", "is_high_visibility": 0, "prior_exceptions_count": 0}
        triage = {"confidence": 0.10}
        resolution = {"grounded": True}
        result = self.qa.review(element, triage, resolution)
        self.assertTrue(result["policy_blocked"])

    def test_ungrounded_resolution_blocked(self):
        element = {"severity": "cosmetic", "is_high_visibility": 0, "prior_exceptions_count": 0}
        triage = {"confidence": 0.95}
        resolution = {"grounded": False}
        result = self.qa.review(element, triage, resolution)
        self.assertTrue(result["policy_blocked"])

    def test_low_risk_case_passes_all_gates(self):
        element = {"severity": "cosmetic", "is_high_visibility": 0, "prior_exceptions_count": 0}
        triage = {"confidence": 0.95}
        resolution = {"grounded": True}
        result = self.qa.review(element, triage, resolution)
        self.assertFalse(result["policy_blocked"])
        self.assertEqual(result["block_reasons"], [])


class TestEscalationAgent(unittest.TestCase):
    def setUp(self):
        self.escalation = EscalationAgent()

    def test_blocked_routes_to_human_review(self):
        status = self.escalation.route({}, {"policy_blocked": True})
        self.assertEqual(status, "pending_human_review")

    def test_unblocked_routes_to_auto_resolved(self):
        status = self.escalation.route({}, {"policy_blocked": False})
        self.assertEqual(status, "auto_resolved")


if __name__ == "__main__":
    unittest.main(verbosity=2)
