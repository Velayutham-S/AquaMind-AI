from typing import Dict, Any, List
from app.supervisor.tool_registry import ToolRegistry
from app.logging_config import logger

class ToolPlanner:
    """Matches and validates tools required for query execution using the ToolRegistry."""

    @classmethod
    def plan_tools(cls, requested_tools: List[str], intent: str) -> List[str]:
        """Validates that all requested tools are registered, and applies fallback/default tools for intents."""
        valid_tools = []
        registered_tools = {t["name"] for t in ToolRegistry.list_tools()}
        
        # Validate requested tools
        for tool in requested_tools:
            if tool in registered_tools:
                valid_tools.append(tool)
            else:
                logger.warning(f"Requested tool '{tool}' is not registered. Skipping.")
                
        # Automatically inject default tools based on intent/response type if none planned
        if not valid_tools:
            if intent in ["prediction", "comparison", "Groundwater Status"]:
                if "ChartGenerator" in registered_tools:
                    valid_tools.append("ChartGenerator")
            elif intent == "gis":
                if "MapGenerator" in registered_tools:
                    valid_tools.append("MapGenerator")
            elif intent == "report":
                if "PDFExporter" in registered_tools:
                    valid_tools.append("PDFExporter")
                    
        return list(set(valid_tools))
