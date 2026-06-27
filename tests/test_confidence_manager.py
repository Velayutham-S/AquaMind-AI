import unittest
from unittest.mock import patch
from app.supervisor.confidence_manager import ConfidenceManager
from app.config import Config

class TestConfidenceManager(unittest.TestCase):
    """Tests the dynamic weighted confidence manager with normalisation and tiering."""

    def setUp(self):
        # Save baseline configuration weights to restore after test runs
        self.baseline_weights = dict(Config.SUPERVISOR_CONFIDENCE)

    def tearDown(self):
        # Restore configuration
        Config.SUPERVISOR_CONFIDENCE = self.baseline_weights

    def test_weighted_confidence_calculation(self):
        """Verifies mathematical weighted confidence calculation is correct under normal conditions."""
        Config.SUPERVISOR_CONFIDENCE = {
            "retrieval": 0.35,
            "sql": 0.20,
            "prediction": 0.20,
            "reranker": 0.15,
            "planner": 0.10
        }
        
        plan_agents = ["DataAgent", "KnowledgeAgent", "PredictionAgent"]
        agent_results = {
            "KnowledgeAgent": {
                "confidence_score": 0.96,
                "reranker_score": 0.91
            },
            "DataAgent": {
                "confidence_score": 1.00
            },
            "PredictionAgent": {
                "confidence_score": 0.88
            }
        }
        plan_confidence = 0.95
        
        # Expected:
        # Retrieval = 0.96 (w = 0.35)
        # SQL = 1.00 (w = 0.20)
        # Prediction = 0.88 (w = 0.20)
        # Reranker = 0.91 (w = 0.15)
        # Planner = 0.95 (w = 0.10)
        # Overall = 0.35*0.96 + 0.20*1.00 + 0.20*0.88 + 0.15*0.91 + 0.10*0.95 = 0.9435
        # Level = "HIGH"
        
        result = ConfidenceManager.compute_overall_confidence(plan_agents, agent_results, plan_confidence)
        
        self.assertAlmostEqual(result["overall_confidence"], 0.9435, places=4)
        self.assertEqual(result["confidence_level"], "HIGH")
        self.assertEqual(result["confidence_breakdown"]["planner"], 0.95)
        self.assertEqual(result["confidence_breakdown"]["retrieval"], 0.96)
        self.assertEqual(result["confidence_breakdown"]["sql"], 1.00)
        self.assertEqual(result["confidence_breakdown"]["prediction"], 0.88)
        self.assertEqual(result["confidence_breakdown"]["reranker"], 0.91)

    def test_dynamic_weight_redistribution(self):
        """Verifies that weights are dynamically normalized to sum up to 100% when components are missing."""
        Config.SUPERVISOR_CONFIDENCE = {
            "retrieval": 0.35,
            "sql": 0.20,
            "prediction": 0.20,
            "reranker": 0.15,
            "planner": 0.10
        }
        
        # Only DataAgent and Planner active (No knowledge / prediction)
        plan_agents = ["DataAgent"]
        agent_results = {
            "DataAgent": {
                "confidence_score": 0.98
            }
        }
        plan_confidence = 0.90
        
        # Active components: "planner" (w=0.10), "sql" (w=0.20)
        # Sum active = 0.30
        # Normalised weights: planner = 0.10/0.30 = 0.333, sql = 0.20/0.30 = 0.667
        # Overall = 0.90*(0.3333333333333333) + 0.98*(0.6666666666666666) = 0.30 + 0.65333 = 0.95333
        # Level = "VERY HIGH"
        
        result = ConfidenceManager.compute_overall_confidence(plan_agents, agent_results, plan_confidence)
        
        self.assertAlmostEqual(result["overall_confidence"], 0.9533333, places=4)
        self.assertEqual(result["confidence_level"], "VERY HIGH")
        self.assertEqual(len(result["confidence_breakdown"]), 2)
        self.assertIn("planner", result["confidence_breakdown"])
        self.assertIn("sql", result["confidence_breakdown"])

    def test_tier_classifications(self):
        """Verifies that the correct classification tier is set based on confidence boundaries."""
        cases = [
            (0.96, "VERY HIGH"),
            (0.95, "VERY HIGH"),
            (0.90, "HIGH"),
            (0.85, "HIGH"),
            (0.80, "MEDIUM"),
            (0.70, "MEDIUM"),
            (0.65, "LOW")
        ]
        
        for score, expected_tier in cases:
            # We bypass calculations by only having planner active (w=1.0)
            Config.SUPERVISOR_CONFIDENCE = {"planner": 1.0}
            res = ConfidenceManager.compute_overall_confidence([], {}, plan_confidence=score)
            self.assertEqual(res["confidence_level"], expected_tier)

if __name__ == "__main__":
    unittest.main()
