from app.agents.state import AgentState
from app.logging_config import logger

class ConfidenceEngine:
    @staticmethod
    def calculate(state: AgentState) -> dict:
        """Computes response confidence score and supporting reasons."""
        score = 0.50 # Base confidence
        reasons = []
        
        loc = state.get("resolved_location")
        loc_type = state.get("resolved_location_type")
        data = state.get("context_data", [])
        knowledge = state.get("context_knowledge", [])
        
        # 1. Location match precision
        if loc:
            score += 0.15
            reasons.append(f"Entity Location resolved: {loc.title()} (Type: {loc_type})")
        else:
            score -= 0.15
            reasons.append("No specific geographical location could be resolved from query.")
            
        # 2. SQL Data matching
        if data:
            score += 0.20
            years_found = [d.get("year") for d in data if d.get("year")]
            reasons.append(f"GEC Database Records matched: Found {len(data)} assessments across years: {', '.join(years_found)}")
            
            # Check for latest 2024-2025 data
            if any("2024-2025" in str(y) for y in years_found):
                score += 0.05
                reasons.append("Latest GEC 2024-2025 resource assessment is active.")
        else:
            reasons.append("No database statistical records matched.")
            
        # 3. RAG Knowledge documents
        if knowledge:
            score += min(0.15, len(knowledge) * 0.04)
            reasons.append(f"Vector Store: Retrieved {len(knowledge)} context chunks from official publications.")
            
            # Check categories
            cats = {k.get("category") for k in knowledge if k.get("category")}
            if cats:
                reasons.append(f"Document categories verified: {', '.join(cats)}")
        else:
            score -= 0.15
            reasons.append("No relevant scientific or regulatory document chunks found in vector index.")

        # Cap score
        final_score = max(0.0, min(1.0, score))
        
        logger.info(f"Confidence score computed: {final_score:.2f}. Reasons: {reasons}")
        
        return {
            "confidence_score": final_score,
            "confidence_reason": "\n".join([f"- {r}" for r in reasons])
        }
