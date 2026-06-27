import os
import json
import hashlib
from datetime import datetime
from app.config import Config
from app.logging_config import logger

class DataVersioningService:
    @staticmethod
    def get_manifest() -> dict:
        """Reads the dataset manifest from disk."""
        if not Config.MANIFEST_PATH.exists():
            # Initialize empty manifest
            manifest = {
                "manifest_version": "1.0",
                "embedding_model": Config.EMBEDDING_MODEL_NAME,
                "reranker_model": Config.RERANKER_MODEL_NAME,
                "ingested_files": {},
                "last_updated": datetime.utcnow().isoformat() + "Z"
            }
            DataVersioningService.save_manifest(manifest)
            return manifest
        try:
            with open(Config.MANIFEST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read manifest file: {e}")
            return {"ingested_files": {}}

    @staticmethod
    def save_manifest(manifest: dict):
        """Writes the dataset manifest to disk."""
        try:
            Config.MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(Config.MANIFEST_PATH, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write manifest file: {e}")

    @staticmethod
    def calculate_checksum(filepath: str) -> str:
        """Computes md5 checksum of a file to check for duplicates."""
        hasher = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating checksum for {filepath}: {e}")
            raise e

    @staticmethod
    def is_file_duplicate(filepath: str) -> bool:
        """Checks if a file with the same checksum has already been ingested."""
        checksum = DataVersioningService.calculate_checksum(filepath)
        manifest = DataVersioningService.get_manifest()
        for file_info in manifest.get("ingested_files", {}).values():
            if file_info.get("checksum") == checksum:
                return True
        return False

    @staticmethod
    def register_file(filepath: str, metadata: dict, chunk_count: int) -> str:
        """Registers an ingested file in the system manifest with enterprise schema."""
        checksum = DataVersioningService.calculate_checksum(filepath)
        manifest = DataVersioningService.get_manifest()
        
        filename = os.path.basename(filepath)
        
        # Determine collection
        collection = metadata.get("category") or metadata.get("type") or "Unknown"
        
        # Generate stable document ID
        doc_hash = hashlib.md5(filename.encode('utf-8')).hexdigest()[:8].upper()
        doc_id = f"DOC-{doc_hash}"
        
        # Count pages if PDF, else 1
        pages = metadata.get("pages")
        if not pages and filename.lower().endswith(".pdf"):
            try:
                import pdfplumber
                with pdfplumber.open(filepath) as pdf:
                    pages = len(pdf.pages)
            except Exception:
                pages = 1
        elif not pages:
            pages = 1

        manifest["ingested_files"][filename] = {
            "document_id": doc_id,
            "title": metadata.get("document_name") or filename.replace("_", " ").replace(".pdf", ""),
            "source": metadata.get("source") or "CGWB",
            "collection": collection,
            "version": metadata.get("version") or "1.0",
            "pages": pages,
            "chunks": chunk_count,
            "embedding_model": metadata.get("embedding_version") or Config.EMBEDDING_MODEL_NAME,
            "checksum": checksum,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "filepath": str(filepath),
            "metadata": metadata
        }
        manifest["last_updated"] = datetime.utcnow().isoformat() + "Z"
        DataVersioningService.save_manifest(manifest)
        logger.info(f"Registered file {filename} in system manifest. Document ID: {doc_id}")
        return checksum
        
    @staticmethod
    def remove_file(filename: str):
        """Removes a file from the system manifest."""
        manifest = DataVersioningService.get_manifest()
        if filename in manifest.get("ingested_files", {}):
            del manifest["ingested_files"][filename]
            manifest["last_updated"] = datetime.utcnow().isoformat() + "Z"
            DataVersioningService.save_manifest(manifest)
            logger.info(f"Removed file {filename} from system manifest.")
