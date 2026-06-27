from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    # Core flow parameters
    session_id: str
    query: str
    original_query: str
    language: str              # en, ta, mixed
    intent: str                # general, data, knowledge, prediction, simulation, comparison
    
    # Resolved entities
    resolved_location: Optional[str]
    resolved_location_type: Optional[str] # district, firka, village
    resolved_year: Optional[str]          # e.g., "2024-2025"
    
    # Multi-agent accumulated contexts
    context_data: Optional[List[Dict[str, Any]]]         # numeric district/firka GEC data
    context_knowledge: Optional[List[Dict[str, Any]]]    # semantic RAG PDF text passages
    context_prediction: Optional[Dict[str, Any]]         # output of prediction model
    context_simulation: Optional[Dict[str, Any]]         # output of simulator
    context_recommendations: Optional[List[Dict[str, Any]]]# output of recommendation generator
    context_analytics: Optional[Dict[str, Any]]          # comparison or stats reports
    
    # Visual links & paths
    chart_paths: Optional[List[str]]
    map_html: Optional[str]
    pdf_report_path: Optional[str]
    
    # Coordinator state
    routing_history: List[str] # List of agents visited
    current_node: str
    
    # Output response variables
    response: str
    confidence_score: float
    confidence_reason: str
    citations: List[Dict[str, Any]]
    
    # Post-execution evaluation
    evaluation: Optional[Dict[str, Any]]
