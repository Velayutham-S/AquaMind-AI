import re
from typing import Dict, Any, Optional
from app.cache import cache
from app.logging_config import logger

class PlannerCache:
    """Manages serialization, storage, and retrieval of supervisor planning caches."""

    CACHE_PREFIX = "aquamind:plan:"
    PLAN_TTL = 172800  # 48 hours

    @classmethod
    def normalize_cache_key(cls, query: str) -> str:
        """Helper to create a standard, lowercase, alphanumeric-only key for hashing."""
        clean = query.strip().lower()
        clean = re.sub(r'[^a-z0-9]', '', clean)
        return clean

    @classmethod
    def get_cached_plan(cls, query: str) -> Optional[Dict[str, Any]]:
        """Retrieves execution plan from cache if it exists."""
        key = cls.normalize_cache_key(query)
        cache_key = f"{cls.CACHE_PREFIX}{key}"
        try:
            cached_plan = cache.get(cache_key)
            if cached_plan and isinstance(cached_plan, dict):
                logger.info(f"Execution plan recovered from cache for query: '{query}'")
                return cached_plan
        except Exception as e:
            logger.error(f"Failed to fetch execution plan from cache: {e}")
        return None

    @classmethod
    def set_cached_plan(cls, query: str, plan: Dict[str, Any]) -> None:
        """Saves execution plan to cache."""
        key = cls.normalize_cache_key(query)
        cache_key = f"{cls.CACHE_PREFIX}{key}"
        try:
            cache.set(cache_key, plan, ex=cls.PLAN_TTL)
            logger.info(f"Saved execution plan to cache under key: {cache_key}")
        except Exception as e:
            logger.error(f"Failed to cache execution plan: {e}")
