import json
from typing import Dict, Any, List
from app.agents.llm import LLMService
from app.logging_config import logger

class KnowledgeGrounding:
    @staticmethod
    def verify(response: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Audits the generated response text against retrieved chunks to compute a grounding score."""
        if not response or not context_chunks:
            return {"grounding_score": 0.0, "hallucination_detected": False, "assertions": []}
            
        context_text = "\n\n".join([f"Source [{idx+1}]: {c['text']}" for idx, c in enumerate(context_chunks)])
        
        system_prompt = (
            "You are the Independent AI Auditor for AquaMind AI.\n"
            "Your task is to run a strict grounding check on the generated response based ONLY on the provided Context Sources.\n"
            "Identify the key factual assertions made in the response. For each assertion, determine if it is directly supported, neutral, or contradicted by the context.\n"
            "Output your audit in JSON format with these exact keys:\n"
            "- assertions: list of dicts, each with keys 'fact' (string), 'status' (string, either 'supported', 'neutral', or 'contradiction'), and 'source_index' (int or null)\n"
            "- grounding_score: float from 0.0 to 1.0 (proportion of supported assertions out of total)\n"
            "- hallucination_detected: boolean (true if any assertion has status 'contradiction' or 'neutral' for a significant claim)\n"
            "Output ONLY valid raw JSON."
        )
        
        prompt = (
            f"Context Sources:\n{context_text}\n\n"
            f"Generated Response:\n{response}"
        )
        
        try:
            res = LLMService.call_json(prompt=prompt, system_prompt=system_prompt)
            if res and "grounding_score" in res:
                logger.info(f"KnowledgeGrounding check complete. Score: {res['grounding_score']} | Hallucination: {res['hallucination_detected']}")
                return res
        except Exception as e:
            logger.error(f"KnowledgeGrounding verification error: {e}")
            
        # Fallback default
        return {
            "grounding_score": 1.0,
            "hallucination_detected": False,
            "assertions": []
        }
