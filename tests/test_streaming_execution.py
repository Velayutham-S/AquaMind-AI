import unittest
from unittest.mock import patch
from app.agents.graph import agent_graph
from app.supervisor.session_manager import SessionManager

class TestStreamingExecution(unittest.TestCase):
    """Tests the streaming execution progress indicators and timeline logging."""

    def test_progress_streaming_events(self):
        """Verifies that progress updates are emitted correctly through callbacks during execution."""
        session_id = "test_streaming_session"
        query = "What is the GEC recharge in Salem?"
        
        # Track callbacks
        events = []
        def callback(event_dict):
            events.append(event_dict)

        # Mock Planner to avoid actual LLM calls
        mock_plan = {
            "intent": "structured data",
            "reasoning": ["User requested Salem groundwater recharge."],
            "language": "English",
            "entities": {"location": "SALEM", "year": "2023-24"},
            "agents": ["DataAgent"],
            "tools": [],
            "response_type": "text",
            "confidence": 0.98
        }
        
        mock_eval = {
            "routing_accuracy": 1.0,
            "retrieval_precision": 1.0,
            "grounding_score": 0.99,
            "citation_accuracy": 1.0,
            "hallucination_detected": False,
            "language_accuracy": 1.0,
            "summary": "Mocked validation output summary."
        }
        
        def mock_call_json(prompt, system_prompt=None):
            if system_prompt and "Auditor" in system_prompt:
                return mock_eval
            return mock_plan

        def mock_call(prompt, system_prompt=None, json_mode=False):
            import json
            if json_mode:
                return json.dumps(mock_call_json(prompt, system_prompt))
            return "Mocked response text"

        # Mock database connection and response synthesis
        with patch("app.agents.llm.LLMService.call_json", side_effect=mock_call_json):
            with patch("app.agents.llm.LLMService.call", side_effect=mock_call):
                with patch("app.supervisor.planner.Planner.plan", return_value=mock_plan):
                    state_input = {
                        "session_id": session_id,
                        "query": query,
                        "original_query": query,
                        "language": "en",
                        "intent": "knowledge",
                        "resolved_location": None,
                        "resolved_location_type": None,
                        "resolved_year": None,
                        "context_data": None,
                        "context_knowledge": None,
                        "context_prediction": None,
                        "context_simulation": None,
                        "context_recommendations": None,
                        "context_analytics": None,
                        "chart_paths": [],
                        "map_html": None,
                        "pdf_report_path": None,
                        "routing_history": [],
                        "current_node": "supervisor",
                        "response": "",
                        "confidence_score": 0.0,
                        "confidence_reason": "",
                        "citations": [],
                        "evaluation": None
                    }
                    
                    # Invoke graph with config
                    config = {
                        "configurable": {
                            "progress_callback": callback
                        }
                    }
                    
                    agent_graph.invoke(state_input, config=config)
                    
                    # Assert callback events
                    self.assertGreater(len(events), 0)
                    
                    # Verify event structure
                    for e in events:
                        self.assertIn("time", e)
                        self.assertIn("stage", e)
                        self.assertIn("message", e)
                        self.assertIn("progress", e)
                        self.assertIsInstance(e["progress"], int)
                        self.assertTrue(10 <= e["progress"] <= 100)
                        
                    # Verify events timeline order
                    percentages = [e["progress"] for e in events]
                    self.assertEqual(percentages, sorted(percentages)) # Percentage must be monotonically increasing
                    
                    # Verify session persistence has timeline
                    sess = SessionManager.get_session(session_id)
                    self.assertIn("execution_timeline", sess)
                    self.assertIn("progress_events", sess)
                    self.assertIn("execution_status", sess)
                    self.assertEqual(sess["execution_status"], "completed")

if __name__ == "__main__":
    unittest.main()
