from typing import List, Dict, Any
from app.logging_config import logger

class SelfReflection:
    @staticmethod
    def generate_reflection_query(query: str, missing_topics: List[str], missing_entities: List[str]) -> str:
        """Constructs a search expansion query targeting missing topics and entities for retry cycles."""
        missing = [str(t).strip() for t in (missing_topics or []) + (missing_entities or []) if str(t).strip()]
        if missing:
            ref_q = f"{query} " + " ".join(missing)
            logger.info(f"SelfReflection generated reflection query: '{ref_q}'")
            return ref_q
        return query

    @staticmethod
    def merge_contexts(original: List[Dict[str, Any]], additional: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merges and de-duplicates additional retrieved chunks with the original candidate list."""
        seen = set()
        merged = []
        for c in original + additional:
            meta = c.get("metadata", {})
            text_norm = c.get("text", "").strip().lower()
            doc_id = str(meta.get("document_id", ""))
            page_num = str(meta.get("page_number", ""))
            
            key = (text_norm, doc_id, page_num)
            if key not in seen:
                seen.add(key)
                merged.append(c)
                
        logger.info(f"SelfReflection merged contexts: original={len(original)} + additional={len(additional)} -> unique={len(merged)}")
        return merged
