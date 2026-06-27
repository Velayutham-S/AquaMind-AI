import os
import time
from datetime import datetime
from app.agents.state import AgentState
from app.agents.llm import LLMService
from app.embeddings.confidence import ConfidenceEngine
from app.logging_config import logger
from app.supervisor.session_manager import SessionManager

class ResponseSynthesizer:
    @staticmethod
    def process(state: AgentState) -> dict:
        """Synthesizer node that merges all agent contexts and generates the final multi-lingual response."""
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
            
        emit_progress("Generation", "Generating final response...", 90)
        
        query = state["query"]
        
        # If response already exists in state (e.g. from GeneralAgent), bypass synthesis
        if state.get("response"):
            logger.info("Response already exists in state. Bypassing synthesis.")
            # Calculate latency of bypass
            synth_dur = (time.time() - start_time) * 1000.0
            timeline = session_data.get("execution_timeline") or []
            timeline.append({
                "time": datetime.utcnow().strftime("%H:%M:%S"),
                "stage": "Response Generator",
                "duration_ms": int(synth_dur)
            })
            session_data["execution_timeline"] = timeline
            emit_progress("Generation", "Generation completed", 95)
            session_data["progress_events"] = progress_events
            SessionManager.save_session(session_id, session_data)
            
            return {
                "response": state["response"],
                "confidence_score": state.get("confidence_score", 1.0),
                "confidence_reason": state.get("confidence_reason", "Pre-computed response bypass."),
                "routing_history": list(state.get("routing_history", [])) + ["synthesize"],
                "current_node": "evaluate"
            }
            
        lang = state.get("language", "en")
        data = state.get("context_data", [])
        knowledge = state.get("context_knowledge", [])
        prediction = state.get("context_prediction")
        simulation = state.get("context_simulation")
        recommendations = state.get("context_recommendations", [])
        analytics = state.get("context_analytics")
        pdf_path = state.get("pdf_report_path")
        
        logger.info(f"ResponseSynthesizer merging contexts for query: '{query}'")
        
        # 1. Compile context summary
        context_blocks = []
        
        if data:
            context_blocks.append(f"GEC Database Records for location:\n{data}")
        if analytics:
            context_blocks.append(f"Comparative Analytics Data:\n{analytics}")
        if knowledge:
            know_text = "\n".join([f"- Chunks from {c['document_name']} (Page {c['page_number']}): {c['text']}" for c in knowledge])
            context_blocks.append(f"Retrieved Document Excerpts:\n{know_text}")
        if prediction:
            context_blocks.append(f"Trend Forecast Output:\n{prediction.get('explanation')}")
        if simulation:
            context_blocks.append(f"What-if Simulation Output:\n{simulation.get('explanation')}")
        if recommendations:
            rec_text = "\n".join([f"- Title: {r['title']}, Action: {r['why']}, Impact: {r['impact']}" for r in recommendations])
            context_blocks.append(f"Tailored Action Plan:\n{rec_text}")

        merged_context = "\n\n".join(context_blocks)
        
        # 2. Formulate system prompt
        system_prompt = (
            "You are the Lead Groundwater Hydrologist and Expert AI Synthesizer for AquaMind AI.\n"
            "Your task is to draft a comprehensive, authoritative, and data-driven response to the user's query.\n"
            "Adhere strictly to these parameters:\n"
            "1. Grounding: Rely only on the provided GEC Database records and Document Excerpts. Do not make up facts.\n"
            "2. Citations: Interlace superscript bracket numbers (e.g. [1]) when referencing facts from the Document Excerpts.\n"
            "3. Formatting: Use clean markdown headers, bullet points, and tables. Avoid plain text blocks.\n"
            "4. Language: If the user asked in Tamil (language = ta) or mixed Tamil (language = mixed), answer in clear, standard Tamil script. "
            "If they asked in English, answer in English.\n"
            "5. Tone: Professional, informative, and expert-level.\n\n"
            "If the provided context does not contain enough information, explain what is missing rather than guessing."
        )

        prompt = (
            f"User Query: {query}\n\n"
            f"Available Context:\n{merged_context}\n\n"
            "Synthesize the response now:"
        )
        
        # 3. Generate response text
        response_text = LLMService.call(prompt, system_prompt=system_prompt)
        
        # 4. Calculate Confidence Score
        conf_data = ConfidenceEngine.calculate(state)
        
        # Prepend warning if confidence is extremely low
        if conf_data["confidence_score"] < 0.60:
            warning = (
                "⚠️ **Disclaimer:** I could not find sufficient authoritative records for this location in my database. "
                "The response below is synthesized from generic regional guidelines and may not reflect local conditions.\n\n"
            )
            response_text = warning + response_text
            
        # Append PDF download confirmation if report generated
        if pdf_path:
            pdf_filename = pdf_path.split(os.sep)[-1]
            report_msg = f"\n\n📂 *Groundwater assessment report compiled successfully. You can download the PDF from the sidebar: `{pdf_filename}`*"
            response_text += report_msg

        # Check debug mode to conditionally show reasoning
        debug_mode = os.getenv("DEBUG_MODE", "0") == "1"
        reasoning = session_data.get("reasoning") or []
        if debug_mode and reasoning:
            reasoning_block = "\n\n---\n### 🔍 Debug Mode: Planner Reasoning\n" + "\n".join([f"- {r}" for r in reasoning])
            response_text += reasoning_block

        history = list(state.get("routing_history", []))
        history.append("synthesize")
        
        logger.info("Response synthesis complete.")
        
        # Log latency
        synth_dur = (time.time() - start_time) * 1000.0
        timeline = session_data.get("execution_timeline") or []
        timeline.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "stage": "Response Generator",
            "duration_ms": int(synth_dur)
        })
        session_data["execution_timeline"] = timeline
        
        emit_progress("Generation", "Generation completed", 95)
        session_data["progress_events"] = progress_events
        SessionManager.save_session(session_id, session_data)

        return {
            "response": response_text,
            "confidence_score": conf_data["confidence_score"],
            "confidence_reason": conf_data["confidence_reason"],
            "routing_history": history,
            "current_node": "evaluate" # Route to evaluator node
        }
