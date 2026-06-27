import unittest
from app.database import SessionLocal, init_db
from app.agents.data_agent import DataAgent

class TestDataAgent(unittest.TestCase):
    """Integration tests verifying full DataAgent workflow and state outputs."""

    def setUp(self):
        init_db()
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_data_agent_workflow(self):
        """Verifies overall state inputs, validations, execution, and outputs compile correctly."""
        state_input = {
            "session_id": "test_agent_session",
            "query": "Groundwater stage in Salem for 2024-2025",
            "original_query": "Groundwater stage in Salem for 2024-2025",
            "resolved_location": "SALEM",
            "resolved_location_type": "district",
            "resolved_year": "2024-2025",
            "intent": "data",
            "response_type": "text",
            "routing_history": []
        }
        
        result = DataAgent.process(state_input)
        
        self.assertIn("context_data", result)
        self.assertIn("confidence_score", result)
        self.assertIn("citations", result)
        self.assertIn("response", result)
        self.assertGreater(result["confidence_score"], 0.5)

if __name__ == "__main__":
    unittest.main()
