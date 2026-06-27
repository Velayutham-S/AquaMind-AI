import re
from typing import Dict, Any, Optional
from app.database import SessionLocal
from app.resolution import LocationResolver
from app.logging_config import logger

class EntityExtractor:
    """Extracts structural entities (locations, years, variables, parameter metrics) from user queries."""

    @classmethod
    def extract_entities(cls, query: str) -> Dict[str, Any]:
        """Extracts location entities, years, variables, and parameters from a clean query."""
        db = SessionLocal()
        entities = {
            "location": None,
            "location_type": None,
            "year": None,
            "parameter": None,
            "variables": []
        }

        try:
            # 1. Extract Year Ranges YYYY-YYYY or YYYY
            # e.g., "2024-2025" or "2024"
            year_match = re.search(r'\b(20\d{2}-\d{4}|20\d{2})\b', query)
            if year_match:
                raw_year = year_match.group(1)
                # Expand year to standard GEC cycle if YYYY
                if "-" not in raw_year:
                    val = int(raw_year)
                    entities["year"] = f"{val-1}-{val}"
                else:
                    entities["year"] = raw_year

            # 2. Extract Location (resolve via DB-seeded cache resolver)
            # Filter out common stop words to avoid false positive location matching
            IGNORE_WORDS = {
                "what", "is", "the", "recharge", "for", "in", "to", "of", "and", "a", "an",
                "where", "how", "why", "who", "show", "data", "status", "level", "year", "report",
                "groundwater", "ground", "water", "detail", "extraction", "aquifer", "district",
                "firka", "village", "taluk", "block", "station", "monitoring", "quality", "average",
                "demand", "demands", "historical", "trend", "forecast", "projection", "simulate",
                "what-if", "whatif", "scenario", "with", "from", "at", "by", "on", "are", "be"
            }
            words = re.findall(r'\b[A-Za-z]+\b', query)
            
            # Simple chunk-based location lookup: check combinations of 1 to 2 words
            resolved_loc = None
            resolved_type = None
            
            for i in range(len(words)):
                for l in range(2, 0, -1):
                    if i + l <= len(words):
                        phrase = " ".join(words[i:i+l])
                        # If the phrase is just ignored words, skip it
                        if all(w.lower() in IGNORE_WORDS for w in phrase.split()):
                            continue
                        res = LocationResolver.resolve_location(db, phrase, threshold=0.85)
                        if res and res["resolved"]:
                            resolved_loc = res["resolved"]
                            resolved_type = res["type"]
                            break
                if resolved_loc:
                    break

            entities["location"] = resolved_loc
            entities["location_type"] = resolved_type

            # 3. Parameter detection
            query_lower = query.lower()
            if "recharge" in query_lower:
                entities["parameter"] = "total_recharge"
            elif "extraction" in query_lower or "draft" in query_lower:
                entities["parameter"] = "total_extraction"
            elif "stage" in query_lower:
                entities["parameter"] = "stage_of_extraction"
            elif "water level" in query_lower or "depth" in query_lower:
                entities["parameter"] = "groundwater_level"
            elif "rainfall" in query_lower or "rain" in query_lower:
                entities["parameter"] = "rainfall"
            elif "quality" in query_lower or "tds" in query_lower:
                entities["parameter"] = "groundwater_quality"

            # 4. Simulation variables (e.g. "+10%", "-20%")
            vars_found = re.findall(r'[+-]?\d+%', query)
            if vars_found:
                entities["variables"] = vars_found

            logger.info(f"Extracted entities: {entities}")
        except Exception as e:
            logger.error(f"Error during entity extraction: {e}", exc_info=True)
        finally:
            db.close()

        return entities
