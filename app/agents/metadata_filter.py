import json
from typing import List, Dict, Any, Optional
from app.agents.llm import LLMService
from app.logging_config import logger

class MetadataFilter:
    @staticmethod
    def infer_filters(query: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Infers metadata filters from user query using LLM and combines with state resolved entities."""
        system_prompt = (
            "You are a Metadata Filter Inferrer for AquaMind AI.\n"
            "Identify geographic or document metadata parameters from the query.\n"
            "Output a JSON object with these exact keys (or null if not mentioned):\n"
            "- document_title: title of document if mentioned\n"
            "- collection: e.g. CGWB, GEC, CGWA, State if mentioned\n"
            "- assessment_year: assessment year range (e.g. 2023-2024)\n"
            "- district: e.g. SALEM, COIMBATORE, etc. in uppercase\n"
            "- taluk: taluk name in uppercase\n"
            "- firka: firka name in uppercase\n"
            "- village: village name in uppercase\n"
            "- aquifer: aquifer name in uppercase\n"
            "- river_basin: river basin name in uppercase\n"
            "- watershed: watershed name in uppercase\n"
            "- report_type: e.g. 'Policy', 'Guideline', 'Year Book', 'Assessment Report'\n"
            "- policy: policy name if mentioned\n"
            "- guideline: guideline name if mentioned\n"
            "- publication_year: 4-digit publication year\n"
            "- source_category: category name if mentioned\n"
            "Output ONLY valid JSON."
        )
        
        inferred = {}
        try:
            res = LLMService.call_json(prompt=query, system_prompt=system_prompt)
            if res and isinstance(res, dict):
                inferred = {k: v for k, v in res.items() if v is not None}
        except Exception as e:
            logger.error(f"MetadataFilter inference error: {e}")

        # Combine with state entities for authority
        loc = state.get("resolved_location")
        loc_type = state.get("resolved_location_type")
        year = state.get("resolved_year")
        
        if loc:
            loc_upper = loc.upper()
            if loc_type == "district":
                inferred["district"] = loc_upper
            elif loc_type == "taluk":
                inferred["taluk"] = loc_upper
            elif loc_type == "firka":
                inferred["firka"] = loc_upper
            elif loc_type == "village":
                inferred["village"] = loc_upper
                
        if year:
            inferred["assessment_year"] = year

        # Post-process cleanup of common query keywords
        logger.info(f"MetadataFilter Inferred Filters: {inferred}")
        return inferred

    @staticmethod
    def filter_chunks(chunks: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Filters retrieved candidate chunks based on inferred filters before Cross-Encoder reranking."""
        if not filters:
            return chunks
            
        filtered = []
        for c in chunks:
            meta = c.get("metadata", {})
            match = True
            
            # Map filters to meta attributes
            for fk, fv in filters.items():
                if fv is None:
                    continue
                
                fv_str = str(fv).strip().upper()
                
                # Retrieve field value from chunk metadata
                chunk_vals = []
                
                if fk == "district":
                    chunk_vals = [meta.get("district")]
                elif fk == "assessment_year":
                    chunk_vals = [meta.get("year"), meta.get("assessment_year")]
                elif fk == "publication_year":
                    chunk_vals = [meta.get("publication_year"), meta.get("year")]
                elif fk == "collection":
                    chunk_vals = [meta.get("source"), meta.get("collection"), meta.get("doc_collection")]
                elif fk == "report_type":
                    chunk_vals = [meta.get("category"), meta.get("section_title"), meta.get("report_type")]
                elif fk == "policy":
                    chunk_vals = [meta.get("title"), meta.get("policy")]
                elif fk == "guideline":
                    chunk_vals = [meta.get("title"), meta.get("guideline")]
                else:
                    # Direct check in metadata
                    chunk_vals = [meta.get(fk)]
                
                # Check match
                field_matched = False
                for val in chunk_vals:
                    if val and fv_str in str(val).strip().upper():
                        field_matched = True
                        break
                        
                # Special cases for graph nodes
                if not field_matched and fk in ["taluk", "firka", "village", "aquifer", "river_basin", "watershed"]:
                    # check node_name in metadata (graph links might store related node details)
                    node_name = meta.get("node_name")
                    node_type = meta.get("node_type")
                    if node_name and fv_str in str(node_name).strip().upper():
                        field_matched = True
                
                if not field_matched:
                    match = False
                    break
            
            if match:
                filtered.append(c)
                
        logger.info(f"MetadataFilter: filtered {len(chunks)} chunks down to {len(filtered)} chunks.")
        return filtered
