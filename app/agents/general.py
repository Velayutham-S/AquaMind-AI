from app.agents.state import AgentState
from app.agents.llm import LLMService
from app.logging_config import logger

class GeneralAgent:
    @staticmethod
    def process(state: AgentState) -> dict:
        """Handles non-groundwater queries directly using the General LLM."""
        query = state["query"]
        logger.info(f"GeneralAgent handling non-groundwater query: '{query}'")
        
        system_prompt = (
            "You are AquaMind AI, an intelligent assistant. The user's query is not related "
            "to groundwater or hydrogeology in Tamil Nadu. Answer their query normally, accurately, "
            "and helper-fully as an intelligent general assistant. Do not reject the question, "
            "and do not say 'I don't have context.' Answer in the user's input language if detected."
        )
        
        response = LLMService.call(query, system_prompt=system_prompt)
        
        history = list(state.get("routing_history", []))
        history.append("general")
        
        return {
            "response": response,
            "routing_history": history,
            "current_node": "synthesize",
            "confidence_score": 1.0,
            "confidence_reason": "General LLM knowledge query handled directly."
        }
