import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime
from app.config import Config
from app.database import SessionLocal
from app.agents.state import AgentState
from app.agents.llm import LLMService
from app.resolution import LocationResolver
from app.models import DistrictAssessment
from app.logging_config import logger

class AnalyticsAgent:
    @staticmethod
    def process(state: AgentState) -> dict:
        """Analytics node that compares groundwater parameters across multiple districts and years."""
        query = state["query"]
        session_id = state.get("session_id", "default")
        
        logger.info(f"AnalyticsAgent processing comparison query: '{query}'")
        
        # 1. Ask LLM to extract multiple location entities for comparative report
        system_prompt = (
            "You are the Analytics Entity Extractor. Extract all Tamil Nadu districts/locations "
            "being compared in the query. Return them as a JSON list. Example: ['Salem', 'Coimbatore'].\n"
            "Output MUST be raw JSON list format only, e.g. {\"locations\": ['Salem', 'Coimbatore']}"
        )
        extracted = LLMService.call_json(f"Extract compared locations: {query}", system_prompt=system_prompt)
        raw_locs = extracted.get("locations", [])
        
        # Fallback to resolved location if none extracted
        if not raw_locs and state.get("resolved_location"):
            raw_locs = [state["resolved_location"]]

        db = SessionLocal()
        resolved_locs = []
        try:
            for rl in raw_locs:
                res = LocationResolver.resolve_location(db, rl)
                if res["resolved"] and res["type"] == "district":
                    resolved_locs.append(res["resolved"])
        except Exception as e:
            logger.error(f"AnalyticsAgent error resolving: {e}")
            
        resolved_locs = list(set(resolved_locs)) # Deduplicate
        
        # Default comparative locations if empty
        if not resolved_locs:
            resolved_locs = ["SALEM", "COIMBATORE"] # Default fallback

        logger.info(f"Comparing districts: {resolved_locs}")

        comparison_data = {}
        chart_paths = list(state.get("chart_paths", []))
        
        try:
            plt.figure(figsize=(8, 4))
            has_data = False
            
            for dist in resolved_locs:
                recs = db.query(DistrictAssessment)\
                    .filter(DistrictAssessment.district == dist.upper())\
                    .order_by(DistrictAssessment.year.asc())\
                    .all()
                    
                if recs:
                    has_data = True
                    years = [r.year for r in recs]
                    stages = [r.stage_of_extraction for r in recs]
                    extractions = [r.total_extraction for r in recs]
                    
                    comparison_data[dist] = {
                        "years": years,
                        "stages": stages,
                        "extractions": extractions,
                        "avg_stage": sum(stages) / len(stages) if stages else 0.0,
                        "avg_extraction": sum(extractions) / len(extractions) if extractions else 0.0,
                        "current_category": recs[-1].category if recs else "Unknown"
                    }
                    
                    # Plot comparison line
                    plt.plot(years, stages, marker='o', label=f"{dist.title()} Stage (%)")
            
            if has_data:
                plt.title("Groundwater Extraction Stage Comparison (%)")
                plt.xlabel("Year")
                plt.ylabel("Stage of Extraction (%)")
                plt.axhline(y=70, color='green', linestyle=':', label='Safe (70%)')
                plt.axhline(y=90, color='yellow', linestyle=':', label='Semi-Critical (90%)')
                plt.axhline(y=100, color='red', linestyle=':', label='Critical (100%)')
                plt.legend()
                plt.grid(True, linestyle='--', alpha=0.5)
                
                chart_dir = Config.BASE_DIR / "reports" / "charts"
                chart_dir.mkdir(parents=True, exist_ok=True)
                
                filename = f"compare_{session_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                filepath = chart_dir / filename
                plt.savefig(filepath, dpi=100)
                plt.close()
                chart_paths.append(str(filepath))
                logger.info(f"Generated comparison chart at {filepath}")
                
        except Exception as e:
            logger.error(f"AnalyticsAgent chart rendering failure: {e}", exc_info=True)
        finally:
            db.close()

        history = list(state.get("routing_history", []))
        history.append("analytics")

        # Determine next node in routing list
        routing_plan = ["data", "recommendation", "gis", "synthesize"]
        next_node = "synthesize"
        for step in routing_plan:
            if step not in history:
                next_node = step
                break

        return {
            "context_analytics": {
                "compared_districts": resolved_locs,
                "comparison": comparison_data
            },
            "chart_paths": chart_paths,
            "routing_history": history,
            "current_node": next_node
        }
