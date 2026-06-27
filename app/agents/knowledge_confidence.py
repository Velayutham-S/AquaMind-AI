import math
from typing import List, Dict, Any
from app.logging_config import logger

class KnowledgeConfidence:
    @staticmethod
    def calculate(
        retrieval_chunks: List[Dict[str, Any]],
        reranked_chunks: List[Dict[str, Any]],
        grounding_score: float,
        llm_score: float = 0.95
    ) -> Dict[str, Any]:
        """Computes weighted overall confidence based on retrieval, reranking, grounding, metadata, and LLM factors."""
        
        # 1. Retrieval Score normalization (RRF score)
        max_rrf = 0.0
        if retrieval_chunks:
            max_rrf = max(c.get("rrf_score", 0.0) for c in retrieval_chunks)
        # Scale RRF score (typical RRF around 0.02 to 0.04 represents strong match)
        retrieval_norm = min(1.0, max_rrf / 0.04) if max_rrf > 0 else 0.0
        
        # 2. Reranker Score normalization (Sigmoid on Logit)
        max_rerank = 0.0
        if reranked_chunks:
            max_rerank = max(c.get("rerank_score", 0.0) for c in reranked_chunks)
        # Sigmoid maps logit to [0, 1]
        rerank_norm = 1.0 / (1.0 + math.exp(-max_rerank)) if reranked_chunks else 0.0
        
        # 3. Grounding score is already 0.0 - 1.0
        grounding_norm = max(0.0, min(1.0, grounding_score))
        
        # 4. Metadata Completeness score
        metadata_scores = []
        if retrieval_chunks:
            for c in retrieval_chunks[:3]:
                meta = c.get("metadata", {})
                fields = ["document_id", "page_number", "category", "title"]
                present = sum(1 for f in fields if meta.get(f) or meta.get(f.replace("title", "document_name")))
                metadata_scores.append(present / len(fields))
        metadata_norm = sum(metadata_scores) / len(metadata_scores) if metadata_scores else 0.0
        
        # 5. LLM Score
        llm_norm = max(0.0, min(1.0, llm_score))
        
        # Weighted Overall Confidence
        overall = (
            (retrieval_norm * 0.35) +
            (rerank_norm * 0.25) +
            (grounding_norm * 0.20) +
            (metadata_norm * 0.10) +
            (llm_norm * 0.10)
        )
        
        if overall >= 0.85:
            tier = "VERY HIGH"
        elif overall >= 0.70:
            tier = "HIGH"
        elif overall >= 0.50:
            tier = "MEDIUM"
        elif overall >= 0.30:
            tier = "LOW"
        else:
            tier = "CRITICAL"
            
        breakdown = {
            "retrieval": float(retrieval_norm),
            "rerank": float(rerank_norm),
            "grounding": float(grounding_norm),
            "metadata": float(metadata_norm),
            "llm": float(llm_norm)
        }
        
        logger.info(f"KnowledgeConfidence calculated: {overall:.4f} ({tier})")
        return {
            "confidence_score": float(overall),
            "confidence_level": tier,
            "confidence_breakdown": breakdown
        }
