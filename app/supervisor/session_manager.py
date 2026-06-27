import uuid
import time
from typing import Dict, Any, Optional
from app.cache import cache
from app.logging_config import logger

class SessionManager:
    """Manages active user sessions, recovery, expiration, and caching of histories."""

    SESSION_PREFIX = "aquamind:session:"
    DEFAULT_TTL = 86400  # 24 hours in seconds

    @staticmethod
    def generate_session_id() -> str:
        """Generates a unique session identifier."""
        return f"sess_{uuid.uuid4().hex[:12]}"

    @classmethod
    def get_session(cls, session_id: str) -> Dict[str, Any]:
        """Retrieves active session context from Redis or returns a fresh session."""
        if not session_id:
            session_id = cls.generate_session_id()

        key = f"{cls.SESSION_PREFIX}{session_id}"
        session_data = cache.get(key)

        if not session_data or not isinstance(session_data, dict):
            # Create a fresh, empty session structure
            session_data = {
                "session_id": session_id,
                "user_id": "anonymous",
                "conversation_id": f"conv_{uuid.uuid4().hex[:12]}",
                "created_at": time.time(),
                "updated_at": time.time(),
                "history": [],
                "entities": {},
                "preferences": {"language": "en"}
            }
            cls.save_session(session_id, session_data)
            logger.info(f"Initialized new session registry context for {session_id}")
        else:
            logger.debug(f"Recovered active session context for {session_id}")

        return session_data

    @classmethod
    def save_session(cls, session_id: str, session_data: Dict[str, Any], ttl: int = DEFAULT_TTL) -> None:
        """Saves current session data back to the cache store with expiration."""
        if not session_id or not session_data:
            return
        
        session_data["updated_at"] = time.time()
        key = f"{cls.SESSION_PREFIX}{session_id}"
        cache.set(key, session_data, ex=ttl)

    @classmethod
    def expire_session(cls, session_id: str) -> None:
        """Manually expires/removes a session context."""
        key = f"{cls.SESSION_PREFIX}{session_id}"
        cache.delete(key)
        logger.info(f"Session {session_id} manually expired.")
