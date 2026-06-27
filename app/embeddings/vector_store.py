import os
import pickle
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from app.config import Config
from app.logging_config import logger

class VectorStoreManager:
    _model = None
    _model_lock = None
    _index = None
    _chunks = None
    _store_lock = None

    @classmethod
    def get_model(cls) -> SentenceTransformer:
        """Lazy loads the SentenceTransformer model on demand from local cache or downloads it once."""
        if cls._model is None:
            if not hasattr(cls, '_model_lock') or cls._model_lock is None:
                import threading
                cls._model_lock = threading.Lock()
            with cls._model_lock:
                if cls._model is None:
                    try:
                        import torch
                        torch.set_num_threads(1)
                        cache_dir = Config.EMBEDDING_MODEL_CACHE_DIR
                        # A valid sentence transformer model has config.json and weights files
                        has_model = (cache_dir / "config.json").exists() and (
                            (cache_dir / "model.safetensors").exists() or 
                            (cache_dir / "pytorch_model.bin").exists()
                        )
                        
                        device = "cuda" if torch.cuda.is_available() else "cpu"
                        logger.info(f"Detecting hardware for embedding model: device = {device}")
                        
                        if has_model:
                            logger.info(f"Loading embedding model from local cache: {cache_dir}...")
                            model = SentenceTransformer(str(cache_dir), device=device)
                        else:
                            logger.info(f"Embedding model not found in local cache. Downloading: {Config.EMBEDDING_MODEL_NAME}...")
                            model = SentenceTransformer(Config.EMBEDDING_MODEL_NAME, device=device)
                            logger.info(f"Saving downloaded model permanently to local cache: {cache_dir}...")
                            model.save(str(cache_dir))
                        
                        if device == "cpu":
                            logger.info("Applying dynamic INT8 quantization for 4x CPU encoding speedup...")
                            cls._model = torch.quantization.quantize_dynamic(
                                model, {torch.nn.Linear}, dtype=torch.qint8
                            )
                        else:
                            cls._model = model
                        logger.info("Embedding model loaded successfully.")
                    except Exception as e:
                        logger.error(f"Error loading embedding model: {e}", exc_info=True)
                        raise e
        return cls._model

    def __init__(self):
        self.index_file = Config.FAISS_INDEX_PATH / "faiss.index"
        self.chunks_file = Config.FAISS_INDEX_PATH / "chunks.pkl"
        self.index = None
        self.chunks = []
        self._load_store()

    def _load_store(self):
        """Loads FAISS index and metadata chunks from disk if they exist, utilizing class cache."""
        if VectorStoreManager._index is not None and VectorStoreManager._chunks is not None:
            self.index = VectorStoreManager._index
            self.chunks = VectorStoreManager._chunks
            return

        if not hasattr(VectorStoreManager, '_store_lock') or VectorStoreManager._store_lock is None:
            import threading
            VectorStoreManager._store_lock = threading.Lock()

        with VectorStoreManager._store_lock:
            if VectorStoreManager._index is not None and VectorStoreManager._chunks is not None:
                self.index = VectorStoreManager._index
                self.chunks = VectorStoreManager._chunks
                return

            try:
                if self.index_file.exists() and self.chunks_file.exists():
                    logger.info("Loading FAISS store from disk into cache...")
                    VectorStoreManager._index = faiss.read_index(str(self.index_file))
                    with open(self.chunks_file, "rb") as f:
                        VectorStoreManager._chunks = pickle.load(f)
                    logger.info(f"Loaded existing FAISS index with {len(VectorStoreManager._chunks)} chunks.")
                else:
                    logger.info("No pre-existing FAISS index found. Initializing new index.")
                    VectorStoreManager._index = None
                    VectorStoreManager._chunks = []
                self.index = VectorStoreManager._index
                self.chunks = VectorStoreManager._chunks
            except Exception as e:
                logger.error(f"Failed to load FAISS store from disk: {e}. Resetting index.")
                self.index = None
                self.chunks = []

    def _save_store(self):
        """Saves current FAISS index and chunks to disk and updates class cache."""
        try:
            Config.FAISS_INDEX_PATH.mkdir(parents=True, exist_ok=True)
            if self.index is not None:
                faiss.write_index(self.index, str(self.index_file))
                with open(self.chunks_file, "wb") as f:
                    pickle.dump(self.chunks, f)
                logger.info(f"Saved FAISS index with {len(self.chunks)} chunks to disk.")
                # Keep class cache in sync
                VectorStoreManager._index = self.index
                VectorStoreManager._chunks = self.chunks
        except Exception as e:
            logger.error(f"Failed to save FAISS store to disk: {e}")

    def add_texts(self, texts: list, metadatas: list) -> dict:
        """Generates embeddings and inserts texts with metadata into the FAISS index.
        Returns a metrics dict with embedding performance data for the console dashboard."""
        if not texts:
            return {"chunks": 0, "elapsed": 0, "throughput": 0, "peak_gpu_mb": 0}
            
        import torch
        import time
        model = self.get_model()
        device = str(model.device) if hasattr(model, 'device') else "cpu"
        use_cuda = "cuda" in device
        
        # Determine batch size dynamically based on device
        batch_size = 128 if use_cuda else 32
        
        gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "None"
        logger.info(f"Generating embeddings for {len(texts)} chunks | Device={device} | GPU={gpu_name} | Batch={batch_size}")
        
        # Reset peak memory tracker before encoding
        if use_cuda:
            torch.cuda.reset_peak_memory_stats()
        
        start_time = time.time()
        if use_cuda:
            with torch.inference_mode(), torch.amp.autocast("cuda"):
                embeddings = model.encode(
                    texts,
                    batch_size=batch_size,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                    normalize_embeddings=False
                )
        else:
            with torch.inference_mode():
                embeddings = model.encode(
                    texts,
                    batch_size=batch_size,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                    normalize_embeddings=False
                )
        elapsed = time.time() - start_time
        throughput = len(texts) / elapsed if elapsed > 0 else 0
        
        # Get peak GPU memory usage
        peak_gpu_mb = 0
        if use_cuda:
            peak_gpu_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
        
        logger.info(f"Generated {len(texts)} embeddings in {elapsed:.2f}s ({throughput:.1f} chunks/sec) | Peak GPU: {peak_gpu_mb:.0f} MB")
        
        # Norm embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        
        dim = embeddings.shape[1]
        
        if self.index is None:
            # IndexFlatIP uses Inner Product (which matches cosine similarity after normalization)
            self.index = faiss.IndexFlatIP(dim)
            
        self.index.add(embeddings)
        
        for text, meta in zip(texts, metadatas):
            self.chunks.append({
                "text": text,
                "metadata": meta
            })
            
        self._save_store()
        logger.info(f"Added {len(texts)} chunks. New index size: {len(self.chunks)}")
        
        return {
            "chunks": len(texts),
            "elapsed": elapsed,
            "throughput": throughput,
            "peak_gpu_mb": peak_gpu_mb,
            "batch_size": batch_size,
            "device": device,
            "gpu_name": gpu_name,
            "index_size": len(self.chunks)
        }

    def similarity_search(self, query: str, k: int = 15, filter_dict: dict = None) -> list:
        """Searches the vector store for similar chunks, with optional metadata filtering."""
        if self.index is None or not self.chunks:
            logger.warning("Search called on empty vector store.")
            return []
            
        model = self.get_model()
        query_vector = model.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(query_vector)
        
        # Search for a larger pool to allow filtering room
        search_k = min(len(self.chunks), k * 4 if filter_dict else k)
        
        scores, indices = self.index.search(query_vector, search_k)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
                
            chunk = self.chunks[idx]
            meta = chunk["metadata"]
            
            # Apply metadata filters if provided
            if filter_dict:
                match = True
                for fk, fv in filter_dict.items():
                    if fv is not None and meta.get(fk) != fv:
                        match = False
                        break
                if not match:
                    continue
                    
            results.append({
                "text": chunk["text"],
                "metadata": meta,
                "score": float(score) # Inner product score matches cosine similarity
            })
            
            if len(results) >= k:
                break
                
        return results

    def clear(self):
        """Clears index files from disk and memory."""
        self.index = None
        self.chunks = []
        VectorStoreManager._index = None
        VectorStoreManager._chunks = None
        if self.index_file.exists():
            os.remove(self.index_file)
        if self.chunks_file.exists():
            os.remove(self.chunks_file)
        logger.info("Cleared FAISS index and chunks successfully.")
