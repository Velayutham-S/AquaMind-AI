from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import Config
from app.logging_config import logger

# Declare SQLAlchemy declarative base
Base = declarative_base()

# Configure Engine
try:
    # Use pool_pre_ping to check connection viability
    engine_kwargs = {"pool_pre_ping": True}
    
    # Configure pool sizing for both SQLite and PostgreSQL to handle parallel stress testing
    if Config.DB_URL.startswith("sqlite"):
        engine_kwargs.update({
            "pool_size": 120,
            "max_overflow": 50,
            "connect_args": {"timeout": 60.0, "check_same_thread": False}
        })
    else:
        engine_kwargs.update({
            "pool_size": 100,
            "max_overflow": 50
        })
        
    engine = create_engine(Config.DB_URL, **engine_kwargs)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info(f"Database connection engine established for URL: {Config.DB_URL.split('@')[-1] if '@' in Config.DB_URL else Config.DB_URL}")
except Exception as e:
    logger.error(f"Failed to initialize database engine: {e}", exc_info=True)
    raise e

def get_db():
    """Dependency for getting DB session, handles cleanup automatically."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initializes tables in database and runs simple schema migrations."""
    try:
        Base.metadata.create_all(bind=engine)
        # Check if district column exists in documents table (SQLite migration helper)
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        if 'documents' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('documents')]
            if 'district' not in columns:
                logger.info("Altering documents table to add 'district' column...")
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE documents ADD COLUMN district VARCHAR"))
                    conn.commit()
                logger.info("Successfully added 'district' column to documents table.")
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database tables: {e}", exc_info=True)
        raise e
