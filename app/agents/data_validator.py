from typing import Dict, Any, List, Tuple
from app.logging_config import logger

class DataValidator:
    """Pre-execution validation engine that audits parameters and locations to prevent runtime query errors."""

    SUPPORTED_PARAMETERS = {
        # Assessment parameters
        "rainfall_recharge", "other_recharge", "total_recharge", "annual_extractable",
        "extraction_irrigation", "extraction_domestic", "extraction_industrial", "total_extraction",
        "stage_of_extraction", "category", "quality_tag",
        # Monitoring database parameters
        "groundwater_level", "rainfall", "river_discharge", "river_level"
    }

    @classmethod
    def validate_query_entities(
        cls,
        location: str,
        location_type: str,
        year: str = None,
        parameter: str = None
    ) -> Tuple[bool, str]:
        """Validates resolved search parameters, locations, and time ranges.
        
        Returns:
            Tuple of (is_valid: bool, error_message: str)
        """
        # 1. Check location name
        if not location:
            return False, "Geographical search location is missing or not provided."
            
        # 2. Check location type
        valid_types = {"district", "taluk", "firka", "village", "aquifer", "river_basin", "watershed"}
        if not location_type or location_type not in valid_types:
            return False, f"Location type '{location_type}' is invalid. Supported categories: {', '.join(valid_types)}"
            
        # 3. Check year format (e.g. "2024-2025" or numeric like "2024")
        if year:
            # Standard GEC year is "YYYY-YYYY" or four-digit year "YYYY"
            import re
            is_range = re.match(r"^\d{4}-\d{4}$", year)
            is_digit = re.match(r"^\d{4}$", year)
            if not (is_range or is_digit):
                return False, f"Assessment year format '{year}' is invalid. Use standard formats like '2024-2025' or '2024'."
                
        # 4. Check query parameter name
        if parameter:
            cleaned_param = parameter.strip().lower()
            if cleaned_param not in cls.SUPPORTED_PARAMETERS:
                # Fuzzy match parameters to be helpful
                import difflib
                matches = difflib.get_close_matches(cleaned_param, list(cls.SUPPORTED_PARAMETERS), n=1, cutoff=0.6)
                suggest = f" Did you mean '{matches[0]}'?" if matches else ""
                return False, f"Parameter '{parameter}' is not supported in the database.{suggest} Supported parameters: {', '.join(cls.SUPPORTED_PARAMETERS)}"
                
        return True, ""
