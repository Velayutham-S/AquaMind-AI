from app.agents.state import AgentState
from app.agents.llm import LLMService
from app.logging_config import logger

class SimulationAgent:
    @staticmethod
    def process(state: AgentState) -> dict:
        """Simulation node that calculates what-if GEC balance scenarios (rainfall drop, extraction hike)."""
        data = state.get("context_data") or []
        loc = state.get("resolved_location")
        query = state["query"]
        
        logger.info(f"SimulationAgent running what-if scenario for: {loc}")
        
        if not data:
            logger.warning("No assessment data available to perform GEC simulation.")
            return {
                "context_simulation": {
                    "status": "no_data",
                    "explanation": "No baseline assessment data available to run simulation model."
                },
                "current_node": "recommendation"
            }

        # Get latest baseline data point
        baseline = data[-1]
        
        # 1. Extract simulation factors from query using LLM
        system_prompt = (
            "You are the Simulation Parameter Extractor. Analyze the query and extract what-if variables.\n"
            "Provide these fields as a JSON dictionary:\n"
            "- extraction_pct_change: percentage change in extraction (e.g. +20, -10), defaults to 0 if not mentioned.\n"
            "- rainfall_pct_change: percentage change in rainfall (e.g. -15, +5), defaults to 0 if not mentioned.\n"
            "- recharge_structures_bonus: added recharge in ham (e.g. 500) if check dams/structures are added, defaults to 0.\n\n"
            "Output MUST be raw JSON format only."
        )
        
        extracted = LLMService.call_json(f"Extract parameters: {query}", system_prompt=system_prompt)
        ext_change = float(extracted.get("extraction_pct_change", 0.0))
        rain_change = float(extracted.get("rainfall_pct_change", 0.0))
        bonus_recharge = float(extracted.get("recharge_structures_bonus", 0.0))

        # Default values if user runs generic simulation query
        if ext_change == 0.0 and rain_change == 0.0 and bonus_recharge == 0.0:
            logger.info("No parameters in query. Defaulting to standard stress test (Extraction +20%, Rainfall -15%).")
            ext_change = 20.0
            rain_change = -15.0

        # Baseline parameters
        base_recharge = baseline["total_recharge"] or 1.0
        base_extractable = baseline["annual_extractable"] or 1.0
        base_extraction = baseline["total_extraction"] or 0.0
        base_stage = baseline["stage_of_extraction"] or 0.0
        base_cat = baseline["category"] or "Safe"
        
        # We assume rainfall recharge is 65% of total recharge as standard approximation in GEC
        base_rain_recharge = baseline.get("rainfall_recharge", base_recharge * 0.65)
        base_other_recharge = base_recharge - base_rain_recharge

        # Apply rainfall change
        sim_rain_recharge = base_rain_recharge * (1.0 + (rain_change / 100.0))
        sim_recharge = sim_rain_recharge + base_other_recharge + bonus_recharge
        
        # Account for environmental flows (typically 10% of total recharge is deducted to get extractable)
        sim_extractable = base_extractable * (sim_recharge / base_recharge)
        
        # Apply extraction change
        sim_extraction = base_extraction * (1.0 + (ext_change / 100.0))
        
        # Compute new stage
        sim_stage = (sim_extraction / sim_extractable * 100.0) if sim_extractable > 0 else 0.0
        
        # Map new category
        if sim_stage <= 70:
            sim_cat = "Safe"
        elif sim_stage <= 90:
            sim_cat = "Semi-Critical"
        elif sim_stage <= 100:
            sim_cat = "Critical"
        else:
            sim_cat = "Over-Exploited"

        explanation = (
            f"Simulation Results for {loc.title()}:\n"
            f"- Scenario parameters: Extraction change: {ext_change:+.1f}%, Rainfall change: {rain_change:+.1f}%, Recharge Structures Bonus: +{bonus_recharge} ham.\n"
            f"- Baseline: Stage = {base_stage:.2f}%, Category = {base_cat}\n"
            f"- Simulated State: Stage = {sim_stage:.2f}%, Category = {sim_cat}\n"
            f"- Details: Extractable resource shifted from {base_extractable:.2f} ham to {sim_extractable:.2f} ham. "
            f"Extraction demands shifted from {base_extraction:.2f} ham to {sim_extraction:.2f} ham."
        )

        simulation_result = {
            "status": "success",
            "extraction_change_pct": ext_change,
            "rainfall_change_pct": rain_change,
            "recharge_bonus_ham": bonus_recharge,
            "base_stage": base_stage,
            "base_category": base_cat,
            "simulated_stage": sim_stage,
            "simulated_category": sim_cat,
            "simulated_extractable": sim_extractable,
            "simulated_extraction": sim_extraction,
            "explanation": explanation
        }

        logger.info(f"Simulation complete. Simulated stage: {sim_stage:.2f}% (Category: {sim_cat})")

        history = list(state.get("routing_history", []))
        history.append("simulation")

        # Determine next node in routing list
        routing_plan = ["recommendation", "synthesize"]
        next_node = "synthesize"
        for step in routing_plan:
            if step not in history:
                next_node = step
                break

        return {
            "context_simulation": simulation_result,
            "routing_history": history,
            "current_node": next_node
        }
