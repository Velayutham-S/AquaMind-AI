import unittest
from unittest.mock import patch
from app.agents.answer_evaluator import AnswerEvaluator

class TestAnswerEvaluator(unittest.TestCase):
    def setUp(self):
        self.context = [{"text": "Groundwater recharge in Salem block is 25 ham."}]
        self.grounding = {"grounding_score": 1.0}

    def test_evaluator_high_quality(self):
        """Verifies evaluator behaves correctly when answer is complete and grounded."""
        mock_eval = {
            "answer_complete": True,
            "missing_topics": [],
            "missing_entities": [],
            "contradictions": [],
            "citation_quality": "HIGH",
            "grounding_quality": "HIGH",
            "needs_retry": False,
            "evaluation_score": 0.95
        }
        with patch("app.agents.llm.LLMService.call_json", return_value=mock_eval):
            res = AnswerEvaluator.evaluate(
                "What is the Salem recharge?",
                "The groundwater recharge in Salem block is 25 ham [1].",
                self.context,
                self.grounding
            )
            self.assertEqual(res["evaluation_score"], 0.95)
            self.assertFalse(res["needs_retry"])

    def test_evaluator_missing_evidence_trigger_retry(self):
        """Verifies that missing evidence or low scores trigger needs_retry."""
        mock_eval = {
            "answer_complete": False,
            "missing_topics": ["recharge rate"],
            "missing_entities": ["Salem"],
            "contradictions": [],
            "citation_quality": "LOW",
            "grounding_quality": "LOW",
            "needs_retry": True,
            "evaluation_score": 0.65
        }
        with patch("app.agents.llm.LLMService.call_json", return_value=mock_eval):
            res = AnswerEvaluator.evaluate(
                "What is the Salem recharge?",
                "Recharge is normal in the state.",
                self.context,
                self.grounding
            )
            self.assertEqual(res["evaluation_score"], 0.65)
            self.assertTrue(res["needs_retry"])

    def test_grounding_trigger_retry(self):
        """Verifies that a low grounding score overrides and forces a retry."""
        mock_eval = {
            "answer_complete": True,
            "missing_topics": [],
            "missing_entities": [],
            "contradictions": [],
            "citation_quality": "HIGH",
            "grounding_quality": "HIGH",
            "needs_retry": False,
            "evaluation_score": 0.95
        }
        with patch("app.agents.llm.LLMService.call_json", return_value=mock_eval):
            # Pass a low grounding score of 0.5
            res = AnswerEvaluator.evaluate(
                "What is the Salem recharge?",
                "The groundwater recharge in Salem block is 25 ham [1].",
                self.context,
                {"grounding_score": 0.5}
            )
            self.assertTrue(res["needs_retry"])

if __name__ == "__main__":
    unittest.main()
