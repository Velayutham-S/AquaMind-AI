from typing import List, Dict, Any
from app.logging_config import logger

class ContextRanker:
    SOURCE_PRIORITIES = {
        "Resource Assessment": 1.0,
        "Regulations & Policy": 0.75,
        "Guidelines & Policy": 0.75,
        "Artificial Recharge": 0.50,
        "Modelling & Simulation": 0.50,
        "Aquifer Management": 0.25,
        "Year Book": 0.25,
        "FAQ": 0.0,
        "General Science": -0.50
    }

    @classmethod
    def rank_and_merge(
        cls, 
        dense: List[Dict[str, Any]], 
        sparse: List[Dict[str, Any]], 
        graph: List[Dict[str, Any]], 
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """Applies Reciprocal Rank Fusion (RRF), filters duplicates, adjusts based on source categories, and ranks final candidates."""
        rrf_scores = {}
        
        def get_key(c):
            meta = c.get("metadata", {})
            text_norm = c.get("text", "").strip().lower()
            doc_id = str(meta.get("document_id", ""))
            page_num = str(meta.get("page_number", ""))
            return (text_norm, doc_id, page_num)

        # 1. RRF Scoring
        for rank, c in enumerate(dense):
            key = get_key(c)
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            
        for rank, c in enumerate(sparse):
            key = get_key(c)
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            
        for rank, c in enumerate(graph):
            key = get_key(c)
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (k + rank + 1)

        # 2. De-duplicate and add priority offsets
        seen_keys = set()
        merged_candidates = []
        
        all_candidates = dense + sparse + graph
        
        for c in all_candidates:
            key = get_key(c)
            if key not in seen_keys:
                seen_keys.add(key)
                c_copy = dict(c)
                
                meta = c_copy.get("metadata", {})
                category = meta.get("category", "General Science")
                priority_offset = cls.SOURCE_PRIORITIES.get(category, 0.0)
                
                base_score = rrf_scores[key]
                c_copy["rrf_score"] = base_score
                c_copy["priority_offset"] = priority_offset
                # Scale priority offset to make it influential but not override rank completely
                c_copy["retrieval_score"] = base_score + (priority_offset * 0.05)
                merged_candidates.append(c_copy)
                
        # 3. Sort final candidates descending
        merged_candidates.sort(key=lambda x: x["retrieval_score"], reverse=True)
        
        logger.info(f"ContextRanker: merged and ranked {len(merged_candidates)} unique candidates.")
        return merged_candidates
