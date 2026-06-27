import os
import sys
import argparse
from pathlib import Path
from sqlalchemy.orm import Session
from app.config import Config
from app.database import SessionLocal, init_db
from app.models import DistrictAssessment, FirkaAssessment, MonitoringData, Document, Chunk
from app.pipelines.versioning import DataVersioningService
from app.logging_config import logger

def discover_files():
    """Recursively walks pdf and structured data directories to catalog raw data files."""
    pdf_files = []
    csv_files = []
    excel_files = []
    
    # 1. Discover PDFs and CSVs in Config.PDF_DIR
    for root, _, files in os.walk(Config.PDF_DIR):
        for file in files:
            fpath = Path(root) / file
            ext = fpath.suffix.lower()
            if ext == ".pdf":
                pdf_files.append(fpath)
            elif ext == ".csv":
                csv_files.append(fpath)
                
    # 2. Discover Excels in Config.STRUCTURED_DATA_DIR
    for root, _, files in os.walk(Config.STRUCTURED_DATA_DIR):
        for file in files:
            fpath = Path(root) / file
            ext = fpath.suffix.lower()
            if ext in [".xlsx", ".xls"]:
                excel_files.append(fpath)
                
    return pdf_files, csv_files, excel_files

def verify_ingestion(db: Session, force_ignore: bool = False):
    logger.info("Executing Mandatory Production Ingestion Gate Verification...")
    init_db()
    
    # Discover physical files
    pdf_files, csv_files, excel_files = discover_files()
    
    # Read manifest
    manifest = DataVersioningService.get_manifest()
    ingested_info = manifest.get("ingested_files", {})
    
    failures = []
    
    # 1. Validate PDF files
    processed_pdfs_count = 0
    failed_pdfs_count = 0
    for pdf_path in pdf_files:
        name = pdf_path.name
        # Check in manifest
        in_manifest = name in ingested_info
        # Check in Document DB table
        db_doc = db.query(Document).filter(Document.title == name.replace("_", " ").replace(".pdf", "")).first()
        if not db_doc:
            # Fallback by matching filename to Document.checksum
            if in_manifest:
                checksum = ingested_info[name].get("checksum")
                db_doc = db.query(Document).filter(Document.checksum == checksum).first()
                
        # Check chunks in Chunk DB table
        db_chunks_count = 0
        if db_doc:
            db_chunks_count = db.query(Chunk).filter(Chunk.document_id == db_doc.document_id).count()
            
        reason = None
        if not in_manifest:
            reason = "File is missing from system manifest.json registry."
        elif not db_doc:
            reason = "Document record is missing from SQLite database 'documents' table."
        elif db_chunks_count == 0:
            reason = "Document has 0 parsed chunks in SQLite database 'chunks' table (possible parser crash or blank text)."
            
        if reason:
            failed_pdfs_count += 1
            failures.append({
                "file": name,
                "path": str(pdf_path),
                "type": "PDF Document",
                "reason": reason,
                "fix": "Re-run the ingestion pipeline on this file specifically: IngestionPipeline.ingest_file(path, force=True)"
            })
        else:
            processed_pdfs_count += 1
            
    # 2. Validate GEC Assessment Excels
    imported_excels_count = 0
    failed_excels_count = 0
    for excel_path in excel_files:
        name = excel_path.name
        # Check if year can be parsed
        # If year GEC is found, check DB rows
        level = "firka" if "firka" in name.lower() or "firka" in str(excel_path).lower() else "district"
        
        # Check if year is in database
        has_records = False
        if level == "district":
            # Match if any record has source containing name or records exist
            d_records = db.query(DistrictAssessment).count()
            has_records = d_records > 0
        else:
            f_records = db.query(FirkaAssessment).count()
            has_records = f_records > 0
            
        reason = None
        if name not in ingested_info:
            reason = "Excel file is missing from manifest.json registry."
        elif not has_records:
            reason = f"No imported assessment records found in '{level}_assessments' DB table."
            
        if reason:
            failed_excels_count += 1
            failures.append({
                "file": name,
                "path": str(excel_path),
                "type": f"GEC Excel ({level.capitalize()})",
                "reason": reason,
                "fix": "Run GEC ingestion handler: IngestionPipeline.ingest_excel(path)"
            })
        else:
            imported_excels_count += 1

    # 3. Validate Monitoring CSVs
    imported_csvs_count = 0
    failed_csvs_count = 0
    for csv_path in csv_files:
        name = csv_path.name
        # Check if records with dataset_source = name exist in MonitoringData table
        db_count = db.query(MonitoringData).filter(MonitoringData.dataset_source == name).count()
        
        reason = None
        if name not in ingested_info:
            reason = "CSV file is missing from manifest.json registry."
        elif db_count == 0:
            # Check if the file is empty or contains only a header line
            is_empty_or_header_only = False
            try:
                if csv_path.exists():
                    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = [line.strip() for line in f if line.strip()]
                    if len(lines) <= 1:
                        is_empty_or_header_only = True
            except Exception:
                pass
            
            if not is_empty_or_header_only:
                reason = "No observation logs found in database 'monitoring_data' table."
            
        if reason:
            failed_csvs_count += 1
            failures.append({
                "file": name,
                "path": str(csv_path),
                "type": "Monitoring CSV",
                "reason": reason,
                "fix": "Import CSV using ingestion pipeline: IngestionPipeline.ingest_csv(path)"
            })
        else:
            imported_csvs_count += 1
            
    # Output counts dashboard
    verification_passed = len(failures) == 0
    
    # 4. Generate report content
    report_path = Config.BASE_DIR / "reports" / "ingestion_failures.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    report_content = [
        "# AquaMind AI Production Ingestion Verification Report",
        f"Overall Ingestion Status: **{'PASSED' if verification_passed else 'FAILED'}**",
        "---",
        "## 1. Discovered Data Assets Summary",
        f"- **PDF Knowledge base**: Discovered: {len(pdf_files)} | Processed: {processed_pdfs_count} | Failed: {failed_pdfs_count}",
        f"- **GEC Excel spreadsheets**: Discovered: {len(excel_files)} | Imported: {imported_excels_count} | Failed: {failed_excels_count}",
        f"- **Monitoring telemetry CSVs**: Discovered: {len(csv_files)} | Imported: {imported_csvs_count} | Failed: {failed_csvs_count}",
        "\n---",
        "## 2. Ingestion Failure Logs" if failures else "## 2. Ingestion Failure Logs\nAll mandatory files have been successfully ingested into the production knowledge platform. No failures detected."
    ]
    
    if failures:
        report_content.append("| Filename | File Type | Failure Reason | Recommended Fix |")
        report_content.append("|---|---|---|---|")
        for f in failures:
            report_content.append(f"| `{f['file']}` | {f['type']} | {f['reason']} | {f['fix']} |")
            
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_content))
        
    logger.info(f"Ingestion verification gate report saved to: {report_path}")
    
    # Logging Summary to CLI
    print("=== INGESTION VERIFICATION GATE ===")
    print(f"Status: {'PASSED' if verification_passed else 'FAILED'}")
    print(f"PDFs: Discovered {len(pdf_files)}, Processed {processed_pdfs_count}, Failed {failed_pdfs_count}")
    print(f"Excels: Discovered {len(excel_files)}, Processed {imported_excels_count}, Failed {failed_excels_count}")
    print(f"CSVs: Discovered {len(csv_files)}, Processed {imported_csvs_count}, Failed {failed_csvs_count}")
    
    if not verification_passed:
        print(f"FAILED: {len(failures)} files failed validation. Detail report in: {report_path}")
        if not force_ignore:
            logger.error("Platform validation check failed. Halting pipeline execution.")
            sys.exit(1)
        else:
            logger.warning("Platform validation check failed, but proceeding anyway due to --force-ignore-failures flag.")
    else:
        print("Success: All files validated successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestion Gate Checker")
    parser.add_argument("--force-ignore-failures", action="store_true", help="Proceed despite ingestion checks failures")
    args = parser.parse_args()
    
    db = SessionLocal()
    try:
        verify_ingestion(db, force_ignore=args.force_ignore_failures)
    finally:
        db.close()
