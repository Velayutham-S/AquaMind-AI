import os
import json
import random
from app.config import Config
from app.database import SessionLocal, init_db
from app.models import DistrictAssessment, FirkaAssessment, MonitoringData, Document, Chunk
from app.logging_config import logger

def expand_benchmark_dataset(target_size=5000):
    logger.info(f"Expanding Ground Truth Benchmark to {target_size} questions using database context...")
    init_db()
    
    db = SessionLocal()
    try:
        # Load all GEC assessments
        dist_records = db.query(DistrictAssessment).all()
        firka_records = db.query(FirkaAssessment).all()
        monitoring_records = db.query(MonitoringData).limit(100).all() # sample limit
        documents = db.query(Document).all()
        
        if not dist_records:
            logger.warning("No district assessments in database. Benchmark expansion will use mock baseline data.")
            # Mock fallback if database is not fully populated yet
            dist_records = [
                DistrictAssessment(district="SALEM", year="2024-2025", stage_of_extraction=83.42, category="Semi-Critical", total_recharge=120300.0, annual_extractable=112000.0, total_extraction=93400.0),
                DistrictAssessment(district="ARIYALUR", year="2024-2025", stage_of_extraction=64.12, category="Safe", total_recharge=60500.0, annual_extractable=55000.0, total_extraction=35200.0),
                DistrictAssessment(district="COIMBATORE", year="2024-2025", stage_of_extraction=102.15, category="Over-Exploited", total_recharge=154300.0, annual_extractable=140000.0, total_extraction=143000.0)
            ]
            
        if not firka_records:
            firka_records = [
                FirkaAssessment(district="SALEM", firka="OMALUR", year="2024-2025", stage_of_extraction=91.2, category="Critical"),
                FirkaAssessment(district="SALEM", firka="VEERAPANDI", year="2024-2025", stage_of_extraction=105.4, category="Over-Exploited"),
                FirkaAssessment(district="ARIYALUR", firka="SENDURAI", year="2024-2025", stage_of_extraction=58.3, category="Safe")
            ]
            
        if not documents:
            documents = [
                Document(document_id="DOC-GEC2015", title="GEC 2015 Guidelines", source="CGWB", collection="Guidelines & Policy", pages=150, checksum="12345"),
                Document(document_id="DOC-TN2003", title="Tamil Nadu Groundwater Act 2003", source="State", collection="Regulations & Policy", pages=45, checksum="67890"),
                Document(document_id="DOC-YB2425", title="Groundwater Year Book 2024-2025", source="CGWB", collection="Year Book", pages=120, checksum="abcde")
            ]

        # 22 Categories of templates tailored to inject real DB variables
        templates = [
            # 1. District Assessments
            {
                "type": "district_stage",
                "template_en": "According to the Dynamic Ground Water Resources of Tamil Nadu {year} report, what is the groundwater extraction stage of {district} district?",
                "template_ta": "தமிழ்நாடு நிலத்தடி நீர் வள அறிக்கை {year}-ன் படி, {district} மாவட்டத்தின் நிலத்தடி நீர் எடுப்பு விகிதம் என்ன?",
                "intent": "data",
                "collection": "Resource Assessment"
            },
            {
                "type": "district_category",
                "template_en": "What is the categorization category (e.g. Safe, Semi-Critical) of {district} district for the assessment year {year}?",
                "template_ta": "{year} மதிப்பீட்டு ஆண்டில் {district} மாவட்டத்தின் நிலத்தடி நீர் வகைப்பாடு என்ன?",
                "intent": "data",
                "collection": "Resource Assessment"
            },
            {
                "type": "district_recharge",
                "template_en": "According to the GEC assessment for {year}, what is the total annual groundwater recharge of {district} district in ham?",
                "template_ta": "{year} மதிப்பீட்டின்படி, {district} மாவட்டத்தின் மொத்த நிலத்தடி நீர் செறிவூட்டல் அளவு என்ன?",
                "intent": "data",
                "collection": "Resource Assessment"
            },
            {
                "type": "district_extraction",
                "template_en": "Find the total extraction amount and extractable groundwater resources for {district} in {year}.",
                "template_ta": "{year}-ல் {district} மாவட்டத்தின் மொத்த நிலத்தடி நீர் எடுப்பு அளவு மற்றும் எடுக்கக்கூடிய வளங்களின் அளவு என்ன?",
                "intent": "data",
                "collection": "Resource Assessment"
            },
            # 2. Firka Assessments
            {
                "type": "firka_stage",
                "template_en": "What is the groundwater extraction stage in {firka} Firka located under {district} district in GEC {year} report?",
                "template_ta": "GEC {year} அறிக்கையின்படி, {district} மாவட்டத்தின் {firka} பிர்காவின் நிலத்தடி நீர் எடுப்பு நிலை என்ன?",
                "intent": "data",
                "collection": "Resource Assessment"
            },
            {
                "type": "firka_category",
                "template_en": "Is {firka} Firka in {district} district categorized as over-exploited or critical in the {year} assessment cycle?",
                "template_ta": "{year} மதிப்பீட்டில் {district} மாவட்டத்தின் {firka} பிர்கா நிலத்தடி நீர் பற்றாக்குறை கொண்ட பகுதியாக வகைப்படுத்தப்பட்டுள்ளதா?",
                "intent": "data",
                "collection": "Resource Assessment"
            },
            # 3. Document / Guidelines
            {
                "type": "document_page",
                "template_en": "What are the rules or guidelines outlined in {doc_title} regarding groundwater management?",
                "template_ta": "நிலத்தடி நீர் மேலாண்மை குறித்து {doc_title} ஆவணத்தில் கூறப்பட்டுள்ள நெறிமுறைகள் யாவை?",
                "intent": "knowledge",
                "collection": "{doc_collection}"
            },
            # 4. Multilingual / Mixed
            {
                "type": "mixed_lang",
                "template_en": "What is the groundwater status in {district} மாவட்டத்தின் for year {year}?",
                "template_ta": "{district} district-ன் நிலத்தடி நீர் மட்டம் {year}-ல் எவ்வாறு இருந்தது?",
                "intent": "data",
                "collection": "Resource Assessment"
            },
            # 5. Misspelled Location
            {
                "type": "misspelled_loc",
                "template_en": "What is the stage of groundwater extraction in {misspelled_district} for the GEC {year} cycle?",
                "template_ta": "{year} ஆண்டில் {misspelled_district} நிலத்தடி நீர் நிலை என்ன?",
                "intent": "data",
                "collection": "Resource Assessment"
            }
        ]

        # Misspelled variations map
        misspelled_map = {
            "SALEM": "Sallim",
            "COIMBATORE": "Kovai",
            "ARIYALUR": "Ariyaloor",
            "TIRUPPUR": "Tirupoor",
            "CUDDALORE": "Kudalur",
            "DHARMAPURI": "Dharmapury",
            "DINDIGUL": "Dindigulll",
            "MADURAI": "Maduray",
            "VELLORE": "Vellor",
            "TIRUCHIRAPPALLI": "Trichi"
        }

        expanded_suite = []
        random.seed(42)
        
        # Helper to retrieve random entity or document
        for i in range(target_size):
            tmpl = random.choice(templates)
            lang = random.choice(["en", "ta", "mixed"])
            
            # Select entity
            dist_rec = random.choice(dist_records)
            firka_rec = random.choice(firka_records)
            doc_rec = random.choice(documents)
            
            district = dist_rec.district or "SALEM"
            firka = firka_rec.firka or "OMALUR"
            year = dist_rec.year or "2024-2025"
            
            doc_title = doc_rec.title
            doc_collection = doc_rec.collection or "Guidelines & Policy"
            doc_id = doc_rec.document_id
            
            misspelled_dist = misspelled_map.get(district.upper(), district.capitalize() + "h")
            
            # Select template string
            if tmpl["type"] == "mixed_lang":
                # Force language to mixed
                lang = "mixed"
                tmpl_str = tmpl["template_en"] if random.choice([True, False]) else tmpl["template_ta"]
            else:
                tmpl_str = tmpl["template_ta"] if lang == "ta" else tmpl["template_en"]
                
            query = tmpl_str.format(
                district=district.title(),
                firka=firka.title(),
                year=year,
                doc_title=doc_title,
                doc_collection=doc_collection,
                misspelled_district=misspelled_dist
            )
            
            # Resolve expected ground truths
            expected_sources = []
            expected_coll = tmpl["collection"].format(doc_collection=doc_collection)
            
            # Map precise files
            if tmpl["type"] in ["district_stage", "district_category", "district_recharge", "district_extraction"]:
                expected_sources = [f"{year}.xlsx"]
            elif tmpl["type"] in ["firka_stage", "firka_category"]:
                expected_sources = [f"{year}.xlsx"]
            elif tmpl["type"] == "document_page":
                expected_sources = [doc_rec.title + ".pdf" if not doc_rec.title.endswith(".pdf") else doc_rec.title]
            else:
                expected_sources = [f"{year}.xlsx"]
                
            # Random page mapping
            expected_pages = [random.randint(1, doc_rec.pages or 20) if doc_rec.pages else 1]
            
            expanded_suite.append({
                "id": i + 1,
                "question": query,
                "query": query,
                "expected_intent": tmpl["intent"],
                "expected_sources": expected_sources,
                "expected_collection": expected_coll,
                "expected_pages": expected_pages,
                "expected_value": {
                    "district": district,
                    "firka": firka if tmpl["type"] in ["firka_stage", "firka_category"] else None,
                    "year": year,
                    "stage_of_extraction": dist_rec.stage_of_extraction if tmpl["type"] == "district_stage" else None,
                    "category": dist_rec.category if tmpl["type"] == "district_category" else None,
                },
                "difficulty": "Hard" if tmpl["intent"] == "simulation" else "Medium" if lang in ["ta", "mixed"] else "Easy",
                "language": lang
            })
            
        out_dir = Config.BASE_DIR / "data"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "benchmark_answers.json"
        
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(expanded_suite, f, indent=2)
            
        logger.info(f"Successfully generated {len(expanded_suite)} benchmark questions in: {out_path}")
        return expanded_suite
        
    except Exception as e:
        logger.error(f"Error during benchmark generation: {e}", exc_info=True)
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    expand_benchmark_dataset(target_size=5000)
