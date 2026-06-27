from typing import TypedDict, List, Dict, Any, Optional

class SupervisorState(TypedDict):
    """Execution state representing the context passed across Supervisor Agent modules."""
    
    # Core inputs & sessions
    session_id: str
    query: str
    original_query: Optional[str]
    normalized_query: Optional[str]
    language: Optional[str]              # en, ta, mixed
    intent: Optional[str]                # data, knowledge, prediction, etc.
    
    # Resolved entities
    entities: Optional[Dict[str, Any]]   # {"location": ..., "year": ...}
    
    # Planning & routing details
    execution_plan: Optional[Dict[str, Any]]
    agent_results: Optional[Dict[str, Any]]
    
    # Accumulating multi-agent contexts
    context_data: Optional[List[Dict[str, Any]]]
    context_knowledge: Optional[List[Dict[str, Any]]]
    context_prediction: Optional[Dict[str, Any]]
    context_simulation: Optional[Dict[str, Any]]
    context_recommendations: Optional[List[Dict[str, Any]]]
    context_analytics: Optional[Dict[str, Any]]
    
    # Visual rendering outputs
    chart_paths: Optional[List[str]]
    map_html: Optional[str]
    pdf_report_path: Optional[str]
    
    # Telemetry, feedback and final outputs
    routing_history: List[str]
    current_node: str
    confidence: Optional[Dict[str, Any]]  # overall confidence score + status
    citations: Optional[List[Dict[str, Any]]]
    final_answer: Optional[str]
    metrics: Optional[Dict[str, Any]]
    errors: Optional[List[str]]
    session: Optional[Dict[str, Any]]    # Cached session data
    
    # Phase 2.1 Enhancements
    reasoning: Optional[List[str]]
    progress_events: Optional[List[Dict[str, Any]]]
    execution_status: Optional[str]
    overall_confidence: Optional[float]
    confidence_level: Optional[str]
    confidence_breakdown: Optional[Dict[str, float]]
    execution_timeline: Optional[List[Dict[str, Any]]]
