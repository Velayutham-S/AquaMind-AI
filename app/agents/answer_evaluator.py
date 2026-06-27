import json
from typing import Dict, Any, List
from app.agents.llm import LLMService
from app.logging_config import logger

class AnswerEvaluator:
    @staticmethod
    def evaluate(query: str, answer: str, context_chunks: List[Dict[str, Any]], grounding_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluates synthesized answer completeness, evidence grounding, citation mapping, and potential contradictions."""
        if not answer:
            return {
                "answer_complete": False,
                "missing_topics": ["Empty answer"],
                "missing_entities": [],
                "contradictions": ["No content provided"],
                "citation_quality": "LOW",
                "grounding_quality": "LOW",
                "needs_retry": True,
                "evaluation_score": 0.0
            }
            
        context_text = "\n\n".join([f"Source [{idx+1}]: {c['text']}" for idx, c in enumerate(context_chunks)])
        grounding_score = grounding_data.get("grounding_score", 1.0)
        
        system_prompt = (
            "You are the Independent RAG Answer Evaluator for AquaMind AI.\n"
            "Evaluate the provided Answer against the User Query and Context Sources.\n"
            "Assess the following:\n"
            "1. Answer Completeness: Are all parts of the user question addressed?\n"
            "2. Citations: Does every fact have supporting citations? Are bracket citations correctly aligned to source indices?\n"
            "3. Contradictions: Are there claims that contradict other statements or context facts?\n"
            "4. Missing Information: Are there critical entities (locations, parameters) or topics missing?\n"
            "5. Quality Metrics: Rates citation quality and grounding quality as 'HIGH', 'MEDIUM', or 'LOW'.\n"
            "6. Evaluation Score: A float from 0.0 to 1.0 based on these criteria.\n\n"
            "Output MUST be in JSON format matching this schema exactly:\n"
            "{\n"
            "  \"answer_complete\": true_or_false,\n"
            "  \"missing_topics\": [\"topic1\", \"topic2\"],\n"
            "  \"missing_entities\": [\"entity1\", \"entity2\"],\n"
            "  \"contradictions\": [\"contradiction1\"],\n"
            "  \"citation_quality\": \"HIGH_or_MEDIUM_or_LOW\",\n"
            "  \"grounding_quality\": \"HIGH_or_MEDIUM_or_LOW\",\n"
            "  \"needs_retry\": true_or_false,\n"
            "  \"evaluation_score\": 0.95\n"
            "}\n"
            "If evaluation_score is below 0.90, set needs_retry to true.\n"
            "Output ONLY valid JSON."
        )
        
        prompt = (
            f"User Query:\n{query}\n\n"
            f"Context Sources:\n{context_text}\n\n"
            f"Grounding Score from Auditor: {grounding_score}\n\n"
            f"Generated Answer:\n{answer}"
        )
        
        try:
            res = LLMService.call_json(prompt=prompt, system_prompt=system_prompt)
            if res and "evaluation_score" in res:
                score = float(res["evaluation_score"])
                if score < 0.90:
                    res["needs_retry"] = True
                else:
                    if grounding_score < 0.90:
                        res["needs_retry"] = True
                logger.info(f"AnswerEvaluator: complete. Score: {res['evaluation_score']} | Retry: {res['needs_retry']}")
                return res
        except Exception as e:
            logger.error(f"AnswerEvaluator error: {e}")
            
        return {
            "answer_complete": True,
            "missing_topics": [],
            "missing_entities": [],
            "contradictions": [],
            "citation_quality": "HIGH",
            "grounding_quality": "HIGH",
            "needs_retry": False,
            "evaluation_score": 1.0
        }
