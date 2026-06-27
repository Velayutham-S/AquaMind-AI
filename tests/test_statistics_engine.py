import unittest
from app.agents.statistics_engine import StatisticsEngine

class TestStatisticsEngine(unittest.TestCase):
    """Tests basic, moving averages, YoY changes, and regression slope calculations."""

    def test_basic_statistics(self):
        """Verifies basic aggregate metrics: min, max, average, and percentiles."""
        records = [
            {"value": 10.0},
            {"value": 20.0},
            {"value": 30.0},
            {"value": 40.0}
        ]
        stats = StatisticsEngine.calculate_basic_stats(records, "value")
        self.assertEqual(stats["count"], 4)
        self.assertEqual(stats["min"], 10.0)
        self.assertEqual(stats["max"], 40.0)
        self.assertEqual(stats["mean"], 25.0)
        self.assertEqual(stats["median"], 25.0)
        self.assertEqual(stats["percentiles"][75], 32.5)

    def test_yoy_growth(self):
        """Verifies Year-over-Year percentage change calculations."""
        records = [
            {"year": "2020", "value": 100.0},
            {"year": "2021", "value": 150.0},
            {"year": "2022", "value": 120.0}
        ]
        growth = StatisticsEngine.calculate_yoy_growth(records, "value")
        self.assertEqual(len(growth), 3)
        self.assertEqual(growth[1]["yoy_growth_pct"], 50.0) # 100 -> 150
        self.assertEqual(growth[2]["yoy_growth_pct"], -20.0) # 150 -> 120

    def test_trend_direction(self):
        """Verifies regression trend slope mapping."""
        # Increasing trend
        records = [
            {"year": "2020", "value": 10.0},
            {"year": "2021", "value": 12.0},
            {"year": "2022", "value": 14.0}
        ]
        trend = StatisticsEngine.calculate_trend(records, "value")
        self.assertEqual(trend["direction"], "increasing")
        self.assertGreater(trend["slope"], 0.0)

if __name__ == "__main__":
    unittest.main()
