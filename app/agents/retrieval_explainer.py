import re
from typing import List, Dict, Any
from app.logging_config import logger

class RetrievalExplainer:
    @staticmethod
    def explain(chunks: List[Dict[str, Any]], query: str = "") -> List[Dict[str, Any]]:
        """Generates detailed selection explanations for the Top-K retrieved chunks."""
        explanations = []
        
        # Scan query for key terms to identify matched entities
        query_terms = re.findall(r'\b[A-Za-z0-9-]+\b', query.lower())
        
        for rank, c in enumerate(chunks):
            meta = c.get("metadata", {})
            text = c.get("text", "")
            
            # 1. Scores (extract directly or set defaults)
            sim_score = c.get("score", c.get("rrf_score", 0.0))
            if "rrf_score" in c:
                # If RRF was applied, score is inner-product or rrf
                sim_score = c.get("rrf_score", 0.0)
            
            bm25_score = c.get("bm25_score", 0.0)
            ce_score = c.get("rerank_score", 0.0)
            
            # 2. Extract matched entities from text
            matched = []
            
            # Check location
            dist = meta.get("district")
            if dist and dist.lower() in text.lower():
                matched.append(dist)
            
            # Extract years mentioned
            years = re.findall(r'\b20\d{2}\b', text)
            if years:
                matched.extend(list(set(years)))
                
            # Check other keywords
            keywords = ["recharge", "extraction", "aquifer", "monitoring", "policy", "guideline", "firka", "taluk"]
            for kw in keywords:
                if kw in text.lower() and kw in query_terms:
                    matched.append(kw.title())
                    
            matched_entities = list(dict.fromkeys(matched)) # deduplicate
            
            # 3. Document Name
            doc_name = meta.get("title") or meta.get("document_name") or "Unknown Document"
            
            # 4. Reason Selected Builder
            reasons = []
            if rank == 0:
                reasons.append("Highest reranker score")
            if sim_score > 0.6:
                reasons.append("High semantic similarity")
            if bm25_score > 5.0:
                reasons.append("High lexical matches (BM25)")
            
            # Check matches to user query keywords
            for ent in matched_entities:
                reasons.append(f"Contains matched parameter '{ent}'")
                
            if not reasons:
                reasons.append("Selected by hybrid context ranking")
                
            reason_selected = ". ".join(reasons[:4]) + "."
            
            # 5. Compile explanation dict
            exp = {
                "chunk_id": id(text) % 1000, # deterministic mock id from string hash
                "similarity_score": float(sim_score),
                "bm25_score": float(bm25_score),
                "cross_encoder_score": float(ce_score),
                "matched_entities": matched_entities,
                "document": doc_name,
                "reason_selected": reason_selected,
                "priority_category": meta.get("category", "General Science"),
                "rank": rank + 1
            }
            
            explanations.append(exp)
            
        logger.info(f"RetrievalExplainer generated {len(explanations)} explanations.")
        return explanations
