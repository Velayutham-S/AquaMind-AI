import unittest
from app.agents.retrieval_explainer import RetrievalExplainer

class TestRetrievalExplainer(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            {
                "text": "Salem recharge details in 2024 monitoring well guidelines.",
                "metadata": {
                    "district": "Salem",
                    "category": "Resource Assessment",
                    "title": "GEC Report 2024"
                },
                "score": 0.85,
                "bm25_score": 12.4,
                "rerank_score": 4.2
            },
            {
                "text": "Tamil Nadu Groundwater Act 2003 guidelines for aquifers.",
                "metadata": {
                    "district": None,
                    "category": "Regulations & Policy",
                    "title": "Groundwater Act 2003"
                },
                "score": 0.70,
                "bm25_score": 8.1,
                "rerank_score": 2.9
            }
        ]

    def test_explanations_reporting(self):
        """Verifies explanation structure, scores, ranks, and metadata reports."""
        exps = RetrievalExplainer.explain(self.chunks, "recharge guidelines in Salem 2024")
        
        self.assertEqual(len(exps), 2)
        
        # Check Rank 1
        exp1 = exps[0]
        self.assertEqual(exp1["rank"], 1)
        self.assertEqual(exp1["similarity_score"], 0.85)
        self.assertEqual(exp1["bm25_score"], 12.4)
        self.assertEqual(exp1["cross_encoder_score"], 4.2)
        self.assertEqual(exp1["priority_category"], "Resource Assessment")
        self.assertEqual(exp1["document"], "GEC Report 2024")
        
        # Check matched entities
        self.assertIn("Salem", exp1["matched_entities"])
        self.assertIn("2024", exp1["matched_entities"])
        self.assertIn("Recharge", exp1["matched_entities"])
        
        # Check Rank 2
        exp2 = exps[1]
        self.assertEqual(exp2["rank"], 2)
        self.assertEqual(exp2["priority_category"], "Regulations & Policy")
        self.assertIn("Highest reranker score", exp1["reason_selected"])

if __name__ == "__main__":
    unittest.main()
