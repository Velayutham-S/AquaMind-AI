from app.agents.llm import LLMService
from app.logging_config import logger

class QueryRewriter:
    @staticmethod
    def rewrite(query: str) -> str:
        """Rewrites vague user queries, resolves abbreviations, and normalizes groundwater terms."""
        system_prompt = (
            "You are an Expert Hydrology Query Optimizer for AquaMind AI.\n"
            "Your job is to rewrite the user query to be precise, clear, and optimized for search retrieval.\n"
            "Adhere to these rules:\n"
            "1. Resolve vagueness (e.g., 'What about Salem?' -> 'What is the groundwater status of Salem district?').\n"
            "2. Expand acronyms: CGWB to 'Central Ground Water Board', CGWA to 'Central Ground Water Authority', GEC to 'Groundwater Estimation Committee'.\n"
            "3. Keep the output query concise but descriptive. Do not add conversational prefixes, markdown, or extra explanations.\n"
            "4. Return ONLY the rewritten query text."
        )
        try:
            rewritten = LLMService.call(prompt=query, system_prompt=system_prompt)
            cleaned = rewritten.strip()
            # Basic sanity check to prevent returning error messages
            if cleaned and not cleaned.startswith("Error"):
                logger.info(f"Query rewriter: '{query}' -> '{cleaned}'")
                return cleaned
        except Exception as e:
            logger.error(f"QueryRewriter error: {e}")
        return query
