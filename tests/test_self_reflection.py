import unittest
from unittest.mock import patch
from app.agents.self_reflection import SelfReflection
from app.agents.knowledge_agent import KnowledgeAgent

class TestSelfReflection(unittest.TestCase):
    def test_generate_reflection_query(self):
        """Verifies query builder merges missing topics/entities correctly."""
        query = "Groundwater recharge Salem"
        topics = ["extraction rate"]
        entities = ["2024"]
        
        ref_query = SelfReflection.generate_reflection_query(query, topics, entities)
        self.assertEqual(ref_query, "Groundwater recharge Salem extraction rate 2024")

    def test_generate_reflection_query_empty(self):
        """Verifies query remains same if no missing information is identified."""
        query = "Groundwater recharge Salem"
        ref_query = SelfReflection.generate_reflection_query(query, [], [])
        self.assertEqual(ref_query, query)

    def test_merge_contexts_deduplication(self):
        """Verifies de-duplication when merging original and additional contexts."""
        original = [
            {"text": "Salem draft is high.", "metadata": {"document_id": "doc1", "page_number": 2}},
            {"text": "Recharge details.", "metadata": {"document_id": "doc2", "page_number": 1}}
        ]
        additional = [
            {"text": "Recharge details.", "metadata": {"document_id": "doc2", "page_number": 1}},
            {"text": "Rainwater harvesting policy.", "metadata": {"document_id": "doc3", "page_number": 5}}
        ]
        
        merged = SelfReflection.merge_contexts(original, additional)
        self.assertEqual(len(merged), 3)
        self.assertEqual(merged[2]["metadata"]["document_id"], "doc3")

    def test_retry_flow_integration(self):
        """Verifies that KnowledgeAgent process triggers a retry cycle when evaluation score is low."""
        state = {
            "session_id": "test_retry_sess",
            "query": "What is Salem recharge rate?",
            "original_query": "What is Salem recharge rate?",
            "language": "en",
            "intent": "knowledge",
            "resolved_location": "SALEM",
            "routing_history": []
        }
        mock_rewrite = "What is the groundwater recharge in Salem district?"
        mock_eval_low = {
            "answer_complete": False,
            "missing_topics": ["recharge rate"],
            "missing_entities": [],
            "contradictions": [],
            "citation_quality": "LOW",
            "grounding_quality": "LOW",
            "needs_retry": True,
            "evaluation_score": 0.5
        }
        mock_eval_high = {
            "answer_complete": True,
            "missing_topics": [],
            "missing_entities": [],
            "contradictions": [],
            "citation_quality": "HIGH",
            "grounding_quality": "HIGH",
            "needs_retry": False,
            "evaluation_score": 0.95
        }
        
        grounding_seq = [{"grounding_score": 0.5}, {"grounding_score": 0.95}]
        eval_seq = [mock_eval_low, mock_eval_high]
        
        with patch("app.agents.query_rewriter.QueryRewriter.rewrite", return_value=mock_rewrite):
            with patch("app.agents.multi_query_generator.MultiQueryGenerator.generate", return_value=["recharge Salem"]):
                with patch("app.agents.llm.LLMService.call", return_value="Recharge rate in Salem block [1]."):
                    with patch("app.agents.knowledge_grounding.KnowledgeGrounding.verify", side_effect=grounding_seq):
                        with patch("app.agents.answer_evaluator.AnswerEvaluator.evaluate", side_effect=eval_seq):
                            out = KnowledgeAgent.process(state)
                            
                            self.assertTrue(out["reflection_attempted"])
                            self.assertTrue(out["retry_generation"])
                            self.assertEqual(out["evaluation_score"], 0.95)
                            self.assertEqual(out["grounding_quality"], "HIGH")

if __name__ == "__main__":
    unittest.main()
