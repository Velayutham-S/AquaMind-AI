import time
from typing import Dict, Any, Optional
from langchain_core.runnables import RunnableConfig
from app.agents.state import AgentState
from app.logging_config import logger
from app.database import SessionLocal

# Import supervisor components
from app.supervisor.session_manager import SessionManager
from app.supervisor.language_detector import LanguageDetector
from app.supervisor.spell_corrector import SpellCorrector
from app.supervisor.query_normalizer import QueryNormalizer
from app.supervisor.entity_extractor import EntityExtractor
from app.supervisor.query_classifier import QueryClassifier
from app.supervisor.planner_cache import PlannerCache
from app.supervisor.planner import Planner
from app.supervisor.router import Router
from app.supervisor.execution_engine import ExecutionEngine
from app.supervisor.confidence_manager import ConfidenceManager
from app.supervisor.evidence_aggregator import EvidenceAggregator
from app.supervisor.supervisor_metrics import SupervisorMetrics
from app.supervisor.state import SupervisorState

class SupervisorAgent:
    """The central intelligence orchestrator that handles preprocessing, planning, parallel execution, routing, and collation."""

    @staticmethod
    def process(state: AgentState, config: RunnableConfig = None) -> dict:
        """Standard entry point node in LangGraph workflow, executing the decoupled orchestrator pattern."""
        start_time = time.time()
        
        session_id = state.get("session_id", "default")
        query = state["query"]
        
        # 1. Recover Session context
        session_data = SessionManager.get_session(session_id)
        
        # Extract progress callback if passed via config
        progress_callback = None
        logger.info(f"DEBUG: SupervisorAgent.process config argument: {config} (type: {type(config)})")
        if config:
            try:
                configurable = config.get("configurable")
                if configurable:
                    progress_callback = configurable.get("progress_callback")
            except AttributeError:
                pass
            
        progress_events = []
        execution_timeline = []
        
        from datetime import datetime
        
        def emit_progress(stage: str, message: str, progress_pct: int):
            event = {
                "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                "stage": stage,
                "message": message,
                "progress": progress_pct
            }
            progress_events.append(event)
            if progress_callback:
                try:
                    progress_callback(event)
                except Exception as cb_err:
                    logger.error(f"Progress callback error: {cb_err}")
            logger.info(f"[PROGRESS {progress_pct}%] {stage}: {message}")
            
        # 2. Text Pre-processing: Language, Spelling, Normalization
        emit_progress("Preprocessing", "Understanding your question...", 10)
        pre_start = time.time()
        lang = LanguageDetector.detect(query)
        emit_progress("Preprocessing", f"Language detected: {lang}", 15)
        
        corrected_query = SpellCorrector.correct(query)
        emit_progress("Preprocessing", "Correcting spelling...", 20)
        
        normalized_query = QueryNormalizer.normalize(corrected_query)
        pre_dur = (time.time() - pre_start) * 1000.0
        execution_timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Preprocessing",
            "duration_ms": int(pre_dur)
        })
        
        # 3. Entity Extraction
        ent_start = time.time()
        emit_progress("Entity Extraction", "Extracting entities...", 25)
        entities = EntityExtractor.extract_entities(normalized_query)
        ent_dur = (time.time() - ent_start) * 1000.0
        execution_timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Entity Extraction",
            "duration_ms": int(ent_dur)
        })
        
        # 4. Lightweight Intent Classification
        classification = QueryClassifier.classify(normalized_query)
        
        # 5. Formulate Execution Plan (utilizing PlannerCache)
        plan_start = time.time()
        emit_progress("Planning", "Planning execution...", 30)
        
        plan_cache_hit = False
        cached_plan = PlannerCache.get_cached_plan(normalized_query)
        if cached_plan:
            plan_cache_hit = True
            plan = cached_plan
        else:
            plan = Planner.plan(normalized_query, classification, entities)
            
        plan_dur = (time.time() - plan_start) * 1000.0
        execution_timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Planner",
            "duration_ms": int(plan_dur)
        })
        
        plan_agents = plan.get("agents", [])
        plan_tools = plan.get("tools", [])
        emit_progress("Planning", f"Planning completed. Selected Agents: {', '.join(plan_agents)}", 35)
        
        # Merge planner-extracted entities if rule-based extraction missed them
        plan_entities = plan.get("entities", {})
        if plan_entities:
            plan_loc = plan_entities.get("location")
            plan_year = plan_entities.get("year")
            
            db = SessionLocal()
            try:
                if plan_loc and not entities["location"]:
                    from app.resolution import LocationResolver
                    res = LocationResolver.resolve_location(db, plan_loc, threshold=0.8)
                    if res and res["resolved"]:
                        entities["location"] = res["resolved"]
                        entities["location_type"] = res["type"]
                if plan_year and not entities["year"]:
                    entities["year"] = plan_year
            except Exception as e:
                logger.error(f"Supervisor error resolving planner entities: {e}")
            finally:
                db.close()
        
        logger.info(f"Execution Plan compiled: {plan}")

        # 6. Separate Router determines LangGraph next node and routing path
        route_start = time.time()
        route_info = Router.determine_route(plan, state)
        current_node = route_info["current_node"]
        routing_history = route_info["routing_history"]

        # Append execution plan agents to routing history if running inside execution engine
        if len(plan_agents) > 1:
            for a in plan_agents:
                routing_history.append(a.lower().replace("agent", ""))
                
        route_dur = (time.time() - route_start) * 1000.0
        execution_timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Router",
            "duration_ms": int(route_dur)
        })

        # 7. Parallel Agent Execution (with retry / fallback policies)
        exec_start = time.time()
        emit_progress("Execution", "Executing scheduled agents...", 45)
        
        if "DataAgent" in plan_agents:
            emit_progress("Execution", "Running DataAgent...", 50)
        if any(a in plan_agents for a in ["PredictionAgent", "SimulationAgent"]):
            emit_progress("Execution", "Running concurrent analysis agents...", 60)
            if "ChartGenerator" in plan_tools:
                emit_progress("Execution", "Generating groundwater chart...", 65)
        if "ReportAgent" in plan_agents:
            emit_progress("Execution", "Running ReportAgent...", 70)
            
        agent_results = ExecutionEngine.execute(plan_agents, {
            **state,
            "query": normalized_query,
            "resolved_location": entities["location"],
            "resolved_location_type": entities["location_type"],
            "resolved_year": entities["year"]
        })
        
        exec_dur = (time.time() - exec_start) * 1000.0
        execution_timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Execution Engine",
            "duration_ms": int(exec_dur)
        })

        # 8. Collate Outputs using the Evidence Aggregator
        agg_start = time.time()
        emit_progress("Aggregation", "Aggregating evidence...", 75)
        collated_evidence = EvidenceAggregator.aggregate(agent_results)
        agg_dur = (time.time() - agg_start) * 1000.0
        execution_timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Evidence Aggregator",
            "duration_ms": int(agg_dur)
        })

        # 9. Compound Confidence Assessment
        confidence_data = ConfidenceManager.compute_overall_confidence(
            plan_agents, 
            agent_results,
            plan_confidence=plan.get("confidence", 0.95)
        )

        # 10. Record operational metrics
        total_latency = time.time() - start_time
        metrics_data = {
            "total_latency": total_latency,
            "intent": plan.get("intent", classification),
            "language": lang,
            "cache_hit": plan_cache_hit,
            "agents_called": plan_agents,
            "confidence_score": confidence_data["overall_confidence"]
        }
        SupervisorMetrics.record_metrics(session_id, metrics_data)

        # Save context history to session registry
        session_data["history"].append({"sender": "user", "content": query})
        session_data["reasoning"] = plan.get("reasoning", [])
        session_data["progress_events"] = progress_events
        session_data["execution_status"] = "running"
        session_data["overall_confidence"] = confidence_data["overall_confidence"]
        session_data["confidence_level"] = confidence_data["confidence_level"]
        session_data["confidence_breakdown"] = confidence_data["confidence_breakdown"]
        session_data["execution_timeline"] = execution_timeline
        session_data["execution_plan"] = plan
        
        SessionManager.save_session(session_id, session_data)

        # 11. Compile final state update dictionary
        return {
            **collated_evidence,
            "query": normalized_query,
            "original_query": query,
            "language": lang,
            "intent": plan.get("intent", classification.lower()),
            "resolved_location": entities["location"],
            "resolved_location_type": entities["location_type"],
            "resolved_year": entities["year"],
            "confidence_score": confidence_data["overall_confidence"],
            "confidence_reason": confidence_data["explanation"],
            "routing_history": routing_history,
            "current_node": current_node
        }

