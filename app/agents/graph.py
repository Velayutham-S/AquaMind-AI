from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.supervisor import SupervisorAgent
from app.agents.general import GeneralAgent
from app.agents.data import DataAgent
from app.agents.knowledge import KnowledgeAgent
from app.agents.analytics import AnalyticsAgent
from app.agents.prediction import PredictionAgent
from app.agents.simulation import SimulationAgent
from app.agents.recommendation import RecommendationAgent
from app.agents.gis import GISAgent
from app.agents.report import ReportAgent
from app.agents.synthesize import ResponseSynthesizer
from app.agents.evaluation import EvaluationAgent

def build_workflow():
    workflow = StateGraph(AgentState)
    
    # 1. Add all Agent Nodes
    workflow.add_node("supervisor", SupervisorAgent.process)
    workflow.add_node("general", GeneralAgent.process)
    workflow.add_node("data", DataAgent.process)
    workflow.add_node("knowledge", KnowledgeAgent.process)
    workflow.add_node("analytics", AnalyticsAgent.process)
    workflow.add_node("prediction", PredictionAgent.process)
    workflow.add_node("simulation", SimulationAgent.process)
    workflow.add_node("recommendation", RecommendationAgent.process)
    workflow.add_node("gis", GISAgent.process)
    workflow.add_node("report", ReportAgent.process)
    workflow.add_node("synthesize", ResponseSynthesizer.process)
    workflow.add_node("evaluate", EvaluationAgent.process)
    
    # 2. Define Entry Point
    workflow.set_entry_point("supervisor")
    
    # Router helper to map state dynamic destination
    def route_by_state(state):
        return state["current_node"]
        
    # 3. Add Conditional Edges
    workflow.add_conditional_edges(
        "supervisor",
        route_by_state,
        {
            "general": "general",
            "data": "data",
            "knowledge": "knowledge",
            "analytics": "analytics",
            "synthesize": "synthesize"
        }
    )
    
    # general node goes straight to synthesize
    workflow.add_edge("general", "synthesize")
    
    # data agent routes dynamically (analytics, prediction, simulation, or recommendation)
    workflow.add_conditional_edges(
        "data",
        route_by_state,
        {
            "analytics": "analytics",
            "prediction": "prediction",
            "simulation": "simulation",
            "recommendation": "recommendation",
            "synthesize": "synthesize"
        }
    )
    
    workflow.add_conditional_edges(
        "knowledge",
        route_by_state,
        {
            "recommendation": "recommendation",
            "synthesize": "synthesize"
        }
    )
    
    workflow.add_conditional_edges(
        "analytics",
        route_by_state,
        {
            "data": "data",
            "recommendation": "recommendation",
            "synthesize": "synthesize"
        }
    )
    
    workflow.add_conditional_edges(
        "prediction",
        route_by_state,
        {
            "recommendation": "recommendation",
            "synthesize": "synthesize"
        }
    )
    
    workflow.add_conditional_edges(
        "simulation",
        route_by_state,
        {
            "recommendation": "recommendation",
            "synthesize": "synthesize"
        }
    )
    
    workflow.add_conditional_edges(
        "recommendation",
        route_by_state,
        {
            "gis": "gis",
            "synthesize": "synthesize"
        }
    )
    
    workflow.add_conditional_edges(
        "gis",
        route_by_state,
        {
            "report": "report",
            "synthesize": "synthesize"
        }
    )
    
    # report always routes to synthesize
    workflow.add_edge("report", "synthesize")
    
    # synthesizer routes to evaluator
    workflow.add_edge("synthesize", "evaluate")
    
    # evaluator ends the graph
    workflow.add_edge("evaluate", END)
    
    # Compile
    return workflow.compile()

# Master compiled graph instance
agent_graph = build_workflow()
