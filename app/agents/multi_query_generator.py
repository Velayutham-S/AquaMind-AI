import json
from typing import List
from app.agents.llm import LLMService
from app.logging_config import logger

class MultiQueryGenerator:
    @staticmethod
    def generate(query: str) -> List[str]:
        """Generates multiple search queries from a user query to optimize search recall."""
        system_prompt = (
            "You are a search query expansion assistant for AquaMind AI.\n"
            "Generate 3 to 5 alternative queries that represent different ways to search for information related to the input query.\n"
            "Focus on different terms, abbreviations, and synonyms (e.g. recharge, extraction, resource assessment, availability).\n"
            "Output your findings in JSON format with a single key 'queries' containing a list of strings.\n"
            "Output ONLY valid JSON."
        )
        try:
            res = LLMService.call_json(prompt=query, system_prompt=system_prompt)
            if res and isinstance(res.get("queries"), list):
                queries = [q.strip() for q in res["queries"] if q.strip()]
                if queries:
                    if query not in queries:
                        queries.insert(0, query)
                    logger.info(f"MultiQueryGenerator generated: {queries}")
                    return queries
        except Exception as e:
            logger.error(f"MultiQueryGenerator error: {e}")
        return [query]
