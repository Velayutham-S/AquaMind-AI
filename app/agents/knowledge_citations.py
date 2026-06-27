import re
from typing import List, Dict, Any
from app.logging_config import logger

class KnowledgeCitations:
    @staticmethod
    def compile_citations(response: str, context_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parses inline bracket citations [1], [2] in response and resolves them against context metadata."""
        if not response or not context_chunks:
            return []
            
        bracket_indices = re.findall(r'\[(\d+)\]', response)
        resolved_indices = set(int(idx) for idx in bracket_indices)
        
        citations = []
        
        for idx in sorted(resolved_indices):
            chunk_idx = idx - 1
            if 0 <= chunk_idx < len(context_chunks):
                chunk = context_chunks[chunk_idx]
                meta = chunk.get("metadata", {})
                
                doc_title = meta.get("title") or meta.get("document_name") or "Unknown Document"
                page_num = meta.get("page_number") or "N/A"
                section = meta.get("category") or meta.get("section_title") or "General"
                collection = meta.get("collection") or meta.get("doc_collection") or "Resource Assessment"
                doc_id = meta.get("document_id") or "UnknownID"
                version = meta.get("version") or "1.0"
                
                citations.append({
                    "citation_id": idx,
                    "document_name": doc_title,
                    "page_number": page_num,
                    "section": section,
                    "collection": collection,
                    "document_id": doc_id,
                    "version": version,
                    "source": meta.get("source", "CGWB"),
                    "text_snippet": chunk["text"][:150] + "..."
                })
                
        logger.info(f"KnowledgeCitations resolved {len(citations)} citations from response text.")
        return citations
