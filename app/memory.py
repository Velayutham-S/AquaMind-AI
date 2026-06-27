from sqlalchemy.orm import Session
from datetime import datetime
from app.models import SessionMemory, ChatMessage
from app.logging_config import logger

class MemoryEngine:
    @staticmethod
    def get_or_create_session(db: Session, session_id: str) -> SessionMemory:
        """Retrieves an existing session memory or initializes a new one."""
        session = db.query(SessionMemory).filter(SessionMemory.session_id == session_id).first()
        if not session:
            try:
                session = SessionMemory(
                    session_id=session_id,
                    summary="",
                    entities={},
                    preferences={"language": "en", "detail_level": "technical"},
                    long_term_profile={}
                )
                db.add(session)
                db.commit()
                db.refresh(session)
                logger.info(f"Initialized new memory session: {session_id}")
            except Exception as e:
                db.rollback()
                logger.error(f"Error creating session memory for {session_id}: {e}")
                # Fallback to unsaved transient object
                session = SessionMemory(
                    session_id=session_id,
                    summary="",
                    entities={},
                    preferences={"language": "en", "detail_level": "technical"},
                    long_term_profile={}
                )
        return session

    @staticmethod
    def save_message(
        db: Session, 
        session_id: str, 
        sender: str, 
        content: str,
        language: str = "en",
        confidence_score: float = None,
        confidence_reason: str = None,
        agent_routing: list = None,
        citations: list = None
    ) -> ChatMessage:
        """Saves a single message to the conversation history and updates session updated_at timestamp."""
        # Ensure session exists
        MemoryEngine.get_or_create_session(db, session_id)
        
        try:
            msg = ChatMessage(
                session_id=session_id,
                sender=sender,
                content=content,
                timestamp=datetime.utcnow(),
                language=language,
                confidence_score=confidence_score,
                confidence_reason=confidence_reason,
                agent_routing=agent_routing,
                citations=citations
            )
            db.add(msg)
            
            # Update session timestamp
            db.query(SessionMemory).filter(SessionMemory.session_id == session_id).update({
                "updated_at": datetime.utcnow()
            })
            
            db.commit()
            db.refresh(msg)
            return msg
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save message for session {session_id}: {e}")
            raise e

    @staticmethod
    def update_entities(db: Session, session_id: str, new_entities: dict) -> dict:
        """Merges new extracted entities (locations, years) into session memory."""
        session = MemoryEngine.get_or_create_session(db, session_id)
        current = dict(session.entities or {})
        current.update(new_entities)
        
        try:
            db.query(SessionMemory).filter(SessionMemory.session_id == session_id).update({
                "entities": current,
                "updated_at": datetime.utcnow()
            })
            db.commit()
            logger.info(f"Updated entities for session {session_id}: {new_entities}")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update entities for session {session_id}: {e}")
        return current

    @staticmethod
    def update_preferences(db: Session, session_id: str, new_prefs: dict) -> dict:
        """Merges new preferences (language, response style) into session memory."""
        session = MemoryEngine.get_or_create_session(db, session_id)
        current = dict(session.preferences or {})
        current.update(new_prefs)
        
        try:
            db.query(SessionMemory).filter(SessionMemory.session_id == session_id).update({
                "preferences": current,
                "updated_at": datetime.utcnow()
            })
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update preferences for session {session_id}: {e}")
        return current

    @staticmethod
    def get_context(db: Session, session_id: str, limit: int = 10) -> dict:
        """Retrieves active conversation history, entities, and summarized memory."""
        session = MemoryEngine.get_or_create_session(db, session_id)
        
        messages = db.query(ChatMessage)\
            .filter(ChatMessage.session_id == session_id)\
            .order_by(ChatMessage.timestamp.desc())\
            .limit(limit)\
            .all()
            
        # Reverse to chronological order
        messages.reverse()
        
        history = [{"sender": m.sender, "content": m.content} for m in messages]
        
        return {
            "summary": session.summary or "",
            "entities": session.entities or {},
            "preferences": session.preferences or {},
            "history": history
        }

    @staticmethod
    def run_summarization(db: Session, session_id: str, llm_client) -> str:
        """Invokes LLM to summarize conversation if message count is large, compacting history."""
        session = MemoryEngine.get_or_create_session(db, session_id)
        messages = db.query(ChatMessage)\
            .filter(ChatMessage.session_id == session_id)\
            .order_by(ChatMessage.timestamp.asc())\
            .all()
            
        if len(messages) < 12:
            return session.summary
            
        # Format text to summarize
        full_text = []
        if session.summary:
            full_text.append(f"Previous Summary: {session.summary}\n")
        
        for m in messages:
            full_text.append(f"{m.sender}: {m.content}")
            
        conversation_str = "\n".join(full_text)
        prompt = (
            "Summarize the following discussion related to groundwater in Tamil Nadu. "
            "Preserve key locations, years, district statistics, and user concerns mentioned. "
            "Write the summary in English and keep it brief.\n\n"
            f"{conversation_str}"
        )
        
        try:
            new_summary = llm_client.generate(prompt)
            db.query(SessionMemory).filter(SessionMemory.session_id == session_id).update({
                "summary": new_summary,
                "updated_at": datetime.utcnow()
            })
            db.commit()
            logger.info(f"Summarized conversation history for session {session_id}")
            return new_summary
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to summarize history for session {session_id}: {e}")
            return session.summary
