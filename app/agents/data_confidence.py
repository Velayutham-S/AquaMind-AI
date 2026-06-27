from typing import Dict, Any, List

class DataConfidence:
    """Calculates weighted confidence scores based on query execution attributes."""

    @classmethod
    def calculate(
        cls,
        resolved_location_type: str,
        is_exact_location: bool,
        sql_built_successfully: bool,
        records: List[Dict[str, Any]],
        year: str = None
    ) -> Dict[str, Any]:
        """Calculates compound confidence score using weights.
        
        Weights:
            Location resolution: 30%
            SQL completeness: 30%
            Missing values: 20%
            Dataset freshness: 20%
        """
        # 1. Location Resolution Score (30%)
        if not resolved_location_type:
            loc_score = 0.0
        elif is_exact_location:
            loc_score = 1.0
        else:
            loc_score = 0.8  # Fuzzy matched location
            
        # 2. SQL Completeness Score (30%)
        sql_score = 1.0 if sql_built_successfully else 0.5
        
        # 3. Missing Values Score (20%)
        missing_score = 1.0
        if records:
            total_elements = 0
            null_elements = 0
            for r in records:
                for k, v in r.items():
                    total_elements += 1
                    if v is None or v == "" or v == "-":
                        null_elements += 1
            if total_elements > 0:
                missing_score = 1.0 - (null_elements / total_elements)
                
        # 4. Dataset Freshness Score (20%)
        freshness_score = 1.0
        target_year = year
        if not target_year and records:
            years = [r.get("year") for r in records if r.get("year")]
            if years:
                target_year = max(years)
                
        if target_year:
            # Scale down for older years
            # e.g., '2024-2025' or '2025' -> 1.0, '2023-2024' -> 0.95, '2022' -> 0.85
            year_str = str(target_year)
            if "2025" in year_str or "2024" in year_str:
                freshness_score = 1.0
            elif "2023" in year_str:
                freshness_score = 0.95
            elif "2022" in year_str:
                freshness_score = 0.90
            elif "2020" in year_str:
                freshness_score = 0.80
            else:
                freshness_score = 0.70
                
        # Compute weighted sum
        overall = (0.30 * loc_score) + (0.30 * sql_score) + (0.20 * missing_score) + (0.20 * freshness_score)
        
        # Clamp value
        overall = min(max(overall, 0.0), 1.0)
        
        return {
            "confidence_score": float(overall),
            "location_resolution": float(loc_score),
            "sql_completeness": float(sql_score),
            "missing_values": float(missing_score),
            "dataset_freshness": float(freshness_score)
        }
