import json
from sqlalchemy.orm import Session
from app.config import Config
from app.database import SessionLocal, init_db
from app.models import Document, Chunk
from app.logging_config import logger

def generate_lineage_report():
    logger.info("Generating Data Lineage Report...")
    init_db()
    
    db = SessionLocal()
    report_dir = Config.BASE_DIR / "reports" / "coverage"
    report_dir.mkdir(parents=True, exist_ok=True)
    
    lineage_map = {}
    
    try:
        # Fetch all chunks and documents
        docs = db.query(Document).all()
        doc_map = {d.document_id: d for d in docs}
        
        chunks = db.query(Chunk).all()
        
        for c in chunks:
            doc = doc_map.get(c.document_id)
            if doc:
                lineage_map[c.chunk_id] = {
                    "document_id": doc.document_id,
                    "title": doc.title,
                    "page_number": c.page_number,
                    "source_pdf": f"{doc.title}.pdf" if not doc.title.endswith(".pdf") else doc.title,
                    "source_authority": doc.source, # e.g. CGWB or State Authority
                    "collection": doc.collection,
                    "embedding_model": doc.embedding_model,
                    "checksum": doc.checksum
                }
                
        # Write to reports/coverage/lineage.json
        output_path = report_dir / "lineage.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(lineage_map, f, indent=2)
            
        logger.info(f"Successfully generated Data Lineage Report for {len(lineage_map)} chunks. Saved to {output_path}")
        
    except Exception as e:
        logger.error(f"Failed to generate lineage report: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    generate_lineage_report()
