import os
import matplotlib
matplotlib.use('Agg') # Thread-safe non-GUI backend
import matplotlib.pyplot as plt
from datetime import datetime
from sqlalchemy.orm import Session
from app.config import Config
from app.database import SessionLocal
from app.agents.state import AgentState
from app.models import DistrictAssessment, FirkaAssessment
from app.logging_config import logger

class DataAgent:
    @staticmethod
    def process(state: AgentState) -> dict:
        """Data node that queries assessment tables from SQL database and generates trend charts."""
        loc = state.get("resolved_location")
        loc_type = state.get("resolved_location_type")
        year = state.get("resolved_year")
        session_id = state.get("session_id", "default")
        
        logger.info(f"DataAgent executing. Location: {loc} ({loc_type}), Year: {year}")
        
        db = SessionLocal()
        records = []
        chart_paths = []
        
        try:
            if loc_type == "district":
                query = db.query(DistrictAssessment).filter(DistrictAssessment.district == loc.upper())
                if year:
                    query = query.filter(DistrictAssessment.year == year)
                db_recs = query.order_by(DistrictAssessment.year.asc()).all()
                
                for r in db_recs:
                    records.append({
                        "level": "district",
                        "name": r.district,
                        "year": r.year,
                        "total_recharge": r.total_recharge,
                        "annual_extractable": r.annual_extractable,
                        "total_extraction": r.total_extraction,
                        "stage_of_extraction": r.stage_of_extraction,
                        "category": r.category,
                        "extraction_irrigation": r.extraction_irrigation,
                        "extraction_domestic": r.extraction_domestic,
                        "extraction_industrial": r.extraction_industrial,
                        "quality_tag": r.quality_tag
                    })
                    
            elif loc_type == "firka":
                query = db.query(FirkaAssessment).filter(FirkaAssessment.firka == loc.upper())
                if year:
                    query = query.filter(FirkaAssessment.year == year)
                db_recs = query.order_by(FirkaAssessment.year.asc()).all()
                
                for r in db_recs:
                    records.append({
                        "level": "firka",
                        "name": r.firka,
                        "district": r.district,
                        "year": r.year,
                        "total_recharge": r.total_recharge,
                        "annual_extractable": r.annual_extractable,
                        "total_extraction": r.total_extraction,
                        "stage_of_extraction": r.stage_of_extraction,
                        "category": r.category,
                        "quality_tag": r.quality_tag
                    })
            else:
                # State-level or fallback: get overall averages grouped by year
                # Query all districts to get state averages
                query = db.query(DistrictAssessment)
                if year:
                    query = query.filter(DistrictAssessment.year == year)
                db_recs = query.order_by(DistrictAssessment.year.asc()).all()
                
                # Group by year
                by_year = {}
                for r in db_recs:
                    y = r.year
                    if y not in by_year:
                        by_year[y] = {"recharge": 0, "extractable": 0, "extraction": 0, "count": 0}
                    by_year[y]["recharge"] += r.total_recharge or 0
                    by_year[y]["extractable"] += r.annual_extractable or 0
                    by_year[y]["extraction"] += r.total_extraction or 0
                    by_year[y]["count"] += 1
                    
                for y, val in sorted(by_year.items()):
                    avg_stage = (val["extraction"] / val["extractable"] * 100) if val["extractable"] > 0 else 0
                    records.append({
                        "level": "state",
                        "name": "TAMIL NADU",
                        "year": y,
                        "total_recharge": val["recharge"],
                        "annual_extractable": val["extractable"],
                        "total_extraction": val["extraction"],
                        "stage_of_extraction": avg_stage,
                        "category": "State Average"
                    })
                    
            # Chart Generation: Generate line chart if we have history (length > 1)
            if len(records) > 1 and loc:
                years = [r["year"] for r in records]
                recharges = [r["total_recharge"] for r in records]
                extractions = [r["total_extraction"] for r in records]
                stages = [r["stage_of_extraction"] for r in records]
                
                plt.figure(figsize=(8, 4))
                
                # Plot recharge vs extraction
                plt.subplot(1, 2, 1)
                plt.plot(years, recharges, marker='o', color='blue', label='Recharge')
                plt.plot(years, extractions, marker='s', color='orange', label='Extraction')
                plt.title(f"{loc.title()} Recharge vs Extraction (ham)")
                plt.xlabel("Year")
                plt.ylabel("ham")
                plt.legend()
                plt.grid(True, linestyle='--', alpha=0.5)
                
                # Plot stage of extraction
                plt.subplot(1, 2, 2)
                plt.plot(years, stages, marker='^', color='red', label='Stage of Ext (%)')
                plt.axhline(y=70, color='green', linestyle=':', label='Safe (70%)')
                plt.axhline(y=90, color='yellow', linestyle=':', label='Semi-Critical (90%)')
                plt.axhline(y=100, color='orange', linestyle=':', label='Critical (100%)')
                plt.title("Stage of Extraction (%)")
                plt.xlabel("Year")
                plt.ylabel("%")
                plt.legend()
                plt.grid(True, linestyle='--', alpha=0.5)
                
                plt.tight_layout()
                
                chart_dir = Config.BASE_DIR / "reports" / "charts"
                chart_dir.mkdir(parents=True, exist_ok=True)
                
                filename = f"chart_{session_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                filepath = chart_dir / filename
                plt.savefig(filepath, dpi=100)
                plt.close()
                chart_paths.append(str(filepath))
                logger.info(f"Generated trend chart at {filepath}")
                
        except Exception as e:
            logger.error(f"DataAgent DB query/chart error: {e}", exc_info=True)
        finally:
            db.close()
            
        history = list(state.get("routing_history", []))
        history.append("data")
        
        # Determine next node in routing list
        current_idx = state.get("routing_history", []).count("supervisor") # standard sequence offset
        routing_plan = []
        intent = state.get("intent")
        if intent == "comparison":
            routing_plan = ["analytics", "recommendation", "gis", "synthesize"]
        elif intent == "prediction":
            routing_plan = ["prediction", "recommendation", "synthesize"]
        elif intent == "simulation":
            routing_plan = ["simulation", "recommendation", "synthesize"]
        else:
            routing_plan = ["recommendation", "gis", "synthesize"]
            
        # Determine next node from remaining steps
        current_node_idx = len(history) - 2 # index in execution
        next_node = "synthesize"
        # Find next node in sequence that hasn't run yet
        for step in routing_plan:
            if step not in history:
                next_node = step
                break
                
        return {
            "context_data": records,
            "chart_paths": chart_paths,
            "routing_history": history,
            "current_node": next_node
        }
