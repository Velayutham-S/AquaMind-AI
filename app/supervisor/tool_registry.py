from typing import Dict, Any, List, Optional
from app.logging_config import logger

class ToolRegistry:
    """Registry for discovering, listing, and getting metadata of system tools."""
    
    _tools: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register_default_tools(cls) -> None:
        """Registers default tools available in the system."""
        cls._tools.clear()
        
        default_tools = {
            "MapGenerator": {
                "name": "MapGenerator",
                "description": "Renders spatial Leaflet/Folium district or firka level maps and saves map HTML files.",
                "parameters": {"location": "str", "data_layer": "str"}
            },
            "ChartGenerator": {
                "name": "ChartGenerator",
                "description": "Plots regression lines, statistical recharge vs extraction bar/line comparison charts.",
                "parameters": {"x_data": "list", "y_data": "list", "title": "str"}
            },
            "TableGenerator": {
                "name": "TableGenerator",
                "description": "Formats GEC water assessment or quality tables dynamically for reports or screen UI.",
                "parameters": {"headers": "list", "rows": "list"}
            },
            "PDFExporter": {
                "name": "PDFExporter",
                "description": "Compiles executive water resource evaluation audit summaries into letter-sized PDF documents.",
                "parameters": {"content": "str", "output_path": "str"}
            },
            "CSVExporter": {
                "name": "CSVExporter",
                "description": "Exports raw groundwater monitoring well level datasets to production CSV spreadsheets.",
                "parameters": {"records": "list", "output_path": "str"}
            },
            "GeoJSONExporter": {
                "name": "GeoJSONExporter",
                "description": "Exports structural administrative boundaries (districts, taluks, firkas) into geojson structures.",
                "parameters": {"features": "list", "output_path": "str"}
            },
            "ImageRenderer": {
                "name": "ImageRenderer",
                "description": "Renders high resolution static images for GIS mapping overlay analysis.",
                "parameters": {"map_path": "str", "output_path": "str"}
            },
            "VoiceSynthesizer": {
                "name": "VoiceSynthesizer",
                "description": "Converts final synthesized texts into clear verbal voice output for audio playback.",
                "parameters": {"text": "str", "voice_id": "str"}
            }
        }
        
        for name, info in default_tools.items():
            cls._tools[name] = {
                "name": name,
                "description": info["description"],
                "parameters": info["parameters"],
                "availability": True
            }
            logger.info(f"Registered Tool: {name} - {info['description'][:40]}...")

    @classmethod
    def get_tool_metadata(cls, name: str) -> Optional[Dict[str, Any]]:
        """Returns details for a registered tool by name."""
        if not cls._tools:
            cls.register_default_tools()
        return cls._tools.get(name)

    @classmethod
    def list_tools(cls) -> List[Dict[str, Any]]:
        """Lists all registered tools."""
        if not cls._tools:
            cls.register_default_tools()
        return list(cls._tools.values())
