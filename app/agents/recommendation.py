from app.agents.state import AgentState
from app.agents.llm import LLMService
from app.logging_config import logger

class RecommendationAgent:
    @staticmethod
    def process(state: AgentState) -> dict:
        """Recommendation node compiling tailored water conservation, recharge, and policy actions."""
        loc = state.get("resolved_location")
        loc_type = state.get("resolved_location_type")
        data = state.get("context_data") or []
        prediction = state.get("context_prediction")
        simulation = state.get("context_simulation")
        
        logger.info(f"RecommendationAgent running for location: {loc}")
        
        # Determine groundwater stress level
        category = "Safe"
        stage = 50.0
        
        if simulation and simulation.get("status") == "success":
            category = simulation["simulated_category"]
            stage = simulation["simulated_stage"]
        elif prediction and prediction.get("status") == "success":
            category = prediction["forecast_categories"][0]
            stage = prediction["forecast_stages"][0]
        elif data:
            category = data[-1]["category"]
            stage = data[-1]["stage_of_extraction"]

        # 1. Select conservation template recommendations based on category
        recommendations = []
        
        if category in ["Critical", "Over-Exploited"]:
            recommendations.append({
                "title": "Mandatory Rainwater Harvesting (RWH)",
                "category": "Recharge",
                "why": "High extraction demands require active aquifer replenishment to stabilize falling water levels.",
                "evidence": f"Stage of extraction is currently {stage:.2f}%, indicating demand exceeds safe replenishment limits.",
                "impact": "Can increase localized recharge by 15-20% and reduce reliance on municipal water networks."
            })
            recommendations.append({
                "title": "Crop Diversification Plan",
                "category": "Agriculture",
                "why": "Paddy and sugarcane cultivation consumes over 80% of irrigation groundwater.",
                "evidence": f"Agricultural extraction is the primary draft component in the region (stage: {stage:.2f}%).",
                "impact": "Shifting to micro-irrigation and millets/pulses reduces irrigation draft by 30-40%."
            })
            recommendations.append({
                "title": "Tamil Nadu Groundwater Act Regulatory Restrictions",
                "category": "Policy",
                "why": "Stricter legal permits prevent illegal deep borewell drilling in stressed blocks.",
                "evidence": f"Category is classified as '{category.upper()}', declaring it a critical zone under CGWA guidelines.",
                "impact": "Limits new commercial groundwater extraction licenses to zero, capping total withdrawal."
            })
        elif category == "Semi-Critical":
            recommendations.append({
                "title": "Check Dam Construction & Desiltation",
                "category": "Recharge",
                "why": "Capturing surface runoff during monsoon is highly effective in increasing unconfined aquifer pressure.",
                "evidence": f"Recharge-to-extraction balance is near critical threshold ({stage:.2f}%).",
                "impact": "Constructing 5 check dams can recharge an estimated 150-250 ham annually."
            })
            recommendations.append({
                "title": "Drip and Sprinkler Irrigation Subsidies",
                "category": "Agriculture",
                "why": "Micro-irrigation increases water use efficiency compared to flood irrigation.",
                "evidence": "Irrigation efficiency in Tamil Nadu is currently averaging 60%.",
                "impact": "Saves up to 1,000 liters of water per hectare, postponing stress levels."
            })
        else: # Safe
            recommendations.append({
                "title": "Community-led Water Budgeting",
                "category": "Management",
                "why": "Maintains the 'Safe' status through voluntary crop and domestic consumption planning.",
                "evidence": f"Groundwater draft stage is currently at a healthy {stage:.2f}%.",
                "impact": "Prevents the region from slipping into Semi-Critical category over the next decade."
            })
            recommendations.append({
                "title": "Percolation Pond Upgrades",
                "category": "Recharge",
                "why": "Increases natural infiltration rates into local shallow aquifers.",
                "evidence": "Adequate seasonal monsoon rainfall is available for catchment.",
                "impact": "Boosts baseline water levels by 0.5 to 1.5 meters post-monsoon."
            })

        # 2. Enrich recommendations with LLM explanation
        prompt = (
            f"Groundwater Status: Location: {loc.title() if loc else 'Tamil Nadu'}, Stage of Extraction: {stage:.2f}%, Category: {category}.\n"
            f"Here are the draft recommendations:\n"
            f"{recommendations}\n\n"
            "Elaborate on these recommendations in a professional paragraph explaining why they are critical for Tamil Nadu, "
            "connecting them directly to GEC 2015 Guidelines and local farming realities. Keep it concise."
        )
        
        narrative = LLMService.call(prompt, system_prompt="You are the Recommendation Synthesis Agent of AquaMind AI.")
        
        logger.info(f"Generated recommendations summary narrative for {loc}.")

        history = list(state.get("routing_history", []))
        history.append("recommendation")

        # Determine next node in routing list
        routing_plan = ["gis", "synthesize"]
        next_node = "synthesize"
        for step in routing_plan:
            if step not in history:
                next_node = step
                break

        return {
            "context_recommendations": recommendations,
            "response": narrative, # Save intermediate narrative to state
            "routing_history": history,
            "current_node": next_node
        }
