import os
from typing import Dict, Any, Generator
from app.agents.llm import LLMService
from app.logging_config import logger

class ResponseGenerator:
    """Compiles and generates the final grounded multilingual response from aggregated evidence (with streaming support)."""

    @classmethod
    def compile_context(cls, state: Dict[str, Any]) -> str:
        """Helper to assemble a single context narrative block from state variables."""
        data = state.get("context_data", [])
        analytics = state.get("context_analytics")
        knowledge = state.get("context_knowledge", [])
        prediction = state.get("context_prediction")
        simulation = state.get("context_simulation")
        recommendations = state.get("context_recommendations", [])

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

        return "\n\n".join(context_blocks)

    @classmethod
    def get_system_prompt(cls) -> str:
        return (
            "You are the Lead Groundwater Hydrologist and Expert AI Synthesizer for AquaMind AI.\n"
            "Your task is to draft a comprehensive, authoritative, and data-driven response to the user's query.\n"
            "Adhere strictly to these parameters:\n"
            "1. Grounding: Rely only on the provided GEC Database records and Document Excerpts. Do not make up facts.\n"
            "2. Citations: Interlace superscript bracket numbers (e.g. [1]) when referencing facts from the Document Excerpts.\n"
            "3. Formatting: Use clean markdown headers, bullet points, and tables. Avoid plain text blocks.\n"
            "4. Language: If the user asked in Tamil (language = ta) or mixed Tamil (language = mixed), answer in clear, Tamil script. "
            "If they asked in English, answer in English.\n"
            "5. Tone: Professional, informative, and expert-level.\n\n"
            "If the provided context does not contain enough information, explain what is missing rather than guessing."
        )

    @classmethod
    def generate(cls, state: Dict[str, Any]) -> str:
        """Synchronously generates the entire response text."""
        query = state["query"]
        merged_context = cls.compile_context(state)
        system_prompt = cls.get_system_prompt()

        prompt = (
            f"User Query: {query}\n\n"
            f"Available Context:\n{merged_context}\n\n"
            "Synthesize the response now:"
        )

        return LLMService.call(prompt, system_prompt=system_prompt)

    @classmethod
    def stream_generate(cls, state: Dict[str, Any]) -> Generator[str, None, None]:
        """Streams progress status statements followed by token chunks of the synthesized response."""
        yield "[STATUS] Synthesizing context data...\n"
        
        query = state["query"]
        merged_context = cls.compile_context(state)
        system_prompt = cls.get_system_prompt()

        prompt = (
            f"User Query: {query}\n\n"
            f"Available Context:\n{merged_context}\n\n"
            "Synthesize the response now:"
        )

        yield "[STATUS] Generating final response...\n"
        
        # Call streaming generator on LLMService
        for chunk in LLMService.call_stream(prompt, system_prompt=system_prompt):
            yield chunk
