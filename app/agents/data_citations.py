from typing import Dict, Any, List

class DataCitations:
    """Compiles audit citation payloads for all structured SQL data retrievals."""

    # Dataset metadata mapping tables to their static sources
    TABLE_SOURCE_METADATA = {
        "district_assessments": {
            "source_file": "Dynamic Ground Water Resources Tamil Nadu 2025.xlsx",
            "version": "GEC-2015-v1.2",
            "authority": "Central Ground Water Board (CGWB) & State Ground Water Resources"
        },
        "firka_assessments": {
            "source_file": "Firka Wise Ground Water Resource Assessment Tamil Nadu 2024.xlsx",
            "version": "GEC-2015-v1.0",
            "authority": "State Ground Water & Aquifer Management Cell"
        },
        "monitoring_data": {
            "source_file": "Groundwater Level Monitoring Stations Database.csv",
            "version": "Mon-Data-2024-v2.0",
            "authority": "State Ground Water Department"
        }
    }

    @classmethod
    def compile_citations(
        cls, 
        table_name: str, 
        records: List[Dict[str, Any]], 
        year: str = None
    ) -> List[Dict[str, Any]]:
        """Constructs list of citation dictionaries for data integrity checks."""
        if not records:
            return []
            
        meta = cls.TABLE_SOURCE_METADATA.get(table_name, {
            "source_file": "AquaMind Data Lake",
            "version": "v1.0",
            "authority": "AquaMind AI Authority"
        })
        
        # Determine unique primary keys (ids) returned
        pkeys = [r.get("id") for r in records if r.get("id") is not None]
        
        # Deduce year from records if not explicitly passed
        resolved_year = year
        if not resolved_year:
            years = {str(r.get("year")) for r in records if r.get("year") is not None}
            if years:
                resolved_year = ", ".join(sorted(list(years)))
            else:
                resolved_year = "N/A"
                
        citation = {
            "database_table": table_name,
            "assessment_year": resolved_year,
            "record_count": len(records),
            "primary_keys": pkeys[:5], # Limit keys count in metadata
            "dataset_version": meta["version"],
            "source_file": meta["source_file"],
            "authority": meta["authority"]
        }
        
        return [citation]
