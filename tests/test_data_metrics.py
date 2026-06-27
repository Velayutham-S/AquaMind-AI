import unittest
from app.database import SessionLocal, init_db
from app.agents.data_metrics import DataMetrics

class TestDataMetrics(unittest.TestCase):
    """Tests execution tracking and SQL execution plan auditing."""

    def setUp(self):
        init_db()
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_explain_plan_audit(self):
        """Verifies indexes auditing dynamically using SQLite explain queries."""
        tracker = DataMetrics.start_tracking()
        
        # Build simple select statement to explain
        sql = "SELECT id, district FROM district_assessments WHERE district = :district"
        params = {"district": "SALEM"}
        
        metrics = DataMetrics.stop_tracking(
            db=self.db,
            sql_str=sql,
            params=params,
            start_state=tracker,
            rows_returned=5
        )
        
        self.assertIn("total_latency_ms", metrics)
        self.assertIn("rows_scanned", metrics)
        self.assertEqual(metrics["rows_returned"], 5)
        self.assertIsInstance(metrics["indexes_used"], list)

if __name__ == "__main__":
    unittest.main()
