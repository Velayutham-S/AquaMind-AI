import os
import re
import pandas as pd
import pdfplumber
from datetime import datetime
from app.logging_config import logger

class DocumentParser:
    @staticmethod
    def parse_pdf(filepath: str) -> list:
        """Extracts text and page-level metadata from a PDF file with strict quality validation checks,
        automatically falling back to pypdfium2 and running OCR (easyocr/pytesseract) on demand if scanned/image-only."""
        pages_data = []
        pdf_opened = False
        parser_used = "pdfplumber"
        
        # 1. Attempt parsing with pdfplumber first
        try:
            with pdfplumber.open(filepath) as pdf:
                num_pages = len(pdf.pages)
                if num_pages > 0:
                    pdf_opened = True
                    logger.info(f"Parsing PDF with pdfplumber: {filepath} ({num_pages} pages)")
                    for idx, page in enumerate(pdf.pages):
                        text = page.extract_text() or ""
                        text = re.sub(r'\s+', ' ', text).strip()
                        
                        # Find tables
                        tables = page.find_tables()
                        tables_extracted = len(tables) if tables else 0
                        
                        pages_data.append({
                            "page_number": idx + 1,
                            "text": text,
                            "tables_extracted": tables_extracted,
                            "is_valid": True,
                            "error_reason": None,
                            "ocr_confidence": 1.0
                        })
        except Exception as e:
            logger.warning(f"pdfplumber failed to parse {filepath}: {e}. Retrying with pypdfium2 fallback.")
            
        # 2. Fallback to pypdfium2 if pdfplumber failed or extracted 0 pages
        if not pdf_opened or not pages_data:
            parser_used = "pypdfium2"
            try:
                import pypdfium2 as pdfium
                doc = pdfium.PdfDocument(filepath)
                num_pages = len(doc)
                pdf_opened = True
                logger.info(f"Parsing PDF with pypdfium2 (fallback): {filepath} ({num_pages} pages)")
                
                pages_data = []
                for idx in range(num_pages):
                    page = doc[idx]
                    text = page.get_textpage().get_text_range() or ""
                    text = re.sub(r'\s+', ' ', text).strip()
                    
                    pages_data.append({
                        "page_number": idx + 1,
                        "text": text,
                        "tables_extracted": 0,  # pypdfium2 does not support table detection natively
                        "is_valid": True,
                        "error_reason": None,
                        "ocr_confidence": 1.0
                    })
            except Exception as e:
                logger.error(f"pypdfium2 fallback failed to parse {filepath}: {e}")
                
        # 3. Handle corrupted PDF
        if not pdf_opened:
            err_msg = f"Corrupted PDF: Failed to open or parse file {filepath} using both pdfplumber and pypdfium2."
            logger.error(err_msg)
            raise ValueError(err_msg)

        # 4. Check if OCR is required (average characters per page < 30)
        total_text_len = sum(len(p["text"]) for p in pages_data)
        avg_text_len = total_text_len / len(pages_data) if pages_data else 0
        ocr_required = len(pages_data) > 0 and avg_text_len < 30.0
        
        if ocr_required:
            logger.warning(f"Detected scanned/image-only PDF (average page text length: {avg_text_len:.1f} chars). Initializing OCR engine...")
            try:
                import pypdfium2 as pdfium
                import numpy as np
                from PIL import Image
                
                doc = pdfium.PdfDocument(filepath)
                
                # Lazy-load easyocr
                import easyocr
                logger.info("Initializing EasyOCR with CUDA support...")
                reader = easyocr.Reader(['en'], gpu=True)
                
                for p_idx, page_item in enumerate(pages_data):
                    logger.info(f"Running OCR on page {p_idx+1}/{len(pages_data)}...")
                    page = doc[p_idx]
                    bitmap = page.render(scale=2.0) # render at 144 DPI
                    pil_img = bitmap.to_pil()
                    
                    # Convert to numpy array for easyocr
                    img_np = np.array(pil_img)
                    ocr_res = reader.readtext(img_np, detail=0)
                    ocr_text = " ".join(ocr_res)
                    ocr_text = re.sub(r'\s+', ' ', ocr_text).strip()
                    
                    page_item["text"] = ocr_text
                    page_item["ocr_confidence"] = 0.90
                    page_item["is_valid"] = len(ocr_text) > 10
                    if not page_item["is_valid"]:
                        page_item["error_reason"] = "OCR failed to extract readable text"
            except Exception as e:
                logger.error(f"EasyOCR failed: {e}. Attempting pytesseract fallback...")
                try:
                    import pytesseract
                    import pypdfium2 as pdfium
                    doc = pdfium.PdfDocument(filepath)
                    for p_idx, page_item in enumerate(pages_data):
                        page = doc[p_idx]
                        bitmap = page.render(scale=2.0)
                        pil_img = bitmap.to_pil()
                        
                        ocr_text = pytesseract.image_to_string(pil_img)
                        ocr_text = re.sub(r'\s+', ' ', ocr_text).strip()
                        
                        page_item["text"] = ocr_text
                        page_item["ocr_confidence"] = 0.80
                        page_item["is_valid"] = len(ocr_text) > 10
                        if not page_item["is_valid"]:
                            page_item["error_reason"] = "OCR failed to extract readable text"
                except Exception as t_err:
                    logger.error(f"pytesseract fallback also failed: {t_err}")
                    # Keep empty text, flag as invalid
                    for page_item in pages_data:
                        if not page_item["text"]:
                            page_item["is_valid"] = False
                            page_item["error_reason"] = "Image-only PDF (OCR engines unavailable or failed)"
                            page_item["ocr_confidence"] = 0.0

        # 5. Run final quality heuristics validation on extracted text
        for page_item in pages_data:
            text = page_item["text"]
            page_num = page_item["page_number"]
            
            # Skip if already flagged as invalid by OCR block
            if not page_item["is_valid"]:
                continue
                
            non_printable = len(re.findall(r'[^\x20-\x7E\s\u0b80-\u0bff]', text))
            total_len = len(text)
            ocr_confidence = page_item.get("ocr_confidence", 1.0)
            
            if total_len > 0:
                non_print_ratio = non_printable / total_len
                ocr_confidence = min(ocr_confidence, max(0.0, 1.0 - non_print_ratio))
            else:
                ocr_confidence = 0.0
                
            page_item["ocr_confidence"] = ocr_confidence
            
            is_valid = True
            reason = None
            if not text:
                is_valid = False
                reason = "Empty Page (Possible Scanned Image without OCR)"
            else:
                if total_len > 0 and (non_printable / total_len) > 0.3:
                    is_valid = False
                    reason = "High Non-Printable Character Ratio (Corrupted/Scrambled text)"
                elif len(text.strip()) < 10:
                    is_valid = False
                    reason = "Too Short (Possible corrupted page or blank page)"
            
            page_item["is_valid"] = is_valid
            page_item["error_reason"] = reason

        return pages_data


    @staticmethod
    def generate_metadata_heuristics(filepath: str, text_sample: str) -> dict:
        """Generates rich metadata using heuristics from filename and content sample."""
        filename = os.path.basename(filepath)
        
        # 1. Detect Year
        year_match = re.search(r'(20\d{2}-\d{2,4}|20\d{2})', filename)
        year = year_match.group(1) if year_match else None
        if not year:
            year_match_text = re.search(r'year\s+(20\d{2}-\d{2,4}|20\d{2})', text_sample, re.IGNORECASE)
            year = year_match_text.group(1) if year_match_text else datetime.now().year
            
        # Convert 2024-25 to 2024-2025 standard
        if year and "-" in str(year):
            parts = str(year).split("-")
            if len(parts[1]) == 2:
                year = f"{parts[0]}-20{parts[1]}"
                
        # 2. Detect District
        districts = [
            "Ariyalur", "Chengalpattu", "Chennai", "Coimbatore", "Cuddalore", "Dharmapuri",
            "Dindigul", "Erode", "Kallakurichi", "Kancheepuram", "Kanyakumari", "Karur",
            "Krishnagiri", "Madurai", "Mayiladuthurai", "Nagapattinam", "Namakkal", "Nilgiris",
            "Perambalur", "Pudukkottai", "Ramanathapuram", "Ranipet", "Salem", "Sivaganga",
            "Tenkasi", "Thanjavur", "Theni", "Thiruvallur", "Thiruvarur", "Thoothukudi",
            "Tiruchirappalli", "Tirunelveli", "Tirupathur", "Tiruppur", "Tiruvannamalai",
            "Vellore", "Viluppuram", "Virudhunagar"
        ]
        doc_district = None
        for dist in districts:
            if dist.lower() in filename.lower() or dist.lower() in text_sample[:2000].lower():
                doc_district = dist
                break

        # 3. Detect Category
        category = "General Science"
        if "guideline" in filename.lower() or "gec" in filename.lower():
            category = "Guidelines & Policy"
        elif "quality" in filename.lower() or "pollution" in filename.lower():
            category = "Water Quality"
        elif "recharge" in filename.lower():
            category = "Artificial Recharge"
        elif "model" in filename.lower() or "flow" in filename.lower() or "simulation" in filename.lower():
            category = "Modelling & Simulation"
        elif "assess" in filename.lower() or "resource" in filename.lower():
            category = "Resource Assessment"
        elif "regulation" in filename.lower() or "act" in filename.lower() or "law" in filename.lower():
            category = "Regulations & Policy"
        elif "year book" in filename.lower() or "yearbook" in filename.lower():
            category = "Year Book"
        elif "faq" in filename.lower():
            category = "FAQ"

        # 4. Source & Source Authority
        source = "CGWB" # Central Ground Water Board default
        source_authority = "Central"
        if "sw_gw" in filename.lower() or "state" in filename.lower():
            source = "State Ground & Surface Water Resources Data Centre"
            source_authority = "State"

        # 5. Language
        language = "English"
        if re.search(r'[\u0b80-\u0bff]+', text_sample):
            language = "Tamil"

        # 6. River Basin
        river_basins = ["Cauvery", "Palar", "Vaigai", "Pennaiyar", "Tamirabarani", "Vellar", "Noyyal", "Bhavani"]
        detected_basin = None
        for basin in river_basins:
            if basin.lower() in filename.lower() or basin.lower() in text_sample.lower():
                detected_basin = basin
                break

        # 7. Aquifer & Hydrogeological unit
        detected_aquifer = None
        aquifers = ["Alluvial", "Fissured", "Hard Rock", "Charnockite", "Crystalline"]
        for aq in aquifers:
            if aq.lower() in filename.lower() or aq.lower() in text_sample.lower():
                detected_aquifer = aq
                break
                
        hydro_unit = "Fissured Hard Rock" if "hard rock" in text_sample.lower() or "crystalline" in text_sample.lower() else "Sedimentary Alluvial"

        # 8. Monitoring / Quality type
        mon_type = "Water Level"
        if "quality" in filename.lower() or "quality" in text_sample.lower():
            mon_type = "Water Quality"
        elif "telemetry" in filename.lower() or "telemetry" in text_sample.lower():
            mon_type = "Telemetry"
            
        qual_type = "Potable"
        if "fluoride" in text_sample.lower():
            qual_type = "Fluoride Affected"
        elif "salin" in text_sample.lower():
            qual_type = "Saline"

        # 9. Assessment Cycle
        assess_cycle = "GEC 2015"
        if "gec 2022" in text_sample.lower() or "gec-2022" in text_sample.lower():
            assess_cycle = "GEC 2022"
        elif "gec 1997" in text_sample.lower():
            assess_cycle = "GEC 1997"

        # 10. Priority & Confidence
        doc_priority = "Medium"
        if "act" in filename.lower() or "regulation" in filename.lower() or "guideline" in filename.lower():
            doc_priority = "High"
            
        confidence = 0.85
        if doc_district:
            confidence += 0.10
        if detected_basin:
            confidence += 0.05

        return {
            "document_name": filename.replace(".pdf", "").replace("_", " "),
            "source": source,
            "year": year,
            "district": doc_district,
            "firka": None,
            "category": category,
            "language": language,
            "embedding_version": "bge-m3",
            "checksum": "",
            # Extended Metadata
            "river_basin": detected_basin,
            "aquifer": detected_aquifer,
            "watershed": None,
            "hydrogeological_unit": hydro_unit,
            "quality_type": qual_type,
            "monitoring_type": mon_type,
            "assessment_cycle": assess_cycle,
            "document_priority": doc_priority,
            "source_authority": source_authority,
            "confidence": min(confidence, 1.0)
        }

    @staticmethod
    def parse_excel_assessment(filepath: str, level: str = "district") -> list:
        """Parses Government GEC assessment spreadsheets using dynamic column indices."""
        filename = os.path.basename(filepath)
        year_match = re.search(r'(20\d{2}-\d{2,4})', filename)
        year = year_match.group(1) if year_match else "Unknown"
        if "-" in year:
            parts = year.split("-")
            if len(parts[1]) == 2:
                year = f"{parts[0]}-20{parts[1]}"

        # Load file raw
        df = pd.read_excel(filepath, header=None)
        
        # Locate S.No header row (typically row 6 or 7)
        header_row_idx = None
        for i in range(15):
            val = str(df.iloc[i, 0]).strip().lower()
            if "s.no" in val or "s. no" in val or "sl.no" in val:
                header_row_idx = i
                break
                
        if header_row_idx is None:
            raise ValueError(f"Could not identify header row in sheet: {filepath}")
            
        logger.info(f"Excel header row identified at index {header_row_idx} for {filename}")
        
        # Combine multi-level headers (next 3 rows if empty or subheader elements)
        row7 = df.iloc[header_row_idx].fillna("")
        row8 = df.iloc[header_row_idx + 1].fillna("")
        row9 = df.iloc[header_row_idx + 2].fillna("")
        
        full_cols = []
        for r7, r8, r9 in zip(row7, row8, row9):
            combined = f"{r7}_{r8}_{r9}".strip("_").replace(" ", "_").replace("\n", "_")
            combined = re.sub(r'_+', '_', combined)
            full_cols.append(combined)
            
        # Helper to find column index dynamically
        def find_col_idx(keywords: list) -> int:
            for idx, col in enumerate(full_cols):
                col_upper = col.upper()
                if all(kw.upper() in col_upper for kw in keywords):
                    return idx
            return None

        # Resolve core indexes
        idx_state = find_col_idx(["STATE"]) or 1
        idx_district = find_col_idx(["DISTRICT"]) or 2
        idx_firka = find_col_idx(["FIRKA"]) if level == "firka" else None
        
        # In case watershed/block details
        idx_watershed = find_col_idx(["Watershed"]) or find_col_idx(["Block"])
        
        # Recharge metrics
        idx_recharge_rain = find_col_idx(["Rainfall_Recharge", "Total"]) or find_col_idx(["Rainfall", "Total"])
        idx_recharge_total = find_col_idx(["Annual", "Recharge", "Total"]) or find_col_idx(["Annual_Ground_water_Recharge", "Total"])
        idx_extractable = find_col_idx(["Extractable", "Total"]) or find_col_idx(["Annual_Extractable", "Total"])
        
        # Extraction metrics
        idx_ext_irr = find_col_idx(["Irrigation", "Total"])
        idx_ext_dom = find_col_idx(["Domestic", "Total"])
        idx_ext_ind = find_col_idx(["Industrial", "Total"])
        idx_ext_total = find_col_idx(["Extraction", "Total"]) or find_col_idx(["all_uses", "Total"])
        
        # Stage & Category
        idx_stage = find_col_idx(["Stage", "Total"]) or find_col_idx(["Stage_of_Ground_Water_Extraction", "Total"])
        idx_category = find_col_idx(["Categorization", "Total"])
        idx_quality = find_col_idx(["Quality", "Total"]) or find_col_idx(["Quality", "NC"])
        
        logger.info(f"Columns resolved for {level}: District={idx_district}, TotalRecharge={idx_recharge_total}, Stage={idx_stage}")

        records = []
        # Data rows start after headers (typically header_row_idx + 4)
        start_data_idx = header_row_idx + 4
        
        for i in range(start_data_idx, len(df)):
            row = df.iloc[i]
            
            # Check for empty rows or footer rows
            sno_val = str(row.iloc[0]).strip().lower()
            if not sno_val or sno_val == "nan" or "total" in sno_val or "state" in sno_val:
                continue
                
            # Verify if S.No is numeric
            try:
                float(sno_val)
            except ValueError:
                # If S.No is not a number, it's likely a footer
                continue
                
            dist_val = str(row.iloc[idx_district]).strip()
            if not dist_val or dist_val == "nan" or "total" in dist_val.lower():
                continue

            # Standard clean floats
            def get_float(val):
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return 0.0

            # Extracted data mapping
            record = {
                "state": str(row.iloc[idx_state]).strip().upper(),
                "district": dist_val.upper(),
                "year": year,
                "total_recharge": get_float(row.iloc[idx_recharge_total]) if idx_recharge_total else 0.0,
                "annual_extractable": get_float(row.iloc[idx_extractable]) if idx_extractable else 0.0,
                "total_extraction": get_float(row.iloc[idx_ext_total]) if idx_ext_total else 0.0,
                "stage_of_extraction": get_float(row.iloc[idx_stage]) if idx_stage else 0.0,
                "quality_tag": str(row.iloc[idx_quality]).strip() if idx_quality and not pd.isna(row.iloc[idx_quality]) else None,
                "raw_data": {full_cols[j]: row.iloc[j] for j in range(len(row)) if not pd.isna(row.iloc[j])}
            }

            # Map category
            cat_val = None
            if idx_category:
                cat_raw = str(row.iloc[idx_category]).strip().lower()
                if cat_raw and cat_raw != "nan":
                    cat_val = cat_raw
            if not cat_val:
                # Heuristic stage based categorization
                stage = record["stage_of_extraction"]
                if stage <= 70:
                    cat_val = "safe"
                elif stage <= 90:
                    cat_val = "semi_critical"
                elif stage <= 100:
                    cat_val = "critical"
                else:
                    cat_val = "over_exploited"
            record["category"] = cat_val.replace("_", " ").title()

            if level == "district":
                record["rainfall_recharge"] = get_float(row.iloc[idx_recharge_rain]) if idx_recharge_rain else 0.0
                record["other_recharge"] = record["total_recharge"] - record["rainfall_recharge"]
                record["extraction_irrigation"] = get_float(row.iloc[idx_ext_irr]) if idx_ext_irr else 0.0
                record["extraction_domestic"] = get_float(row.iloc[idx_ext_dom]) if idx_ext_dom else 0.0
                record["extraction_industrial"] = get_float(row.iloc[idx_ext_ind]) if idx_ext_ind else 0.0
            else:
                record["firka"] = str(row.iloc[idx_firka]).strip().upper() if idx_firka else "UNKNOWN"
                record["watershed_or_block"] = str(row.iloc[idx_watershed]).strip().upper() if idx_watershed else None
                
            records.append(record)
            
        logger.info(f"Successfully parsed {len(records)} rows from GEC sheet for year {year} ({level} level)")
        return records
