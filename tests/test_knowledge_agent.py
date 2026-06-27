import unittest
from unittest.mock import patch, MagicMock
from app.database import SessionLocal, init_db
from app.agents.query_rewriter import QueryRewriter
from app.agents.multi_query_generator import MultiQueryGenerator
from app.agents.retrieval_orchestrator import RetrievalOrchestrator
from app.agents.context_ranker import ContextRanker
from app.agents.context_compressor import ContextCompressor
from app.agents.knowledge_grounding import KnowledgeGrounding
from app.agents.knowledge_citations import KnowledgeCitations
from app.agents.knowledge_confidence import KnowledgeConfidence
from app.agents.knowledge_metrics import KnowledgeMetrics
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.graph import agent_graph

class TestKnowledgeAgentPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_query_rewriter(self):
        """Verifies that QueryRewriter rewrites vague questions successfully using LLMService."""
        with patch("app.agents.llm.LLMService.call", return_value="What is the groundwater status of Salem district?"):
            res = QueryRewriter.rewrite("What about Salem?")
            self.assertEqual(res, "What is the groundwater status of Salem district?")

    def test_multi_query_generator(self):
        """Verifies that MultiQueryGenerator generates alternative search variations."""
        mock_json = {"queries": ["groundwater recharge Salem", "Salem recharge assessment", "Salem GEC recharge"]}
        with patch("app.agents.llm.LLMService.call_json", return_value=mock_json):
            res = MultiQueryGenerator.generate("groundwater recharge in Salem")
            self.assertEqual(len(res), 4) # includes the original query
            self.assertIn("groundwater recharge in Salem", res)
            self.assertIn("Salem GEC recharge", res)

    def test_retrieval_orchestrator_and_graph(self):
        """Verifies that RetrievalOrchestrator hybrid search retrieves candidates and Knowledge Graph lookup extracts links."""
        graph_links = RetrievalOrchestrator.lookup_knowledge_graph("SALEM")
        self.assertIsInstance(graph_links, list)
        
        hybrid_res = RetrievalOrchestrator.retrieve_hybrid(["recharge in Salem"], filter_dict=None, k=2)
        self.assertIn("dense", hybrid_res)
        self.assertIn("sparse", hybrid_res)

    def test_context_ranker(self):
        """Verifies context ranking de-duplicates and applies source priority offsets."""
        dense = [
            {"text": "recharge in Salem block is high.", "metadata": {"category": "Resource Assessment", "document_id": "doc1", "page_number": 2}, "score": 0.9},
            {"text": "salem aquifer mapping is draft.", "metadata": {"category": "General Science", "document_id": "doc2", "page_number": 5}, "score": 0.8}
        ]
        sparse = [
            {"text": "recharge in Salem block is high.", "metadata": {"category": "Resource Assessment", "document_id": "doc1", "page_number": 2}, "score": 0.75},
            {"text": "water draft in Salem taluk.", "metadata": {"category": "Resource Assessment", "document_id": "doc3", "page_number": 1}, "score": 0.6}
        ]
        graph = [
            {"text": "Knowledge Graph Link: Salem belongs to Taluk Salem", "metadata": {"category": "Hydrological Graph Link", "document_id": "graph", "page_number": 0}, "score": 0.85}
        ]
        
        ranked = ContextRanker.rank_and_merge(dense, sparse, graph)
        self.assertEqual(len(ranked), 4)
        self.assertEqual(ranked[0]["metadata"]["category"], "Resource Assessment")

    def test_context_compressor(self):
        """Verifies paragraph sorting, freshness prioritization, and sentence-level de-duplication."""
        chunks = [
            {"text": "Salem groundwater draft is critical. Salem groundwater draft is critical.", "metadata": {"title": "Groundwater Resource Assessment 2021", "year": "2021"}, "score": 0.8},
            {"text": "Aquifer recharge in Salem is low.", "metadata": {"title": "Groundwater Resource Assessment 2024", "year": "2024"}, "score": 0.85}
        ]
        compressed = ContextCompressor.compress(chunks, max_chars=1000)
        self.assertEqual(len(compressed), 2)
        self.assertEqual(compressed[0]["metadata"]["year"], "2024")
        self.assertNotIn("Salem groundwater draft is critical. Salem groundwater draft is critical.", compressed[1]["text"])

    def test_knowledge_grounding(self):
        """Verifies assertion check outputs a proper grounding score using LLMService."""
        mock_audit = {
            "assertions": [
                {"fact": "Salem recharge is high", "status": "supported", "source_index": 1},
                {"fact": "Groundwater quality is critical", "status": "neutral", "source_index": None}
            ],
            "grounding_score": 0.5,
            "hallucination_detected": True
        }
        with patch("app.agents.llm.LLMService.call_json", return_value=mock_audit):
            res = KnowledgeGrounding.verify("Salem recharge is high. Groundwater quality is critical.", [{"text": "Salem recharge is high."}])
            self.assertEqual(res["grounding_score"], 0.5)
            self.assertTrue(res["hallucination_detected"])

    def test_knowledge_citations(self):
        """Verifies document citation brackets are resolved properly."""
        response = "Salem aquifers are unconfined [1]. CGWB limits draft [2]."
        context = [
            {"text": "Salem aquifers are unconfined.", "metadata": {"title": "Aquifer Mapping", "page_number": 12, "category": "Resource Assessment", "document_id": "AQ01", "version": "1.0", "source": "CGWB"}},
            {"text": "CGWB limits draft.", "metadata": {"title": "CGWB Regulations", "page_number": 4, "category": "Regulations & Policy", "document_id": "RG01", "version": "2.0", "source": "CGWA"}}
        ]
        citations = KnowledgeCitations.compile_citations(response, context)
        self.assertEqual(len(citations), 2)
        self.assertEqual(citations[0]["document_name"], "Aquifer Mapping")
        self.assertEqual(citations[1]["document_name"], "CGWB Regulations")

    def test_knowledge_confidence(self):
        """Verifies compound weighted confidence and tier classifications."""
        retrieval = [{"rrf_score": 0.035, "metadata": {"document_id": "d1", "page_number": 1, "category": "RAG", "title": "Salem assessment"}}]
        rerank = [{"rerank_score": 2.5}]
        conf = KnowledgeConfidence.calculate(retrieval, rerank, grounding_score=0.9)
        self.assertIn("confidence_score", conf)
        self.assertIn("confidence_level", conf)
        self.assertEqual(conf["confidence_level"], "VERY HIGH")

    def test_knowledge_metrics(self):
        """Verifies start/stop tracking updates correctly."""
        tracker = KnowledgeMetrics.start_tracking()
        metrics = KnowledgeMetrics.stop_tracking(
            tracker=tracker,
            retrieval_dur_ms=100.0,
            rerank_dur_ms=50.0,
            compress_dur_ms=10.0,
            gen_dur_ms=200.0,
            chunks_searched=15,
            chunks_retrieved=10,
            chunks_reranked=8,
            chunks_compressed=5,
            context_len=1000,
            output_len=500
        )
        self.assertEqual(metrics["chunks_searched"], 15)
        self.assertEqual(metrics["chunks_compressed"], 5)
        self.assertGreaterEqual(metrics["total_latency_ms"], 0.0)

    def test_knowledge_agent_graph_run(self):
        """Verifies full orchestrator execution and routing within StateGraph."""
        state_input = {
            "session_id": "test_know_session",
            "query": "What is the CGWA regulation in Salem block?",
            "original_query": "What is the CGWA regulation in Salem block?",
            "language": "en",
            "intent": "knowledge",
            "resolved_location": "SALEM",
            "resolved_location_type": "district",
            "resolved_year": "2024-2025",
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
            "citations": [],
            "evaluation": None
        }
        
        mock_rewrite = "What is the Central Ground Water Authority regulation in Salem district?"
        mock_plan = {
            "intent": "knowledge",
            "reasoning": ["Mocked planner response"],
            "language": "English",
            "entities": {"location": "SALEM", "year": "2024-2025"},
            "agents": ["KnowledgeAgent"],
            "tools": [],
            "response_type": "text",
            "confidence": 0.95
        }
        mock_eval = {
            "assertions": [{"fact": "Groundwater guidelines exist", "status": "supported", "source_index": 1}],
            "grounding_score": 1.0,
            "hallucination_detected": False
        }
        
        def mock_call_json(prompt, system_prompt=None):
            if system_prompt and "Auditor" in system_prompt:
                return mock_eval
            return mock_plan

        with patch("app.agents.query_rewriter.QueryRewriter.rewrite", return_value=mock_rewrite):
            with patch("app.agents.multi_query_generator.MultiQueryGenerator.generate", return_value=["CGWA regulation Salem", "groundwater guidelines Salem"]):
                with patch("app.agents.llm.LLMService.call", return_value="CGWA guidelines Salem require check dams [1]."):
                    with patch("app.agents.llm.LLMService.call_json", side_effect=mock_call_json):
                        out = agent_graph.invoke(state_input)
                        self.assertIn("knowledge", out["routing_history"])
                        self.assertIn("synthesize", out["routing_history"])
                        self.assertTrue(len(out["response"]) > 0)
                        self.assertGreater(out["confidence_score"], 0.0)

if __name__ == "__main__":
    unittest.main()
