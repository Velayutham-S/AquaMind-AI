import unittest
from app.agents.graph import agent_graph
from app.supervisor.language_detector import LanguageDetector
from app.supervisor.spell_corrector import SpellCorrector
from app.supervisor.query_normalizer import QueryNormalizer
from app.supervisor.entity_extractor import EntityExtractor
from app.supervisor.query_classifier import QueryClassifier
from app.supervisor.planner import Planner
from app.supervisor.confidence_manager import ConfidenceManager
from app.supervisor.response_generator import ResponseGenerator
from app.supervisor.session_manager import SessionManager

class TestSupervisorAgent(unittest.TestCase):
    """Unit and integration test cases for the dynamic Supervisor Agent framework."""

    def test_language_detector(self):
        """Verifies correct language script detection (en vs ta vs mixed)."""
        self.assertEqual(LanguageDetector.detect("What is the groundwater status of Salem?"), "en")
        self.assertEqual(LanguageDetector.detect("சேலம் மாவட்ட நிலத்தடி நீர் நிலை என்ன?"), "ta")
        self.assertEqual(LanguageDetector.detect("kovai groundwater status detail epadi irukku?"), "mixed")

    def test_spell_corrector(self):
        """Verifies location typos are resolved correctly."""
        self.assertIn("Salem", SpellCorrector.correct("Show data for sallim district"))
        self.assertIn("Coimbatore", SpellCorrector.correct("kovai extraction status"))
        self.assertIn("Tiruchirappalli", SpellCorrector.correct("trichy guidelines"))

    def test_query_normalizer(self):
        """Verifies date ranges and units are normalized to standard formats."""
        self.assertEqual(QueryNormalizer.normalize("2024-25 report"), "2024-2025 report")
        # 2024 is mapped to standard GEC range "2023-2024"
        self.assertEqual(QueryNormalizer.normalize("status in 2024"), "status in 2023-2024")
        self.assertEqual(QueryNormalizer.normalize("extraction in hectare meters"), "extraction in ham")

    def test_query_classifier(self):
        """Verifies lightweight intent category mapping heuristics."""
        self.assertEqual(QueryClassifier.classify("hello there"), "General AI")
        self.assertEqual(QueryClassifier.classify("predict groundwater extraction by 2030"), "Prediction")
        self.assertEqual(QueryClassifier.classify("what happens if extraction increases by 20%"), "Simulation")
        self.assertEqual(QueryClassifier.classify("show a map of groundwater stress zones"), "GIS")

    def test_entity_extractor(self):
        """Verifies location and year range parsing."""
        entities = EntityExtractor.extract_entities("What is the recharge in Salem for 2024-2025?")
        self.assertEqual(entities["location"], "SALEM")
        self.assertEqual(entities["location_type"], "district")
        self.assertEqual(entities["year"], "2024-2025")
        self.assertEqual(entities["parameter"], "total_recharge")

    def test_session_manager(self):
        """Verifies session lifecycle creation, retrieval and expiration."""
        sess_id = SessionManager.generate_session_id()
        self.assertTrue(sess_id.startswith("sess_"))
        
        session = SessionManager.get_session(sess_id)
        self.assertEqual(session["session_id"], sess_id)
        self.assertEqual(session["user_id"], "anonymous")
        
        # Modify and save session
        session["user_id"] = "test_user"
        SessionManager.save_session(sess_id, session)
        
        recovered = SessionManager.get_session(sess_id)
        self.assertEqual(recovered["user_id"], "test_user")
        
        # Expire session
        SessionManager.expire_session(sess_id)

    def test_confidence_manager(self):
        """Verifies overall confidence compounding metric calculation."""
        res = ConfidenceManager.compute_overall_confidence(
            ["DataAgent", "KnowledgeAgent"],
            {"DataAgent": {"confidence_score": 0.98}, "KnowledgeAgent": {"confidence_score": 0.90}}
        )
        self.assertEqual(res["confidence_score"], 0.94)

    def test_agent_graph_integration(self):
        """Verifies full LangGraph StateGraph traversal using the new supervisor."""
        state_input = {
            "session_id": "test_integration_session",
            "query": "hello",
            "original_query": "hello",
            "language": "en",
            "intent": "general",
            "resolved_location": None,
            "resolved_location_type": None,
            "resolved_year": None,
            "routing_history": [],
            "current_node": "supervisor",
            "response": "",
            "confidence_score": 0.0,
            "citations": [],
            "evaluation": None
        }
        
        out = agent_graph.invoke(state_input)
        self.assertIn("supervisor", out["routing_history"])
        self.assertIn("general", out["routing_history"])
        self.assertIn("synthesize", out["routing_history"])
        self.assertIn("evaluate", out["routing_history"])
        self.assertTrue(len(out["response"]) > 0)

if __name__ == "__main__":
    unittest.main()
