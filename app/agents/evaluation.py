import time
from datetime import datetime
from app.agents.state import AgentState
from app.agents.llm import LLMService
from app.logging_config import logger
from app.supervisor.session_manager import SessionManager
from app.supervisor.report_generator import ExecutionReportGenerator

class EvaluationAgent:
    @staticmethod
    def process(state: AgentState) -> dict:
        """Evaluation node that runs a RAGAS-like post-synthesis quality check on response validity."""
        start_time = time.time()
        session_id = state.get("session_id", "default")
        
        # Recover Session context to append progress
        session_data = SessionManager.get_session(session_id)
        progress_events = session_data.get("progress_events") or []
        
        def emit_progress(stage: str, message: str, progress_pct: int):
            event = {
                "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
                "stage": stage,
                "message": message,
                "progress": progress_pct
            }
            progress_events.append(event)
            logger.info(f"[PROGRESS {progress_pct}%] {stage}: {message}")
            
        emit_progress("Validation", "Auditing and validating response...", 95)
        
        query = state["query"]
        response = state.get("response", "")
        data = state.get("context_data") or []
        knowledge = state.get("context_knowledge") or []
        routing = state.get("routing_history") or []
        lang = state.get("language") or "en"
        
        logger.info("EvaluationAgent executing post-response check...")
        
        if not response:
            logger.warning("No response text found to evaluate.")
            eval_dur = (time.time() - start_time) * 1000.0
            timeline = session_data.get("execution_timeline") or []
            timeline.append({
                "time": datetime.utcnow().strftime("%H:%M:%S"),
                "stage": "Output Validator",
                "duration_ms": int(eval_dur)
            })
            session_data["execution_timeline"] = timeline
            emit_progress("Validation", "Completed.", 100)
            session_data["progress_events"] = progress_events
            session_data["execution_status"] = "failed"
            SessionManager.save_session(session_id, session_data)
            
            # Generate final execution report
            ExecutionReportGenerator.generate(session_data, {})
            
            return {"evaluation": {"status": "skipped", "reason": "No response text available."}}

        # Format context parameters for the LLM validator
        context_str = "\n\n".join([f"Chunk {i+1} [{c.get('document_name')}, Page {c.get('page_number')}]: {c.get('text')}" for i, c in enumerate(knowledge)])
        db_str = str(data)

        system_prompt = (
            "You are the Independent AI Auditor for AquaMind AI.\n"
            "Analyze the RAG query, the retrieved contexts, database outputs, and the assistant's final response to score quality.\n"
            "Output your findings in JSON format with these exact keys:\n"
            "- routing_accuracy: float from 0.0 to 1.0 (did supervisor call the correct agents?)\n"
            "- retrieval_precision: float from 0.0 to 1.0 (are retrieved chunks highly relevant to query?)\n"
            "- grounding_score: float from 0.0 to 1.0 (is response grounded in context? 1.0 = no hallucination, 0.0 = completely fabricated)\n"
            "- citation_accuracy: float from 0.0 to 1.0 (are all cited documents relevant to assertions made?)\n"
            "- hallucination_detected: boolean (true if response makes claims not found in context or DB data)\n"
            "- language_accuracy: float from 0.0 to 1.0 (did response match the requested language style?)\n"
            "- summary: A brief 2-sentence quality audit report.\n\n"
            "Output MUST be raw JSON format only."
        )

        prompt = (
            f"Query: {query}\n\n"
            f"DB Context: {db_str}\n\n"
            f"RAG PDF Chunks:\n{context_str}\n\n"
            f"Invoked Routing History: {routing}\n\n"
            f"Generated Response:\n{response}\n"
        )
        
        evaluation = LLMService.call_json(prompt, system_prompt=system_prompt)
        logger.info(f"Auditor evaluation results: Grounding={evaluation.get('grounding_score')}, Hallucination={evaluation.get('hallucination_detected')}")
        
        # Log latency
        eval_dur = (time.time() - start_time) * 1000.0
        timeline = session_data.get("execution_timeline") or []
        timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Output Validator",
            "duration_ms": int(eval_dur)
        })
        session_data["execution_timeline"] = timeline
        
        emit_progress("Validation", "Completed.", 100)
        session_data["progress_events"] = progress_events
        session_data["execution_status"] = "completed"
        SessionManager.save_session(session_id, session_data)
        
        # Compile execution report
        ExecutionReportGenerator.generate(session_data, evaluation)
        
        routing.append("evaluate")
        return {
            "evaluation": evaluation,
            "routing_history": routing
        }
