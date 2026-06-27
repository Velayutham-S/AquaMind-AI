from sentence_transformers import CrossEncoder
from app.config import Config
from app.logging_config import logger

class RerankerManager:
    _model = None
    _model_lock = None

    @classmethod
    def get_model(cls) -> CrossEncoder:
        """Lazy loads the CrossEncoder model to optimize load times."""
        if cls._model is None:
            if not hasattr(cls, '_model_lock') or cls._model_lock is None:
                import threading
                cls._model_lock = threading.Lock()
            with cls._model_lock:
                if cls._model is None:
                    try:
                        import torch
                        torch.set_num_threads(1)
                        logger.info(f"Loading reranker model: {Config.RERANKER_MODEL_NAME}...")
                        cls._model = CrossEncoder(Config.RERANKER_MODEL_NAME)
                        logger.info("Reranker model loaded successfully.")
                    except Exception as e:
                        logger.error(f"Error loading reranker model: {e}", exc_info=True)
                        raise e
        return cls._model

    @classmethod
    def rerank(cls, query: str, candidate_chunks: list, top_k: int = 5) -> list:
        """Reranks candidate chunks against the user query using the Cross-Encoder."""
        if not candidate_chunks:
            return []
            
        try:
            model = cls.get_model()
            
            # Format inputs as [query, text] pairs
            pairs = [[query, chunk["text"]] for chunk in candidate_chunks]
            
            logger.info(f"Reranking {len(candidate_chunks)} candidate chunks using Cross-Encoder...")
            scores = model.predict(pairs)
            
            # Update scores in chunks
            for idx, score in enumerate(scores):
                candidate_chunks[idx]["rerank_score"] = float(score)
                
            # Sort chunks by rerank score descending
            ranked_chunks = sorted(candidate_chunks, key=lambda x: x["rerank_score"], reverse=True)
            
            # Select top K
            final_chunks = ranked_chunks[:top_k]
            logger.info(f"Rerank complete. Top score: {final_chunks[0]['rerank_score'] if final_chunks else 'N/A'}")
            return final_chunks
            
        except Exception as e:
            logger.error(f"Failed to run reranker: {e}. Falling back to original FAISS scores.")
            # Fallback to original order
            return candidate_chunks[:top_k]
