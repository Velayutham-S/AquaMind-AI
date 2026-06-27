from typing import Dict, Any, List
from app.logging_config import logger

class EvidenceAggregator:
    """Collates and structures multi-agent contexts, citations, and outputs into a single consolidated payload."""

    @classmethod
    def aggregate(cls, agent_results: Dict[str, Any]) -> Dict[str, Any]:
        """Merges results from executed agents into standardized context state fields."""
        logger.info(f"EvidenceAggregator collating results from {len(agent_results)} agents...")
        
        aggregated = {
            "context_data": [],
            "context_knowledge": [],
            "context_prediction": None,
            "context_simulation": None,
            "context_recommendations": [],
            "context_analytics": None,
            "chart_paths": [],
            "map_html": None,
            "pdf_report_path": None,
            "citations": [],
            "errors": []
        }

        for agent_name, result in agent_results.items():
            if not result:
                continue
                
            if isinstance(result, dict) and "error" in result:
                aggregated["errors"].append(f"{agent_name}: {result['error']}")
                
            # Merge list context fields
            for key in ["context_data", "context_knowledge", "context_recommendations", "chart_paths"]:
                if key in result and isinstance(result[key], list):
                    # Filter out duplicate list elements if needed
                    aggregated[key].extend(result[key])
                    
            # Merge scalar context fields
            for key in ["context_prediction", "context_simulation", "context_analytics", "map_html", "pdf_report_path"]:
                if key in result and result[key] is not None:
                    aggregated[key] = result[key]
                    
            # Gather citations
            if "citations" in result and isinstance(result["citations"], list):
                aggregated["citations"].extend(result["citations"])
                
        # Remove duplicate citations if any
        seen_citations = set()
        unique_citations = []
        for cit in aggregated["citations"]:
            if isinstance(cit, dict):
                # Unique key: doc name + page
                cit_key = (cit.get("source", ""), cit.get("page", ""))
                if cit_key not in seen_citations:
                    seen_citations.add(cit_key)
                    unique_citations.append(cit)
        aggregated["citations"] = unique_citations
        
        logger.info("Evidence collation complete. "
                    f"Data records: {len(aggregated['context_data'])}, "
                    f"Knowledge chunks: {len(aggregated['context_knowledge'])}, "
                    f"Citations: {len(aggregated['citations'])}")
                    
        return aggregated
