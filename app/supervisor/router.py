from typing import Dict, Any, List
from app.logging_config import logger
from app.supervisor.agent_registry import AgentRegistry

class Router:
    """Decides the routing destination (next LangGraph node) and coordinates execution task routing."""

    @classmethod
    def determine_route(cls, execution_plan: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Inspects the execution plan and maps it to next LangGraph nodes and execution paths."""
        agents = execution_plan.get("agents", [])
        intent = execution_plan.get("intent", "").lower()
        
        # Compile execution routing list
        routing_history = list(state.get("routing_history", []))
        if "supervisor" not in routing_history:
            routing_history.append("supervisor")
            
        # Determine next LangGraph node target
        if not agents:
            current_node = "synthesize"
        elif "GeneralAgent" in agents:
            current_node = "general"
        else:
            # All other agents are executed by the ExecutionEngine and route to synthesize
            current_node = "synthesize"
            
        logger.info(f"Router resolved next node destination: '{current_node}' (intent: '{intent}', agents: {agents})")
        
        return {
            "current_node": current_node,
            "routing_history": routing_history
        }
