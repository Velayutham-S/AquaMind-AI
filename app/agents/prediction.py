import numpy as np
from app.agents.state import AgentState
from app.logging_config import logger

class PredictionAgent:
    @staticmethod
    def process(state: AgentState) -> dict:
        """Prediction node that fits a regression trend model to forecast groundwater extraction stages."""
        data = state.get("context_data") or []
        loc = state.get("resolved_location")
        
        logger.info(f"PredictionAgent executing for location: {loc}")
        
        if not data or len(data) < 2:
            logger.warning("Insufficient historical data to make trend predictions.")
            return {
                "context_prediction": {
                    "status": "insufficient_data",
                    "explanation": "Not enough historical data points to perform linear trend regression."
                },
                "current_node": "recommendation"
            }
            
        # Extract years and numeric values
        years = []
        stages = []
        extractions = []
        recharges = []
        
        for r in data:
            # Parse start year from range (e.g. "2024-2025" -> 2024)
            y_str = str(r["year"])
            start_year = int(y_str.split("-")[0])
            years.append(start_year)
            stages.append(r["stage_of_extraction"])
            extractions.append(r["total_extraction"])
            recharges.append(r["total_recharge"])
            
        # Fit Linear regression (least squares)
        x = np.array(years)
        y_stage = np.array(stages)
        
        # Calculate slope (m) and intercept (c)
        A = np.vstack([x, np.ones(len(x))]).T
        m_stage, c_stage = np.linalg.lstsq(A, y_stage, rcond=None)[0]
        
        # Fit extraction and recharge trends
        m_ext, c_ext = np.linalg.lstsq(A, np.array(extractions), rcond=None)[0]
        m_rech, c_rech = np.linalg.lstsq(A, np.array(recharges), rcond=None)[0]
        
        # Project years: 2026, 2028, 2030
        future_years = [2026, 2028, 2030]
        forecast_stages = [float(m_stage * fy + c_stage) for fy in future_years]
        forecast_extractions = [float(m_ext * fy + c_ext) for fy in future_years]
        forecast_recharges = [float(m_rech * fy + c_rech) for fy in future_years]
        
        # Map category predictions
        forecast_categories = []
        for stage in forecast_stages:
            if stage <= 70:
                cat = "Safe"
            elif stage <= 90:
                cat = "Semi-Critical"
            elif stage <= 100:
                cat = "Critical"
            else:
                cat = "Over-Exploited"
            forecast_categories.append(cat)
            
        # Calculate risk assessment
        trend_direction = "increasing" if m_stage > 0.05 else "decreasing" if m_stage < -0.05 else "stable"
        
        explanation = (
            f"Based on historical linear trend regression (2016-2025), the groundwater extraction stage for {loc.title()} "
            f"is {trend_direction} at an annual rate of {m_stage:+.2f}%. "
            f"At this rate, the extraction stage is projected to reach {forecast_stages[-1]:.2f}% by 2030. "
            f"This would classify the resource status as '{forecast_categories[-1].upper()}'. "
            f"Historical recharge changes average {m_rech:+.2f} ham/year, while extraction demands are changing by {m_ext:+.2f} ham/year."
        )

        prediction_result = {
            "status": "success",
            "historical_slope_stage": float(m_stage),
            "historical_slope_extraction": float(m_ext),
            "historical_slope_recharge": float(m_rech),
            "trend": trend_direction,
            "forecast_years": [f"{fy}-{fy+1}" for fy in future_years],
            "forecast_stages": forecast_stages,
            "forecast_extractions": forecast_extractions,
            "forecast_recharges": forecast_recharges,
            "forecast_categories": forecast_categories,
            "explanation": explanation
        }
        
        logger.info(f"Prediction successful for {loc}. Projected 2030 stage: {forecast_stages[-1]:.2f}%")

        history = list(state.get("routing_history", []))
        history.append("prediction")

        # Determine next node in routing list
        routing_plan = ["recommendation", "synthesize"]
        next_node = "synthesize"
        for step in routing_plan:
            if step not in history:
                next_node = step
                break

        return {
            "context_prediction": prediction_result,
            "routing_history": history,
            "current_node": next_node
        }
