import unittest
from app.agents.data_confidence import DataConfidence

class TestDataConfidence(unittest.TestCase):
    """Tests the structured dynamic confidence score computation."""

    def test_calculate_confidence(self):
        """Verifies weighted calculation and parameter mappings."""
        records = [
            {"year": "2024-2025", "value": 10.0, "status": "Safe"},
            {"year": "2024-2025", "value": None, "status": "Safe"}
        ]
        
        # Test Case: Exact Match Location, SQL complete, missing values (50%), freshness (100%)
        # weights: loc (30%)*1.0 + sql (30%)*1.0 + missing (20%)*0.833 + freshness (20%)*1.0
        # elements = 6, null = 1. missing = 5/6 = 0.8333333333333334
        # score = 0.30 + 0.30 + 0.16666 + 0.20 = 0.96666
        
        res = DataConfidence.calculate(
            resolved_location_type="district",
            is_exact_location=True,
            sql_built_successfully=True,
            records=records,
            year="2024-2025"
        )
        
        self.assertAlmostEqual(res["confidence_score"], 0.96666666, places=4)
        self.assertEqual(res["location_resolution"], 1.0)
        self.assertEqual(res["sql_completeness"], 1.0)
        self.assertAlmostEqual(res["missing_values"], 0.8333333, places=4)
        self.assertEqual(res["dataset_freshness"], 1.0)

if __name__ == "__main__":
    unittest.main()
