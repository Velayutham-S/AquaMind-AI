import concurrent.futures
from typing import Dict, Any, List
from app.supervisor.agent_registry import AgentRegistry
from app.logging_config import logger

class ExecutionEngine:
    """Executes planned agents concurrently using a thread pool, implementing retries and graceful fallback routing."""

    @classmethod
    def execute(cls, plan_agents: List[str], state: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the planned agents in waves to satisfy dependencies while maximizing concurrency."""
        if not plan_agents:
            return {}

        logger.info(f"ExecutionEngine scheduling agents: {plan_agents}")
        
        results = {}
        # Make a local mutable copy of state so we can pass updates downstream
        local_state = dict(state)
        
        # Group into waves
        wave1 = [a for a in plan_agents if a == "DataAgent"]
        wave2 = [a for a in plan_agents if a not in ["DataAgent", "ReportAgent"]]
        wave3 = [a for a in plan_agents if a == "ReportAgent"]
        
        # --- Wave 1: DataAgent ---
        if wave1:
            logger.info("Executing Wave 1: DataAgent")
            for agent_name in wave1:
                try:
                    res = cls._run_agent_with_retry(agent_name, local_state)
                    if res:
                        results[agent_name] = res
                        local_state.update(res)
                except Exception as e:
                    logger.error(f"Wave 1 Agent '{agent_name}' failed: {e}. Activating fallback.")
                    fallback_res = cls._handle_agent_fallback(agent_name, local_state)
                    results[agent_name] = fallback_res
                    local_state.update(fallback_res)
                    
        # --- Wave 2: Intermediate concurrent agents ---
        if wave2:
            logger.info(f"Executing Wave 2 (Parallel): {wave2}")
            futures = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(wave2)) as executor:
                for agent_name in wave2:
                    futures[executor.submit(cls._run_agent_with_retry, agent_name, local_state)] = agent_name
                
                for future in concurrent.futures.as_completed(futures):
                    agent_name = futures[future]
                    try:
                        res = future.result()
                        if res:
                            results[agent_name] = res
                            local_state.update(res)
                    except Exception as e:
                        logger.error(f"Wave 2 Agent '{agent_name}' failed: {e}. Activating fallback.")
                        fallback_res = cls._handle_agent_fallback(agent_name, local_state)
                        results[agent_name] = fallback_res
                        local_state.update(fallback_res)
                        
        # --- Wave 3: ReportAgent ---
        if wave3:
            logger.info("Executing Wave 3: ReportAgent")
            for agent_name in wave3:
                try:
                    res = cls._run_agent_with_retry(agent_name, local_state)
                    if res:
                        results[agent_name] = res
                        local_state.update(res)
                except Exception as e:
                    logger.error(f"Wave 3 Agent '{agent_name}' failed: {e}. Activating fallback.")
                    fallback_res = cls._handle_agent_fallback(agent_name, local_state)
                    results[agent_name] = fallback_res
                    local_state.update(fallback_res)
                    
        return results

    @classmethod
    def _run_agent_with_retry(cls, agent_name: str, state: Dict[str, Any], retries: int = 1) -> Dict[str, Any]:
        """Runs a single agent, retrying once on failure before raising."""
        attempt = 0
        while True:
            try:
                logger.debug(f"Invoking {agent_name} (attempt {attempt + 1}/{retries + 1})...")
                # Invoke the agent's process method
                return AgentRegistry.invoke_agent(agent_name, state)
            except Exception as e:
                attempt += 1
                logger.warning(f"Attempt {attempt} for {agent_name} failed: {e}")
                if attempt > retries:
                    raise e

    @classmethod
    def _handle_agent_fallback(cls, agent_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Executes custom fallback policies for failed agents to allow graceful degradation."""
        logger.info(f"Applying fallback policy for failed agent: {agent_name}")
        
        if agent_name == "PredictionAgent":
            # Fallback to KnowledgeAgent to explain current data instead of regression projections
            try:
                logger.info("PredictionAgent fallback: Invoking KnowledgeAgent to provide descriptive context...")
                know_res = AgentRegistry.invoke_agent("KnowledgeAgent", state)
                # Mark prediction status as unavailable
                know_res["context_prediction"] = {
                    "status": "unavailable",
                    "explanation": "Groundwater trend forecasts are temporarily unavailable. Displaying historical qualitative insights."
                }
                return know_res
            except Exception as fallback_err:
                logger.error(f"PredictionAgent fallback invocation also failed: {fallback_err}")
                return {
                    "context_prediction": {
                        "status": "error",
                        "explanation": "Trend forecasts are currently unavailable due to an agent error."
                    }
                }
                
        elif agent_name == "GISAgent":
            return {
                "map_html": None,
                "gis_error": "Interactive map rendering is temporarily unavailable."
            }
            
        elif agent_name == "ReportAgent":
            return {
                "pdf_report_path": None,
                "report_error": "Report PDF compilation failed. You can view the online assessment details below."
            }

        # General safety default return
        return {
            f"context_{agent_name.lower().replace('agent','')}_status": "failed",
            "error_msg": "Agent execution failed."
        }
