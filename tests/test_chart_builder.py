import unittest
import os
from app.agents.chart_builder import ChartBuilder

class TestChartBuilder(unittest.TestCase):
    """Tests Matplotlib visualization exports."""

    def test_line_chart_generation(self):
        """Verifies line chart PNG gets created on disk."""
        records = [
            {"year": "2020", "value": 10.0},
            {"year": "2021", "value": 12.0},
            {"year": "2022", "value": 14.0}
        ]
        paths = ChartBuilder.generate_line_chart(
            records=records,
            x_field="year",
            y_field="value",
            title="Salem Level Projections",
            session_id="test_chart"
        )
        self.assertEqual(len(paths), 1)
        self.assertTrue(os.path.exists(paths[0]))
        
        # Clean up
        try:
            os.remove(paths[0])
        except Exception:
            pass

if __name__ == "__main__":
    unittest.main()
