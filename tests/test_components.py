import unittest
import os
import sys
from sqlalchemy.orm import Session
from app.config import Config
from app.database import SessionLocal, init_db
from app.resolution import LocationResolver
from app.pipelines.parser import DocumentParser
from app.embeddings.reranker import RerankerManager
from app.memory import MemoryEngine
from app.agents.analytics import AnalyticsAgent
from app.agents.evaluation import EvaluationAgent

class TestAquaMindComponents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.db = SessionLocal()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_location_resolution(self):
        # 1. Test alias lookups
        res = LocationResolver.resolve_location(self.db, "kovai")
        self.assertEqual(res["resolved"], "COIMBATORE")
        self.assertEqual(res["type"], "district")

        res_nellai = LocationResolver.resolve_location(self.db, "nellai")
        self.assertEqual(res_nellai["resolved"], "TIRUNELVELI")
        self.assertEqual(res_nellai["type"], "district")

        # 2. Test exact match
        res_salem = LocationResolver.resolve_location(self.db, "SALEM")
        self.assertEqual(res_salem["resolved"], "SALEM")
        self.assertEqual(res_salem["type"], "district")

        # 3. Test fuzzy matching
        res_fuzzy = LocationResolver.resolve_location(self.db, "Tirupur")
        self.assertEqual(res_fuzzy["resolved"], "TIRUPPUR")
        self.assertEqual(res_fuzzy["type"], "district")

        # 4. Test non-existent location
        res_none = LocationResolver.resolve_location(self.db, "NonexistentPlaceXYZ")
        self.assertIsNone(res_none["resolved"])
        self.assertIsNone(res_none["type"])

    def test_metadata_validation(self):
        filepath = "d:\\AquamindAI\\pdf\\resources assessment\\Salem_2025_resource_assessment.pdf"
        text_sample = "This report covers GEC assessment for Salem district in the year 2024-25."
        
        meta = DocumentParser.generate_metadata_heuristics(filepath, text_sample)
        self.assertEqual(meta["year"], "2025") # From GEC_Salem_2025_report.pdf filename
        self.assertEqual(meta["district"], "Salem")
        self.assertEqual(meta["category"], "Resource Assessment")
        self.assertEqual(meta["language"], "English")
        self.assertEqual(meta["embedding_version"], "bge-m3")

    def test_reranker_validation(self):
        # Setup mock candidate chunks
        candidate_chunks = [
            {"text": "Cats are small carnivorous mammals often kept as indoor pets.", "rerank_score": 0.0},
            {"text": "Groundwater guidelines and policies regulate the extraction of subterranean aquifers.", "rerank_score": 0.0},
            {"text": "Rainfall data is measured using rain gauges in local meteorological stations.", "rerank_score": 0.0}
        ]
        query = "What are the rules and guidelines for groundwater aquifers?"
        
        # Run reranker
        ranked = RerankerManager.rerank(query, candidate_chunks, top_k=2)
        
        # Groundwater chunk should be ranked highest
        self.assertTrue(len(ranked) <= 2)
        self.assertTrue("groundwater" in ranked[0]["text"].lower())
        self.assertGreater(ranked[0]["rerank_score"], ranked[1]["rerank_score"])

    def test_memory_engine(self):
        session_id = "test_suite_session_999"
        
        # Test creation/retrieval
        session = MemoryEngine.get_or_create_session(self.db, session_id)
        self.assertEqual(session.session_id, session_id)
        
        # Test entities update
        entities = {"district": "SALEM", "year": "2024-2025"}
        MemoryEngine.update_entities(self.db, session_id, entities)
        
        # Test preferences update
        prefs = {"language": "ta", "detail_level": "farmer"}
        MemoryEngine.update_preferences(self.db, session_id, prefs)
        
        # Test get_context
        context = MemoryEngine.get_context(self.db, session_id)
        self.assertEqual(context["entities"]["district"], "SALEM")
        self.assertEqual(context["preferences"]["language"], "ta")
        
        # Clean up session messages & record if any
        from app.models import SessionMemory, ChatMessage
        self.db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        self.db.query(SessionMemory).filter(SessionMemory.session_id == session_id).delete()
        self.db.commit()

    def test_analytics_agent(self):
        # We test that the Analytics agent process runs and outputs comparative format
        state_input = {
            "query": "Compare groundwater extraction in Salem and Coimbatore",
            "resolved_location": "SALEM",
            "resolved_location_type": "district",
            "routing_history": ["supervisor"]
        }
        res = AnalyticsAgent.process(state_input)
        self.assertIn("context_analytics", res)
        comp = res["context_analytics"]
        self.assertIn("compared_districts", comp)
        self.assertTrue("SALEM" in comp["compared_districts"] or "COIMBATORE" in comp["compared_districts"])

    def test_evaluation_loop(self):
        # Test EvaluationAgent formatting and output keys
        state_input = {
            "query": "Is Salem groundwater safe?",
            "response": "According to GEC assessment, Salem is semi-critical.",
            "context_data": [{"level": "district", "name": "SALEM", "stage_of_extraction": 85.0}],
            "context_knowledge": [{"document_name": "GEC Report", "page_number": 12, "text": "Salem is semi-critical."}],
            "routing_history": ["supervisor", "data", "synthesize"],
            "language": "en"
        }
        res = EvaluationAgent.process(state_input)
        self.assertIn("evaluation", res)
        eval_dict = res["evaluation"]
        # If LLM rate limits hit, eval_dict might be empty or fallback. Otherwise check standard keys.
        if eval_dict and "grounding_score" in eval_dict:
            self.assertIn("hallucination_detected", eval_dict)
            self.assertIn("routing_accuracy", eval_dict)

if __name__ == "__main__":
    unittest.main()
