import os
import re
import math
import pandas as pd
from sqlalchemy.orm import Session
from datetime import datetime
from app.config import Config
from app.logging_config import logger
from app.database import init_db
import hashlib
from app.models import DistrictAssessment, FirkaAssessment, MonitoringData, AuditLog, Document, Chunk
from app.pipelines.parser import DocumentParser
from app.pipelines.versioning import DataVersioningService
from app.embeddings.vector_store import VectorStoreManager

class IngestionPipeline:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.vector_store = VectorStoreManager()
        # Initialize DB tables if not exist
        init_db()

    def validate_file(self, filepath: str) -> bool:
        """Validates if file exists and has a supported extension."""
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return False
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in [".pdf", ".xlsx", ".xls", ".csv"]:
            logger.error(f"Unsupported file format: {ext} for file {filepath}")
            return False
        return True

    def ingest_excel(self, filepath: str) -> str:
        """Ingests GEC assessment spreadsheets into District/Firka tables."""
        filename = os.path.basename(filepath)
        
        # Determine level based on path
        level = "district"
        if "firka" in filepath.lower() or "firka" in filename.lower():
            level = "firka"
            
        logger.info(f"Ingesting GEC assessment spreadsheet: {filename} at {level} level")
        records = DocumentParser.parse_excel_assessment(filepath, level=level)
        
        if not records:
            logger.warning(f"No records parsed from Excel: {filepath}")
            return "0"

        # Write records in bulk or upsert
        count = 0
        if level == "district":
            # Clear old records for this year to prevent duplicates on re-ingest
            year = records[0]["year"]
            self.db.query(DistrictAssessment).filter(DistrictAssessment.year == year).delete()
            self.db.commit()
            
            db_records = [DistrictAssessment(**rec) for rec in records]
            self.db.bulk_save_objects(db_records)
            self.db.commit()
            count = len(db_records)
        else:
            # Firka level
            year = records[0]["year"]
            self.db.query(FirkaAssessment).filter(FirkaAssessment.year == year).delete()
            self.db.commit()
            
            db_records = [FirkaAssessment(**rec) for rec in records]
            self.db.bulk_save_objects(db_records)
            self.db.commit()
            count = len(db_records)

        # Log audit action
        audit = AuditLog(
            user_role="admin",
            action="ingest_excel",
            details=f"Parsed GEC {level} spreadsheet: {filename}, year: {year}, records: {count}"
        )
        self.db.add(audit)
        self.db.commit()

        # Update manifest
        meta = {
            "type": "spreadsheet",
            "level": level,
            "year": year,
            "record_count": count
        }
        DataVersioningService.register_file(filepath, meta, chunk_count=count)
        
        logger.info(f"Successfully finished Excel ingestion. Inserted {count} records.")
        return str(count)

    def ingest_csv(self, filepath: str) -> str:
        """Ingests monitoring datasets in batch into the MonitoringData table."""
        filename = os.path.basename(filepath)
        logger.info(f"Ingesting monitoring CSV: {filename}")

        # Standard CSV read
        df_sample = pd.read_csv(filepath, nrows=10)
        cols = df_sample.columns.tolist()

        # Determine parameter and unit dynamically
        parameter = "unknown"
        unit = "unknown"
        value_col = None

        for col in cols:
            col_lower = col.lower()
            if "groundwater level" in col_lower or "ground water level" in col_lower:
                parameter = "groundwater_level"
                unit = "meter"
                value_col = col
                break
            elif "rainfall" in col_lower:
                parameter = "rainfall"
                unit = "mm"
                value_col = col
                break
            elif "river water level" in col_lower or "river_level" in col_lower:
                parameter = "river_level"
                unit = "meter"
                value_col = col
                break
            elif "discharge" in col_lower and "available" not in col_lower:
                parameter = "river_discharge"
                unit = "m3/sec"
                value_col = col
                break

        if not value_col:
            # Fallback to last column as numeric value
            value_col = cols[-1]
            parameter = "metric"
            unit = "units"
            logger.warning(f"Could not identify parameter column in CSV {filename}. Defaulting to column '{value_col}'")

        # Set up batch processing
        batch_size = 5000
        count = 0
        
        # Deduplicate: check if this source file has already been ingested
        self.db.query(MonitoringData).filter(MonitoringData.dataset_source == filename).delete()
        self.db.commit()

        try:
            for chunk in pd.read_csv(filepath, chunksize=batch_size):
                db_chunk = []
                for _, row in chunk.iterrows():
                    # Handle date conversions
                    raw_time = row.get("Data Acquisition Time")
                    acq_time = None
                    if pd.notna(raw_time):
                        try:
                            acq_time = datetime.strptime(str(raw_time).strip(), "%d-%m-%Y %H:%M")
                        except ValueError:
                            try:
                                acq_time = datetime.strptime(str(raw_time).strip(), "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                acq_time = datetime.utcnow() # Fallback

                    val = row.get(value_col)
                    if pd.isna(val):
                        continue # Skip empty data readings

                    # Read coordinates
                    lat = row.get("Latitude")
                    lon = row.get("Longitude")
                    lat_val = float(lat) if pd.notna(lat) and str(lat) != "-" else None
                    lon_val = float(lon) if pd.notna(lon) and str(lon) != "-" else None

                    rec = MonitoringData(
                        station=str(row.get("Station", "-")),
                        agency=str(row.get("Agency", "-")),
                        district=str(row.get("District", "-")).upper(),
                        tehsil=str(row.get("Tehsil", "-")).upper(),
                        block=str(row.get("Block", "-")).upper(),
                        village=str(row.get("Village", "-")).upper(),
                        latitude=lat_val,
                        longitude=lon_val,
                        parameter=parameter,
                        acquisition_time=acq_time,
                        value=float(val),
                        unit=unit,
                        dataset_source=filename
                    )
                    db_chunk.append(rec)

                if db_chunk:
                    self.db.bulk_save_objects(db_chunk)
                    self.db.commit()
                    count += len(db_chunk)
                    
            logger.info(f"Ingested CSV: {filename}. Registered {count} monitoring records.")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during CSV ingestion of {filename}: {e}", exc_info=True)
            raise e

        # Update manifest
        meta = {
            "type": "monitoring_csv",
            "parameter": parameter,
            "record_count": count
        }
        DataVersioningService.register_file(filepath, meta, chunk_count=count)
        return str(count)

    def ingest_pdf(self, filepath: str) -> str:
        """Parses PDF text, generates metadata, chunks text, generates embeddings and saves to FAISS."""
        filename = os.path.basename(filepath)
        logger.info(f"Ingesting knowledge PDF: {filename}")
        
        pages_data = DocumentParser.parse_pdf(filepath)
        if not pages_data:
            logger.warning(f"No text extracted from PDF: {filepath}")
            return "0"

        # Generate base heuristics metadata based on a text sample
        sample_text = "\n".join([p["text"] for p in pages_data[:3]])
        metadata = DocumentParser.generate_metadata_heuristics(filepath, sample_text)
        
        # Calculate and inject OCR quality metrics
        total_pages = len(pages_data)
        avg_ocr_confidence = sum(p.get("ocr_confidence", 1.0) for p in pages_data) / total_pages if total_pages > 0 else 0.0
        unreadable_pages_count = sum(1 for p in pages_data if not p.get("is_valid", True))
        extracted_tables_count = sum(p.get("tables_extracted", 0) for p in pages_data)
        
        metadata["ocr_confidence"] = round(avg_ocr_confidence, 4)
        metadata["unreadable_pages"] = unreadable_pages_count
        metadata["extracted_tables_count"] = extracted_tables_count
        metadata["pages"] = total_pages
        
        # Chunk text
        chunks = []
        chunk_metadatas = []
        
        chunk_size = 750
        overlap = 150
        
        for page in pages_data:
            text = page["text"]
            page_num = page["page_number"]
            
            # Simple text slider
            words = text.split()
            step = int(chunk_size / 6) # approx words
            step_overlap = int(overlap / 6)
            
            i = 0
            while i < len(words):
                chunk_words = words[i: i + step]
                chunk_text = " ".join(chunk_words)
                
                # Check for duplicate checksum / deduplicate chunk
                meta = dict(metadata)
                meta["page_number"] = page_num
                
                chunks.append(chunk_text)
                chunk_metadatas.append(meta)
                
                i += (step - step_overlap)
                if i >= len(words) - step_overlap:
                    break

        if chunks:
            # Add to FAISS Vector store and capture embedding metrics
            embed_metrics = self.vector_store.add_texts(chunks, chunk_metadatas)
            self.vector_store._last_metrics = embed_metrics
            
            # Write to SQLite DB
            pages = len(pages_data)
            checksum = DataVersioningService.calculate_checksum(filepath)
            doc_hash = hashlib.md5(filename.encode('utf-8')).hexdigest()[:8].upper()
            doc_id = f"DOC-{doc_hash}"
            
            # Deduplicate DB records
            self.db.query(Document).filter(Document.document_id == doc_id).delete()
            self.db.query(Chunk).filter(Chunk.document_id == doc_id).delete()
            self.db.commit()
            
            db_doc = Document(
                document_id=doc_id,
                title=metadata.get("document_name") or filename.replace("_", " ").replace(".pdf", ""),
                source=metadata.get("source") or "CGWB",
                collection=metadata.get("category") or "Unknown",
                version=metadata.get("version") or "1.0",
                pages=pages,
                chunks=len(chunks),
                embedding_model=metadata.get("embedding_version") or Config.EMBEDDING_MODEL_NAME,
                checksum=checksum,
                district=metadata.get("district")
            )
            self.db.add(db_doc)
            self.db.commit()
            
            db_chunks = []
            for idx, (chunk_text, chunk_meta) in enumerate(zip(chunks, chunk_metadatas)):
                chunk_id = f"{doc_id}-CH-{idx+1:04d}"
                db_chunk = Chunk(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    page_number=chunk_meta.get("page_number"),
                    section_title=chunk_meta.get("category"),
                    text=chunk_text
                )
                db_chunks.append(db_chunk)
            
            self.db.bulk_save_objects(db_chunks)
            self.db.commit()
            
            try:
                from app.embeddings.bm25 import BM25Manager
                BM25Manager.get_instance().rebuild_index()
            except Exception as e:
                logger.error(f"Failed to rebuild BM25 index: {e}")
            
        # Log to manifest
        metadata["checksum"] = DataVersioningService.calculate_checksum(filepath)
        DataVersioningService.register_file(filepath, metadata, chunk_count=len(chunks))
        
        logger.info(f"Ingested PDF: {filename}. Registered {len(chunks)} text chunks in FAISS.")
        return str(len(chunks))

    def ingest_file(self, filepath: str, force: bool = False) -> str:
        """Main ingestion handler. Dispatches file to appropriate sub-pipeline based on format."""
        if not self.validate_file(filepath):
            return "0"
            
        filename = os.path.basename(filepath)
        
        # Check duplicate
        import hashlib
        is_dup = DataVersioningService.is_file_duplicate(filepath)
        db_exists = True
        
        if is_dup:
            ext = os.path.splitext(filepath)[1].lower()
            if ext == ".pdf":
                doc_hash = hashlib.md5(filename.encode('utf-8')).hexdigest()[:8].upper()
                doc_id = f"DOC-{doc_hash}"
                db_exists = self.db.query(Document).filter(Document.document_id == doc_id).count() > 0
            elif ext == ".csv":
                db_exists = self.db.query(MonitoringData).filter(MonitoringData.dataset_source == filename).count() > 0
            elif ext in [".xlsx", ".xls"]:
                level = "firka" if "firka" in filename.lower() or "firka" in filepath.lower() else "district"
                if level == "district":
                    db_exists = self.db.query(DistrictAssessment).count() > 0
                else:
                    db_exists = self.db.query(FirkaAssessment).count() > 0

        if not force and is_dup and db_exists:
            logger.info(f"File {filename} has already been ingested. Skipping (force=False).")
            return "duplicate"


        ext = os.path.splitext(filepath)[1].lower()
        if ext in [".xlsx", ".xls"]:
            return self.ingest_excel(filepath)
        elif ext == ".csv":
            return self.ingest_csv(filepath)
        elif ext == ".pdf":
            return self.ingest_pdf(filepath)
        return "0"

    def auto_ingest_workspace(self, force: bool = False):
        """Walks pdf and structured data folders and ingests all missing source data."""
        logger.info("Starting automated workspace ingestion...")
        
        # 1. Ingest GEC Excel data
        excel_dirs = [
            Config.STRUCTURED_DATA_DIR / "district",
            Config.STRUCTURED_DATA_DIR / "firka"
        ]
        for edir in excel_dirs:
            if edir.exists():
                for file in os.listdir(edir):
                    if file.endswith((".xlsx", ".xls")):
                        fpath = edir / file
                        self.ingest_file(str(fpath), force=force)

        # 2. Ingest CSV level datasets inside PDF directory
        csv_dirs = [
            Config.PDF_DIR / "groundwater level",
            Config.PDF_DIR / "rainfall",
            Config.PDF_DIR / "river_discharge",
            Config.PDF_DIR / "river_water_level"
        ]
        for cdir in csv_dirs:
            if cdir.exists():
                for file in os.listdir(cdir):
                    if file.endswith(".csv"):
                        fpath = cdir / file
                        self.ingest_file(str(fpath), force=force)

        # 3. Ingest PDF files inside PDF directory recursively
        for root, dirs, files in os.walk(Config.PDF_DIR):
            for file in files:
                if file.endswith(".pdf"):
                    fpath = os.path.join(root, file)
                    self.ingest_file(str(fpath), force=force)
                    
        logger.info("Automated workspace ingestion complete.")
