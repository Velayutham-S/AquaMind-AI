from typing import List

class QueryClassifier:
    """Pre-evaluates and classifies user queries into primary categories using lightweight heuristics."""

    @classmethod
    def classify(cls, query: str) -> str:
        """Determines the primary classification category of the query."""
        if not query:
            return "Unknown"

        q_lower = query.lower()

        # Check for greeting or non-groundwater generic queries
        greetings = {"hello", "hi", "hey", "who are you", "what is your name", "capabilities", "what can you do", "help"}
        words = set(q_lower.split())
        if greetings.intersection(words) or "developed" in q_lower or "creator" in q_lower or "created" in q_lower:
            return "General AI"

        # Check for Simulation keywords (what-if scenarios, percentage shifts, stress tests)
        simulation_keywords = {"what-if", "what if", "scenario", "simulate", "decrease by", "increase by", "change by", "shift by"}
        if any(kw in q_lower for kw in simulation_keywords) or "%" in q_lower:
            return "Simulation"

        # Check for Prediction/Forecast keywords
        prediction_keywords = {"predict", "forecast", "projection", "project", "future", "2030", "trend", "regress"}
        if any(kw in q_lower for kw in prediction_keywords):
            return "Prediction"

        # Check for GIS/Map keywords
        gis_keywords = {"map", "gis", "visualize", "coordinates", "render", "plot on map", "stressed blocks"}
        if any(kw in q_lower for kw in gis_keywords):
            return "GIS"

        # Check for comparative/analytics keywords
        comparison_keywords = {"compare", "versus", "vs", "difference", "trend", "analytics", "ranking", "rank"}
        if any(kw in q_lower for kw in comparison_keywords):
            return "Mixed"

        # Check for scientific / policy / RAG document search keywords
        knowledge_keywords = {
            "why", "how", "guideline", "policy", "regulation", "scientific", "aquifer plan", "act",
            "recharge method", "artificial recharge", "water quality", "tds", "fluoride", "contamination"
        }
        if any(kw in q_lower for kw in knowledge_keywords):
            return "Knowledge"

        # Check for specific numbers or database GEC statistics keywords
        data_keywords = {"statistics", "numbers", "stage of extraction", "annual recharge", "total recharge", "ham", "extraction"}
        if any(kw in q_lower for kw in data_keywords):
            return "Structured Data"

        # Default fallback: check if location is mentioned to route to data/knowledge
        return "Structured Data"
