import importlib
import inspect
from typing import Dict, Any, List, Optional
from app.logging_config import logger

class AgentRegistry:
    """Dynamic registry for discovering, registering, and checking the health of system agents."""

    _agents: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def discover_agents(cls) -> None:
        """Dynamically scans and registers agents available in the app.agents package."""
        cls._agents.clear()
        
        # Hardcoded list of agents to load dynamically
        agent_modules = {
            "KnowledgeAgent": ("app.agents.knowledge", "KnowledgeAgent"),
            "DataAgent": ("app.agents.data_agent", "DataAgent"),
            "PredictionAgent": ("app.agents.prediction", "PredictionAgent"),
            "SimulationAgent": ("app.agents.simulation", "SimulationAgent"),
            "RecommendationAgent": ("app.agents.recommendation", "RecommendationAgent"),
            "GISAgent": ("app.agents.gis", "GISAgent"),
            "AnalyticsAgent": ("app.agents.analytics", "AnalyticsAgent"),
            "GeneralAgent": ("app.agents.general", "GeneralAgent"),
            "ReportAgent": ("app.agents.report", "ReportAgent")
        }

        for name, (module_path, class_name) in agent_modules.items():
            try:
                mod = importlib.import_module(module_path)
                klass = getattr(mod, class_name)
                
                # Fetch metadata declared on the class or use standard fallbacks
                metadata = getattr(klass, "METADATA", {})
                
                cls._agents[name] = {
                    "name": name,
                    "class": klass,
                    "description": metadata.get("description", klass.__doc__ or f"{name} coordinator agent."),
                    "capabilities": metadata.get("capabilities", [name.lower().replace("agent", "")]),
                    "supported_inputs": metadata.get("supported_inputs", ["state"]),
                    "supported_outputs": metadata.get("supported_outputs", ["state_diff"]),
                    "cost": metadata.get("cost", 0.01),
                    "latency": metadata.get("latency", 1.0),
                    "priority": metadata.get("priority", 10),
                    "availability": True,
                    "health_status": "healthy"
                }
                logger.info(f"Dynamically registered Agent: {name} with capabilities {cls._agents[name]['capabilities']}")
            except Exception as e:
                logger.error(f"Failed to dynamically discover agent {name} from {module_path}: {e}")

    @classmethod
    def get_agent_metadata(cls, name: str) -> Optional[Dict[str, Any]]:
        """Returns details for a registered agent by name."""
        if not cls._agents:
            cls.discover_agents()
        return cls._agents.get(name)

    @classmethod
    def list_agents(cls) -> List[Dict[str, Any]]:
        """Lists all registered agents."""
        if not cls._agents:
            cls.discover_agents()
        return list(cls._agents.values())

    @classmethod
    def invoke_agent(cls, name: str, state: Any) -> Any:
        """Safely invokes a registered agent's process method."""
        agent_meta = cls.get_agent_metadata(name)
        if not agent_meta:
            raise ValueError(f"Agent '{name}' is not registered.")
        
        klass = agent_meta["class"]
        return klass.process(state)
