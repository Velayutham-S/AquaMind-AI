import os
import json
import pickle
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.config import Config
from app.database import SessionLocal, init_db
from app.models import DistrictAssessment, FirkaAssessment, MonitoringData, Document, Chunk
from app.pipelines.versioning import DataVersioningService

def generate_ingestion_audit():
    init_db()
    db = SessionLocal()
    
    # 1. Walk PDF directory
    pdf_files = []
    for root, _, files in os.walk(Config.PDF_DIR):
        for file in files:
            if file.endswith(".pdf"):
                pdf_files.append(Path(root) / file)
                
    # Walk Excel & CSV
    excel_files = []
    for root, _, files in os.walk(Config.STRUCTURED_DATA_DIR):
        for file in files:
            if file.endswith((".xlsx", ".xls")):
                excel_files.append(Path(root) / file)
                
    csv_files = []
    for root, _, files in os.walk(Config.PDF_DIR):
        for file in files:
            if file.endswith(".csv"):
                csv_files.append(Path(root) / file)

    # Load Manifest & FAISS chunks
    manifest = DataVersioningService.get_manifest()
    ingested_info = manifest.get("ingested_files", {})
    
    chunks_pkl_path = Config.FAISS_INDEX_PATH / "chunks.pkl"
    faiss_chunks = []
    vector_checksums = set()
    vector_doc_names = set()
    if chunks_pkl_path.exists():
        try:
            with open(chunks_pkl_path, "rb") as f:
                faiss_chunks = pickle.load(f)
                for fc in faiss_chunks:
                    meta = fc.get("metadata", {})
                    if "checksum" in meta:
                        vector_checksums.add(meta["checksum"])
                    if "document_name" in meta:
                        vector_doc_names.add(meta["document_name"].lower())
        except Exception:
            pass
            
    # Load SQLite databases cache
    db_docs = {d.checksum: d for d in db.query(Document).all()}
    db_doc_titles = {d.title.lower(): d for d in db.query(Document).all()}
    
    chunk_counts_by_doc = {}
    db_chunks = db.query(Chunk.document_id).all()
    for (d_id,) in db_chunks:
        chunk_counts_by_doc[d_id] = chunk_counts_by_doc.get(d_id, 0) + 1

    pdf_discovered = len(pdf_files)
    pdf_processed = 0
    pdf_failed = 0
    
    pdf_rows = []
    
    print("-" * 140)
    print(f"{'File Name':<50} | {'Collection':<25} | {'Pages':<5} | {'Parsed':<6} | {'Chunks':<6} | {'Embeds':<6} | {'Manifest':<8} | {'FAISS':<5} | {'Status':<10}")
    print("-" * 140)
    
    # Sort files by directory and name to show natural ingestion order
    pdf_files.sort(key=lambda p: (p.parent.name, p.name))
    
    for pdf_path in pdf_files:
        name = pdf_path.name
        checksum = ""
        try:
            checksum = DataVersioningService.calculate_checksum(str(pdf_path))
        except Exception:
            pass
            
        # Get actual collection from DB if ingested, else fallback to directory name
        in_manifest = name in ingested_info
        manifest_meta = ingested_info[name] if in_manifest else {}
        doc_obj = db_docs.get(checksum) or db_doc_titles.get(name.replace(".pdf", "").replace("_", " ").lower())
        
        collection = "Pending"
        if doc_obj:
            collection = doc_obj.collection
        elif in_manifest:
            collection = manifest_meta.get("collection", "Unknown")
        else:
            # Fallback to directory name
            collection = pdf_path.parent.name
            
        db_pages = doc_obj.pages if doc_obj else manifest_meta.get("pages", 0)
        
        db_chunks_count = 0
        if doc_obj:
            db_chunks_count = chunk_counts_by_doc.get(doc_obj.document_id, 0)
            
        # Check FAISS
        in_vector = (checksum in vector_checksums) or (name.replace(".pdf", "").replace("_", " ").lower() in vector_doc_names)
        
        # Deduce status
        status = "Pending"
        parsed = "No"
        if in_manifest and doc_obj and in_vector:
            status = "Completed"
            parsed = "Yes"
            pdf_processed += 1
        elif in_manifest or doc_obj or in_vector:
            status = "In Progress"
            parsed = "Yes"
            pdf_processed += 1 # count as processed/partially processed
        else:
            status = "Pending"
            
        # Count failures
        if status == "Completed" and db_chunks_count == 0:
            status = "Failed"
            parsed = "No"
            pdf_failed += 1
            pdf_processed -= 1
            
        print(f"{name[:50]:<50} | {collection[:25]:<25} | {db_pages:<5} | {parsed:<6} | {db_chunks_count:<6} | {db_chunks_count:<6} | {'Yes' if in_manifest else 'No':<8} | {'Yes' if in_vector else 'No':<5} | {status:<10}")
        
        pdf_rows.append({
            "name": name,
            "collection": collection,
            "pages": db_pages,
            "parsed": parsed,
            "chunks": db_chunks_count,
            "manifest": in_manifest,
            "vector": in_vector,
            "status": status
        })
        
    print("-" * 140)
    
    # 2. Verify Excel & CSV Imports
    imported_excels = 0
    for excel_path in excel_files:
        level = "firka" if "firka" in excel_path.name.lower() else "district"
        has_records = False
        if level == "district":
            has_records = db.query(DistrictAssessment).count() > 0
        else:
            has_records = db.query(FirkaAssessment).count() > 0
            
        if excel_path.name in ingested_info and has_records:
            imported_excels += 1
            
    imported_csvs = 0
    for csv_path in csv_files:
        db_count = db.query(MonitoringData).filter(MonitoringData.dataset_source == csv_path.name).count()
        if csv_path.name in ingested_info and db_count > 0:
            imported_csvs += 1
            
    # Counts summary
    total_db_chunks = db.query(Chunk).count()
    
    print("\n=== DATASET INVENTORY COUNTS SUMMARY ===")
    print(f"PDFs Discovered: {pdf_discovered}")
    print(f"PDFs Processed: {pdf_processed}")
    print(f"PDFs Failed: {pdf_failed}")
    print(f"CSVs Discovered: {len(csv_files)} | Imported: {imported_csvs}")
    print(f"Excel Files Discovered: {len(excel_files)} | Imported: {imported_excels}")
    print(f"Total Chunks in DB: {total_db_chunks}")
    print(f"Total Embeddings in FAISS: {len(faiss_chunks)}")
    
    # Retrieval Coverage Report by Collection
    collections_checklist = [
        "GEC Guidelines",
        "Resource Assessment",
        "Aquifer Mapping",
        "Aquifer Management",
        "Groundwater Quality",
        "Groundwater Modelling",
        "Artificial Recharge",
        "Groundwater Regulations",
        "Groundwater Policies",
        "Groundwater Year Books",
        "FAQ",
        "Monitoring",
        "Rainwater Harvesting",
        "System Identity"
    ]
    
    COLLECTION_MAP = {
        "GEC Guidelines": ["Guidelines & Policy"],
        "Resource Assessment": ["Resource Assessment"],
        "Aquifer Mapping": ["Aquifer Mapping"],
        "Aquifer Management": ["Aquifer Management"],
        "Groundwater Quality": ["Water Quality", "Groundwater Quality"],
        "Groundwater Modelling": ["Modelling & Simulation", "Groundwater Modelling"],
        "Artificial Recharge": ["Artificial Recharge"],
        "Groundwater Regulations": ["Regulations & Policy", "Regulations", "Act"],
        "Groundwater Policies": ["Regulations & Policy", "Policy", "MOU"],
        "Groundwater Year Books": ["Year Book", "Yearbook"],
        "FAQ": ["FAQ"],
        "Monitoring": ["monitoring_csv", "Monitoring"],
        "Rainwater Harvesting": ["Rainwater Harvesting", "FAQ"],
        "System Identity": ["System Identity", "General Science"]
    }
    
    print("\n=== RETRIEVAL COVERAGE CHUNKS BY COLLECTION ===")
    print(f"{'Collection':<30} | {'Chunk Count'}")
    print("-" * 45)
    for col in collections_checklist:
        filters = []
        for val in COLLECTION_MAP.get(col, [col]):
            filters.append(Document.collection.like(f"%{val}%"))
            filters.append(Chunk.section_title.like(f"%{val}%"))
            
        col_db_count = db.query(Chunk).join(Document, Chunk.document_id == Document.document_id).filter(or_(*filters)).count()
        print(f"{col:<30} | {col_db_count}")
    print("-" * 45)
    
    db.close()

if __name__ == "__main__":
    generate_ingestion_audit()
