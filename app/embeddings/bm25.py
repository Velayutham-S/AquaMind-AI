import re
import math
import pickle
from pathlib import Path
from sqlalchemy.orm import Session
from app.config import Config
from app.database import SessionLocal
from app.models import Chunk, Document
from app.logging_config import logger

class BM25Searcher:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.index_path = Config.BASE_DIR / "data" / "bm25_index.pkl"
        self.vocab = {}
        self.idf = {}
        self.doc_lens = []
        self.avg_doc_len = 0.0
        self.doc_term_freqs = []  # List of dicts mapping term -> count
        self.doc_ids = []  # List of chunk_ids
        self.corpus_size = 0
        self.chunk_records_cache = {}  # In-memory database cache
        self._load_or_build()

    def tokenize(self, text: str) -> list:
        """Tokenizes text using word boundaries, supporting both English and Tamil characters."""
        if not text:
            return []
        # Support Tamil unicode range (\u0b80-\u0bff) and English
        tokens = re.findall(r'[a-zA-Z0-9\u0b80-\u0bff]+', text.lower())
        return tokens

    def _load_or_build(self):
        """Loads index from disk or builds from scratch if missing."""
        if self.index_path.exists():
            try:
                with open(self.index_path, "rb") as f:
                    state = pickle.load(f)
                    self.vocab = state["vocab"]
                    self.idf = state["idf"]
                    self.doc_lens = state["doc_lens"]
                    self.avg_doc_len = state["avg_doc_len"]
                    self.doc_term_freqs = state["doc_term_freqs"]
                    self.doc_ids = state["doc_ids"]
                    self.corpus_size = state["corpus_size"]
                    self.chunk_records_cache = state.get("chunk_records_cache", {})
                logger.info(f"Loaded existing BM25 index with {self.corpus_size} documents.")
                
                # Rebuild if cache is empty (legacy index file transition helper)
                if self.corpus_size > 0 and not self.chunk_records_cache:
                    logger.info("Legacy index file detected (no cached metadata). Rebuilding index...")
                    self.rebuild_index()
                return
            except Exception as e:
                logger.error(f"Failed to load BM25 index from disk: {e}. Rebuilding...")

        self.rebuild_index()

    def rebuild_index(self):
        """Builds the BM25 index from the current database chunks and caches metadata."""
        logger.info("Building BM25 index from SQLite chunks database...")
        db = SessionLocal()
        try:
            # Query all chunks and join with document to get metadata
            chunks_data = db.query(Chunk).all()
            if not chunks_data:
                logger.warning("No chunks found in database. BM25 index remains empty.")
                self.vocab = {}
                self.idf = {}
                self.doc_lens = []
                self.avg_doc_len = 0.0
                self.doc_term_freqs = []
                self.doc_ids = []
                self.corpus_size = 0
                self.chunk_records_cache = {}
                return

            doc_records = {d.document_id: d for d in db.query(Document).all()}
            
            self.doc_ids = [c.chunk_id for c in chunks_data]
            self.corpus_size = len(chunks_data)
            
            # Reset structures
            self.doc_lens = []
            self.doc_term_freqs = []
            self.vocab = {}
            self.chunk_records_cache = {}
            doc_counts = {}  # term -> count of docs containing it
            
            total_len = 0
            for chunk in chunks_data:
                tokens = self.tokenize(chunk.text)
                doc_len = len(tokens)
                self.doc_lens.append(doc_len)
                total_len += doc_len
                
                term_freq = {}
                for token in tokens:
                    term_freq[token] = term_freq.get(token, 0) + 1
                    
                self.doc_term_freqs.append(term_freq)
                
                # Update vocabulary and doc counts
                for token in term_freq.keys():
                    doc_counts[token] = doc_counts.get(token, 0) + 1
                    if token not in self.vocab:
                        self.vocab[token] = len(self.vocab)
                
                # Cache metadata to remove runtime SQLite lookup overhead
                doc = doc_records.get(chunk.document_id)
                self.chunk_records_cache[chunk.chunk_id] = {
                    "text": chunk.text,
                    "document_id": chunk.document_id,
                    "page_number": chunk.page_number,
                    "section_title": chunk.section_title,
                    "doc_title": doc.title if doc else "Unknown",
                    "doc_collection": doc.collection if doc else "Unknown",
                    "doc_source": doc.source if doc else "CGWB",
                    "doc_district": doc.district if doc else None
                }
                        
            self.avg_doc_len = total_len / self.corpus_size if self.corpus_size > 0 else 0.0
            
            # Compute IDF (using standard Lucene/Okapi formula)
            self.idf = {}
            for term, doc_count in doc_counts.items():
                # Avoid log negative values by adding 0.5 and 1
                self.idf[term] = math.log((self.corpus_size - doc_count + 0.5) / (doc_count + 0.5) + 1.0)
                
            # Save index to disk
            self._save_index()
            logger.info(f"BM25 index built and saved. Vocabulary size: {len(self.vocab)} terms.")
            
        except Exception as e:
            logger.error(f"Error rebuilding BM25 index: {e}", exc_info=True)
        finally:
            db.close()

    def _save_index(self):
        """Saves current state to data/bm25_index.pkl."""
        try:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "vocab": self.vocab,
                "idf": self.idf,
                "doc_lens": self.doc_lens,
                "avg_doc_len": self.avg_doc_len,
                "doc_term_freqs": self.doc_term_freqs,
                "doc_ids": self.doc_ids,
                "corpus_size": self.corpus_size,
                "chunk_records_cache": self.chunk_records_cache
            }
            with open(self.index_path, "wb") as f:
                pickle.dump(state, f)
            logger.info("BM25 index pickle saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save BM25 index: {e}")

    def search(self, query: str, k: int = 15, filter_dict: dict = None) -> list:
        """Computes BM25 similarity score for all indexed chunks and returns top K matched results."""
        if self.corpus_size == 0 or not self.doc_term_freqs:
            return []
            
        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []
            
        results = []
        try:
            # Check cached database records
            chunk_records = self.chunk_records_cache
            
            # If cache is empty, lazy load it from SQLite once (fallback recovery)
            if not chunk_records:
                logger.info("BM25 in-memory chunk cache is empty. Lazy loading from SQLite database...")
                db = SessionLocal()
                try:
                    chunks_data = db.query(Chunk).all()
                    doc_records = {d.document_id: d for d in db.query(Document).all()}
                    for chunk in chunks_data:
                        doc = doc_records.get(chunk.document_id)
                        chunk_records[chunk.chunk_id] = {
                            "text": chunk.text,
                            "document_id": chunk.document_id,
                            "page_number": chunk.page_number,
                            "section_title": chunk.section_title,
                            "doc_title": doc.title if doc else "Unknown",
                            "doc_collection": doc.collection if doc else "Unknown",
                            "doc_source": doc.source if doc else "CGWB",
                            "doc_district": doc.district if doc else None
                        }
                except Exception as ex:
                    logger.error(f"Failed to lazy load BM25 cache from DB: {ex}")
                finally:
                    db.close()

            scores = []
            for doc_idx in range(self.corpus_size):
                chunk_id = self.doc_ids[doc_idx]
                chunk_obj = chunk_records.get(chunk_id)
                if not chunk_obj:
                    continue
                    
                # Apply metadata filters directly on cached record
                if filter_dict:
                    match = True
                    meta = {
                        "document_id": chunk_obj["document_id"],
                        "page_number": chunk_obj["page_number"],
                        "category": chunk_obj["section_title"],
                        "title": chunk_obj["doc_title"],
                        "district": chunk_obj["doc_district"]
                    }
                    for fk, fv in filter_dict.items():
                        if fv is not None and meta.get(fk) != fv:
                            match = False
                            break
                    if not match:
                        continue
                        
                # Compute BM25 score
                score = 0.0
                tf_dict = self.doc_term_freqs[doc_idx]
                doc_len = self.doc_lens[doc_idx]
                
                for token in query_tokens:
                    if token not in self.idf:
                        continue
                    tf = tf_dict.get(token, 0)
                    if tf == 0:
                        continue
                        
                    # Standard BM25 term score formula
                    numerator = tf * (self.k1 + 1.0)
                    denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
                    score += self.idf[token] * (numerator / denominator)
                    
                if score > 0.0:
                    scores.append((score, chunk_obj))
                    
            # Sort scores descending
            scores.sort(key=lambda x: x[0], reverse=True)
            
            for score, chunk in scores[:k]:
                # Format to look identical to VectorStore similarity_search output
                results.append({
                    "text": chunk["text"],
                    "metadata": {
                        "document_id": chunk["document_id"],
                        "page_number": chunk["page_number"],
                        "category": chunk["section_title"] or chunk["doc_collection"] or "Unknown",
                        "title": chunk["doc_title"] or "Unknown",
                        "source": chunk["doc_source"] or "CGWB",
                        "district": chunk["doc_district"]
                    },
                    "score": float(score)
                })
                
        except Exception as e:
            logger.error(f"Error executing BM25 search: {e}", exc_info=True)
            
        return results

class BM25Manager:
    _instance = None
    _lock = None

    @classmethod
    def get_instance(cls) -> BM25Searcher:
        if cls._instance is None:
            if not hasattr(cls, '_lock') or cls._lock is None:
                import threading
                cls._lock = threading.Lock()
            with cls._lock:
                if cls._instance is None:
                    cls._instance = BM25Searcher()
        return cls._instance
