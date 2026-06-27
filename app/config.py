import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(os.getenv("DATA_DIR", "d:\\AquamindAI"))

class Config:
    BASE_DIR = BASE_DIR
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    DB_URL = os.getenv("DB_URL", f"sqlite:///{BASE_DIR}/aquamind.db")
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Models
    EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
    RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    
    # Paths
    PDF_DIR = BASE_DIR / "pdf"
    STRUCTURED_DATA_DIR = BASE_DIR / "structured data"
    FAISS_INDEX_PATH = BASE_DIR / "data" / "faiss_index"
    MANIFEST_PATH = BASE_DIR / "data" / "manifest.json"
    EMBEDDING_MODEL_CACHE_DIR = BASE_DIR / "models" / "embeddings" / "bge-m3"
    
    # Ensure system directories exist
    SUPERVISOR_CONFIDENCE = {
        "retrieval": float(os.getenv("CONF_WEIGHT_RETRIEVAL", "0.35")),
        "sql": float(os.getenv("CONF_WEIGHT_SQL", "0.20")),
        "prediction": float(os.getenv("CONF_WEIGHT_PREDICTION", "0.20")),
        "reranker": float(os.getenv("CONF_WEIGHT_RERANKER", "0.15")),
        "planner": float(os.getenv("CONF_WEIGHT_PLANNER", "0.10"))
    }
    
    @classmethod
    def ensure_dirs(cls):
        cls.PDF_DIR.mkdir(parents=True, exist_ok=True)
        cls.STRUCTURED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        (cls.BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
        (cls.BASE_DIR / "reports").mkdir(parents=True, exist_ok=True)
        (cls.BASE_DIR / "reports" / "executions").mkdir(parents=True, exist_ok=True)
        (cls.BASE_DIR / "logs").mkdir(parents=True, exist_ok=True)
        cls.EMBEDDING_MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Run directory check on import
Config.ensure_dirs()
