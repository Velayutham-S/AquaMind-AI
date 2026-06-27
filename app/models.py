from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class DistrictAssessment(Base):
    __tablename__ = "district_assessments"
    
    id = Column(Integer, primary_key=True, index=True)
    state = Column(String, index=True)
    district = Column(String, index=True)
    year = Column(String, index=True) # e.g. "2024-2025"
    
    # Ground Water Recharge components (ham)
    rainfall_recharge = Column(Float, nullable=True)
    other_recharge = Column(Float, nullable=True)
    total_recharge = Column(Float, nullable=True)
    annual_extractable = Column(Float, nullable=True)
    
    # Extraction components (ham)
    extraction_irrigation = Column(Float, nullable=True)
    extraction_domestic = Column(Float, nullable=True)
    extraction_industrial = Column(Float, nullable=True)
    total_extraction = Column(Float, nullable=True)
    
    # Stage & Categorization
    stage_of_extraction = Column(Float, nullable=True) # %
    category = Column(String, index=True) # e.g., Safe, Semi-Critical, Critical, Over-Exploited
    quality_tag = Column(Text, nullable=True)
    
    # Schema-on-Read fallback for all other raw columns
    raw_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class FirkaAssessment(Base):
    __tablename__ = "firka_assessments"
    
    id = Column(Integer, primary_key=True, index=True)
    state = Column(String, index=True)
    district = Column(String, index=True)
    firka = Column(String, index=True)
    watershed_or_block = Column(String, nullable=True)
    year = Column(String, index=True)
    
    # Resources (ham)
    total_recharge = Column(Float, nullable=True)
    annual_extractable = Column(Float, nullable=True)
    total_extraction = Column(Float, nullable=True)
    stage_of_extraction = Column(Float, nullable=True)
    category = Column(String, index=True)
    quality_tag = Column(Text, nullable=True)
    
    raw_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class MonitoringData(Base):
    __tablename__ = "monitoring_data"
    
    id = Column(Integer, primary_key=True, index=True)
    station = Column(String, index=True)
    agency = Column(String, nullable=True)
    district = Column(String, index=True)
    tehsil = Column(String, nullable=True)
    block = Column(String, nullable=True)
    village = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    parameter = Column(String, index=True) # e.g., "groundwater_level", "rainfall", "river_discharge", "river_level"
    acquisition_time = Column(DateTime, index=True)
    value = Column(Float)
    unit = Column(String, nullable=True) # e.g., "meter", "mm", "m3/sec"
    
    dataset_source = Column(String) # filename or telemetry code
    created_at = Column(DateTime, default=datetime.utcnow)

class SessionMemory(Base):
    __tablename__ = "session_memories"
    
    session_id = Column(String, primary_key=True, index=True)
    summary = Column(Text, nullable=True)
    entities = Column(JSON, default=dict) # e.g., active locations, active years
    preferences = Column(JSON, default=dict) # e.g., language, detail level
    long_term_profile = Column(JSON, default=dict) # profile elements remembered across sessions
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("session_memories.session_id"), index=True)
    sender = Column(String) # "user" or "assistant"
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Metadata for enterprise reporting
    language = Column(String, default="en") # en, ta, mixed
    confidence_score = Column(Float, nullable=True)
    confidence_reason = Column(Text, nullable=True)
    agent_routing = Column(JSON, nullable=True) # list of agents invoked
    citations = Column(JSON, nullable=True) # citations list with doc, page, text
    
    session = relationship("SessionMemory", back_populates="messages")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_role = Column(String, default="user") # user, expert, admin
    action = Column(String, index=True) # e.g., "query", "ingest", "run_simulation"
    details = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, unique=True, index=True)
    title = Column(String, index=True)
    source = Column(String, index=True)
    collection = Column(String, index=True)
    version = Column(String, default="1.0")
    pages = Column(Integer, nullable=True)
    chunks = Column(Integer, nullable=True)
    embedding_model = Column(String, nullable=True)
    checksum = Column(String, nullable=True)
    district = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Chunk(Base):
    __tablename__ = "chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(String, unique=True, index=True)
    document_id = Column(String, ForeignKey("documents.document_id"), index=True)
    page_number = Column(Integer, nullable=True)
    section_title = Column(String, nullable=True)
    text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class UploadHistory(Base):
    __tablename__ = "upload_history"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    file_type = Column(String)
    status = Column(String) # "success", "failed"
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

class SourceRegistry(Base):
    __tablename__ = "source_registry"
    
    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String, unique=True, index=True)
    authority_type = Column(String) # e.g. "State", "Central"
    description = Column(Text, nullable=True)

class DistrictMaster(Base):
    __tablename__ = "district_master"
    id = Column(Integer, primary_key=True, index=True)
    district_name = Column(String, unique=True, index=True)

class TalukMaster(Base):
    __tablename__ = "taluk_master"
    id = Column(Integer, primary_key=True, index=True)
    taluk_name = Column(String, index=True)
    district_name = Column(String, index=True)

class FirkaMaster(Base):
    __tablename__ = "firka_master"
    id = Column(Integer, primary_key=True, index=True)
    firka_name = Column(String, index=True)
    taluk_name = Column(String, index=True)
    district_name = Column(String, index=True)

class VillageMaster(Base):
    __tablename__ = "village_master"
    
    id = Column(Integer, primary_key=True, index=True)
    village_id = Column(String, unique=True, index=True)
    village_name = Column(String, index=True)
    village_name_tamil = Column(String, nullable=True)
    village_aliases = Column(Text, nullable=True)
    firka = Column(String, index=True)
    taluk = Column(String, index=True)
    district = Column(String, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    pincode = Column(String, nullable=True)
    lgd_code = Column(String, nullable=True)
    source = Column(String, nullable=True)
    confidence = Column(Float, default=1.0)

class AquiferMaster(Base):
    __tablename__ = "aquifer_master"
    id = Column(Integer, primary_key=True, index=True)
    aquifer_name = Column(String, unique=True, index=True)
    type = Column(String, nullable=True)

class RiverBasinMaster(Base):
    __tablename__ = "river_basin_master"
    id = Column(Integer, primary_key=True, index=True)
    river_basin_name = Column(String, unique=True, index=True)

class WatershedMaster(Base):
    __tablename__ = "watershed_master"
    id = Column(Integer, primary_key=True, index=True)
    watershed_name = Column(String, unique=True, index=True)
