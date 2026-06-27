import unittest
from unittest.mock import patch
from app.supervisor.planner import Planner

class TestExplainablePlanner(unittest.TestCase):
    """Tests the explainable reasoning capabilities of the Supervisor Planner."""

    def test_planner_generates_reasoning_keys(self):
        """Verifies that the planner output JSON structure contains the reasoning array."""
        query = "Forecast groundwater stage for Coimbatore by 2030."
        classification = "prediction"
        entities = {"location": "COIMBATORE", "year": "2030"}

        # Mock LLM response to assert JSON output formats correctly
        mock_response = {
            "intent": "prediction",
            "reasoning": [
                "User requested prediction for Coimbatore by 2030.",
                "PredictionAgent is selected to perform trend regressions.",
                "DataAgent is selected to fetch Coimbatore historical records."
            ],
            "language": "English",
            "entities": {"location": "COIMBATORE", "year": "2030"},
            "agents": ["DataAgent", "PredictionAgent"],
            "tools": [],
            "response_type": "text",
            "confidence": 0.90
        }

        with patch("app.agents.llm.LLMService.call_json", return_value=mock_response):
            # Bypass cache to force compilation
            with patch("app.supervisor.planner_cache.PlannerCache.get_cached_plan", return_value=None):
                with patch("app.supervisor.planner_cache.PlannerCache.set_cached_plan") as mock_cache:
                    plan = Planner.plan(query, classification, entities)
                    
                    self.assertIn("reasoning", plan)
                    self.assertIsInstance(plan["reasoning"], list)
                    self.assertGreater(len(plan["reasoning"]), 0)
                    self.assertEqual(plan["intent"], "prediction")
                    self.assertIn("PredictionAgent", plan["agents"])

    def test_planner_fallback_generates_reasoning(self):
        """Verifies that the fallback plan generated during exception contains reasoning details."""
        query = "Invalid query triggering error"
        
        # Patch call_json to raise an exception
        with patch("app.agents.llm.LLMService.call_json", side_effect=ValueError("LLM Failure")):
            with patch("app.supervisor.planner_cache.PlannerCache.get_cached_plan", return_value=None):
                plan = Planner.plan(query, "general", {})
                
                self.assertIn("reasoning", plan)
                self.assertIsInstance(plan["reasoning"], list)
                self.assertTrue(any("Fallback" in r or "LLM Failure" in r for r in plan["reasoning"]))

if __name__ == "__main__":
    unittest.main()
