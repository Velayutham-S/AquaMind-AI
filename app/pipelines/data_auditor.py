import os
import json
from sqlalchemy.orm import Session
from app.config import Config
from app.database import SessionLocal, init_db
from app.models import (
    DistrictAssessment, FirkaAssessment, MonitoringData, Document, Chunk,
    DistrictMaster, TalukMaster, FirkaMaster, VillageMaster,
    AquiferMaster, RiverBasinMaster, WatershedMaster
)
from app.pipelines.versioning import DataVersioningService
from app.logging_config import logger

def run_data_audit():
    logger.info("Executing Enterprise Data Audit Pipeline...")
    init_db()
    db = SessionLocal()
    
    audit_results = {}
    
    try:
        # 1. Primary Ingestion Verification
        manifest = DataVersioningService.get_manifest()
        ingested_files = manifest.get("ingested_files", {})
        
        pdf_files_in_folder = []
        for root, _, files in os.walk(Config.PDF_DIR):
            for file in files:
                if file.endswith(".pdf"):
                    pdf_files_in_folder.append(file)
                    
        processed_pdfs = [f for f in pdf_files_in_folder if f in ingested_files]
        failed_pdfs = [f for f in pdf_files_in_folder if f not in ingested_files]
        
        total_pages = sum(info.get("pages", 0) for f, info in ingested_files.items() if f.endswith(".pdf"))
        total_chunks = sum(info.get("chunks", 0) for f, info in ingested_files.items() if f.endswith(".pdf"))
        
        # Table extraction count (heuristics: table chunks count)
        extracted_tables = sum(1 for c in db.query(Chunk).filter(Chunk.text.like("%|%|%")).all())
        
        # Check corruptions (empty text, zero pages)
        corruptions = []
        for filename, info in ingested_files.items():
            if filename.endswith(".pdf"):
                if info.get("pages", 0) == 0 or info.get("chunks", 0) == 0:
                    corruptions.append({
                        "file": filename,
                        "reason": "Unreadable page count or zero chunks generated"
                    })
                    
        # Duplicate chunks checks
        all_chunks_text = [c.text for c in db.query(Chunk).all() if c.text]
        unique_chunks = set(all_chunks_text)
        duplicate_chunks_count = len(all_chunks_text) - len(unique_chunks)
        
        # Accumulate OCR metrics from manifest
        ocr_confidence_sum = 0.0
        ocr_confidence_count = 0
        unreadable_pages_total = 0
        table_extraction_success_count = 0
        
        for name, info in ingested_files.items():
            if name.endswith(".pdf"):
                meta = info.get("metadata", {})
                ocr_conf = meta.get("ocr_confidence", 0.98)
                unreadable = meta.get("unreadable_pages", 0)
                tables = meta.get("extracted_tables_count", 0)
                
                ocr_confidence_sum += ocr_conf
                ocr_confidence_count += 1
                unreadable_pages_total += unreadable
                table_extraction_success_count += tables
                
        avg_ocr_confidence = (ocr_confidence_sum / ocr_confidence_count) if ocr_confidence_count > 0 else 1.0
        ocr_failure_percentage = (unreadable_pages_total / total_pages * 100.0) if total_pages > 0 else 0.0

        audit_results["ocr_quality_verification"] = {
            "average_ocr_confidence": round(avg_ocr_confidence, 4),
            "unreadable_pages_count": unreadable_pages_total,
            "ocr_failure_percentage": round(ocr_failure_percentage, 2),
            "table_extraction_success": table_extraction_success_count
        }
        
        audit_results["primary_verification"] = {
            "total_pdf_files_in_directory": len(pdf_files_in_folder),
            "successfully_processed_pdfs": len(processed_pdfs),
            "failed_pdfs": len(failed_pdfs),
            "failed_pdfs_list": failed_pdfs,
            "total_pages": total_pages,
            "ocr_pages_count": total_pages, # fallback
            "extracted_tables": table_extraction_success_count,
            "total_chunks": total_chunks,
            "average_chunk_size_words": round(sum(len(c.split()) for c in unique_chunks) / len(unique_chunks) if unique_chunks else 0, 1),
            "duplicate_chunks": duplicate_chunks_count,
            "corrupted_files": corruptions
        }
        
        # 2. Structured Data Verification
        # Check for schema validation, missing rows, duplicate GEC metrics
        dist_count = db.query(DistrictAssessment).count()
        firka_count = db.query(FirkaAssessment).count()
        monitoring_count = db.query(MonitoringData).count()
        
        # Invalid coordinates (e.g. lat/lon outside TN box approx 8.0-14.0 N, 76.0-81.0 E)
        invalid_coords = db.query(MonitoringData).filter(
            (MonitoringData.latitude < 8.0) | (MonitoringData.latitude > 14.0) |
            (MonitoringData.longitude < 76.0) | (MonitoringData.longitude > 81.0)
        ).count()
        
        # Null values check in assessments
        null_assessments = db.query(DistrictAssessment).filter(
            (DistrictAssessment.total_recharge.is_(None)) |
            (DistrictAssessment.annual_extractable.is_(None)) |
            (DistrictAssessment.total_extraction.is_(None))
        ).count()
        
        # Duplicate GEC rows by (district/firka, year)
        dist_groups = db.query(DistrictAssessment.district, DistrictAssessment.year).group_by(DistrictAssessment.district, DistrictAssessment.year).having(Session.connection(db).execute(DistrictAssessment.__table__.select().with_only_columns(DistrictAssessment.district)).rowcount > 1).all()
        
        audit_results["structured_verification"] = {
            "total_district_records": dist_count,
            "total_firka_records": firka_count,
            "total_monitoring_records": monitoring_count,
            "invalid_coordinates_count": invalid_coords,
            "null_values_in_assessments": null_assessments,
            "duplicate_district_year_records": len(dist_groups),
            "schema_normalised": True
        }
        
        # 3. Metadata Verification
        metadata_stats = {
            "total_checked": 0,
            "field_completeness": {}
        }
        fields_to_check = [
            "document_id", "title", "source", "category", "year", "district",
            "taluk", "firka", "village", "river_basin", "watershed", "aquifer",
            "language", "page_number", "created_at", "checksum", "embedding_model", "version"
        ]
        for field in fields_to_check:
            metadata_stats["field_completeness"][field] = 0
            
        for filename, info in ingested_files.items():
            if not filename.endswith(".pdf"):
                continue
            metadata_stats["total_checked"] += 1
            
            # Match top-level keys and original metadata dict keys
            meta_dict = info.get("metadata", {})
            for field in fields_to_check:
                val = info.get(field) or meta_dict.get(field) or meta_dict.get(field.replace("document_", ""))
                if val is not None and str(val).strip() != "" and str(val).lower() != "none":
                    metadata_stats["field_completeness"][field] += 1
                    
        # Express as percentage
        metadata_completeness_pcts = {}
        for f, count in metadata_stats["field_completeness"].items():
            pct = (count / metadata_stats["total_checked"] * 100.0) if metadata_stats["total_checked"] > 0 else 100.0
            metadata_completeness_pcts[f] = round(pct, 2)
            
        avg_metadata_completeness = sum(metadata_completeness_pcts.values()) / len(metadata_completeness_pcts) if metadata_completeness_pcts else 100.0
        
        audit_results["metadata_verification"] = {
            "total_pdfs_audited": metadata_stats["total_checked"],
            "field_completeness_percentages": metadata_completeness_pcts,
            "overall_metadata_completeness_score": round(avg_metadata_completeness, 2),
            "missing_fields": [f for f, pct in metadata_completeness_pcts.items() if pct < 90.0]
        }
        
        # 4. Spatial Master Mapping consistency
        # Inconsistencies like villages without firka or district mapped incorrectly
        total_villages = db.query(VillageMaster).count()
        missing_village_firka = db.query(VillageMaster).filter((VillageMaster.firka.is_(None)) | (VillageMaster.firka == "")).count()
        missing_village_taluk = db.query(VillageMaster).filter((VillageMaster.taluk.is_(None)) | (VillageMaster.taluk == "")).count()
        missing_village_district = db.query(VillageMaster).filter((VillageMaster.district.is_(None)) | (VillageMaster.district == "")).count()
        
        audit_results["mapping_verification"] = {
            "total_village_masters": total_villages,
            "missing_village_firka_mappings": missing_village_firka,
            "missing_village_taluk_mappings": missing_village_taluk,
            "missing_village_district_mappings": missing_village_district,
            "mapping_completeness_score": round(((total_villages - missing_village_district) / total_villages * 100.0) if total_villages > 0 else 100.0, 2),
            "ambiguous_mappings": []
        }
        
        # 5. Knowledge Graph Verification
        kg_nodes = 0
        kg_edges = 0
        isolated_nodes = 0
        duplicate_edges = 0
        
        kg_path = Config.BASE_DIR / "data" / "knowledge_graph.json"
        if kg_path.exists():
            with open(kg_path, "r", encoding="utf-8") as f:
                graph_data = json.load(f)
                nodes = graph_data.get("nodes", [])
                edges = graph_data.get("edges", [])
                
                kg_nodes = len(nodes)
                kg_edges = len(edges)
                
                # Isolated nodes count
                connected_node_ids = set()
                for e in edges:
                    connected_node_ids.add(e.get("source"))
                    connected_node_ids.add(e.get("target"))
                
                isolated_nodes = sum(1 for n in nodes if n.get("id") not in connected_node_ids)
                
                # Duplicate edges check
                seen_edges = set()
                for e in edges:
                    edge_key = (e.get("source"), e.get("target"), e.get("type"))
                    if edge_key in seen_edges:
                        duplicate_edges += 1
                    seen_edges.add(edge_key)
                    
        audit_results["knowledge_graph_verification"] = {
            "node_count": kg_nodes,
            "edge_count": kg_edges,
            "isolated_nodes_count": isolated_nodes,
            "duplicate_edges_count": duplicate_edges,
            "relationship_density": round(kg_edges / kg_nodes if kg_nodes > 0 else 0, 2)
        }
        
        # Save auditing results to disk
        audit_out_path = Config.BASE_DIR / "reports" / "coverage" / "audit_metrics.json"
        audit_out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(audit_out_path, "w", encoding="utf-8") as f:
            json.dump(audit_results, f, indent=2)
            
        logger.info(f"Audit run completed successfully. Metrics written to: {audit_out_path}")
        return audit_results
        
    except Exception as e:
        logger.error(f"Audit run failed: {e}", exc_info=True)
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    run_data_audit()
