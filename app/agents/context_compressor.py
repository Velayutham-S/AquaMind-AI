import re
from typing import List, Dict, Any
from app.logging_config import logger

class ContextCompressor:
    @staticmethod
    def compress(chunks: List[Dict[str, Any]], max_chars: int = 4000) -> List[Dict[str, Any]]:
        """Compresses candidate chunks by filtering redundancy, prioritizing freshness/scores, and matching character budgets."""
        compressed_chunks = []
        char_count = 0
        
        # Freshness heuristic based on years in document titles or metadata
        def get_chunk_freshness(c):
            meta = c.get("metadata", {})
            title = str(meta.get("title", "")).lower()
            year = str(meta.get("year", ""))
            
            # Look for 4-digit years matching 20xx
            years = re.findall(r'20\d{2}', title + year)
            if years:
                return max(int(y) for y in years)
            return 2000

        # Sort by freshness (primary) and rerank/original score (secondary)
        sorted_chunks = sorted(
            chunks, 
            key=lambda x: (get_chunk_freshness(x), x.get("rerank_score", x.get("score", 0.0))), 
            reverse=True
        )

        seen_sentences = set()

        for c in sorted_chunks:
            text = c["text"]
            
            # Simple sentence splitting
            sentences = re.split(r'(?<=[.!?])\s+', text)
            cleaned_sentences = []
            
            for s in sentences:
                s_strip = s.strip()
                s_norm = re.sub(r'[^\w\s]', '', s_strip).lower().strip()
                # De-duplicate sentences longer than 15 characters
                if len(s_norm) > 15:
                    if s_norm not in seen_sentences:
                        seen_sentences.add(s_norm)
                        cleaned_sentences.append(s_strip)
                else:
                    cleaned_sentences.append(s_strip)
                    
            if not cleaned_sentences:
                continue
                
            compressed_text = " ".join(cleaned_sentences)
            
            # Truncate if we hit maximum character limits
            if char_count + len(compressed_text) > max_chars:
                remaining = max_chars - char_count
                if remaining < 100:
                    break
                truncated = compressed_text[:remaining]
                last_space = truncated.rfind(" ")
                if last_space > 0:
                    truncated = truncated[:last_space]
                compressed_text = truncated + "..."
                
            c_copy = dict(c)
            c_copy["text"] = compressed_text
            compressed_chunks.append(c_copy)
            char_count += len(compressed_text)
            
            if char_count >= max_chars:
                break
                
        logger.info(f"Compressed {len(chunks)} chunks into {len(compressed_chunks)} chunks (Total length: {char_count} chars).")
        return compressed_chunks
