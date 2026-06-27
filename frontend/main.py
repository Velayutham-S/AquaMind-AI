import os
import folium
from datetime import datetime
import streamlit as st
from streamlit_folium import st_folium
from sqlalchemy.orm import Session
from app.database import SessionLocal, init_db
from app.agents.graph import agent_graph
from app.memory import MemoryEngine
from app.pipelines.ingest import IngestionPipeline
from app.logging_config import logger

# Initialize database
init_db()

# Streamlit App Configurations
st.set_page_config(
    page_title="AquaMind AI - Groundwater Intelligence Platform",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling using CSS injection
st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Outfit', sans-serif;
            background-color: #F8FAFC;
        }
        
        .main-header {
            background: linear-gradient(135deg, #002B49 0%, #1E5B84 100%);
            padding: 2rem;
            border-radius: 12px;
            color: white;
            margin-bottom: 2rem;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        }
        
        .kpi-card {
            background: white;
            border-radius: 10px;
            padding: 1.2rem;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
            border-left: 5px solid #1E5B84;
            margin-bottom: 1rem;
        }
        
        .kpi-title {
            font-size: 0.85rem;
            color: #718096;
            text-transform: uppercase;
            font-weight: 600;
        }
        
        .kpi-value {
            font-size: 1.6rem;
            font-weight: 800;
            color: #2D3748;
            margin-top: 0.2rem;
        }
        
        /* Chat bubble styles */
        .chat-bubble-user {
            background-color: #EDF2F7;
            padding: 1rem;
            border-radius: 15px 15px 0px 15px;
            margin: 0.5rem 0;
            max-width: 80%;
            float: right;
            clear: both;
        }
        
        .chat-bubble-assistant {
            background-color: #E2E8F0;
            border-left: 4px solid #1E5B84;
            padding: 1rem;
            border-radius: 0px 15px 15px 15px;
            margin: 0.5rem 0;
            max-width: 85%;
            float: left;
            clear: both;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# Active Session configuration
if "session_id" not in st.session_state:
    st.session_state.session_id = "session_" + datetime.utcnow().strftime("%Y%m%d%H%M%S")
if "language" not in st.session_state:
    st.session_state.language = "en"
if "history" not in st.session_state:
    st.session_state.history = []
if "active_map" not in st.session_state:
    st.session_state.active_map = None
if "active_charts" not in st.session_state:
    st.session_state.active_charts = []
if "pdf_reports" not in st.session_state:
    st.session_state.pdf_reports = []

db = SessionLocal()

# Translations map for multilingual support
T = {
    "en": {
        "title": "AquaMind AI Platform",
        "subtitle": "Tamil Nadu Groundwater Intelligence & Decision Support",
        "chat_tab": "💬 Hydrology Chat Copilot",
        "data_tab": "📊 Monitoring & Visualizations",
        "expert_tab": "🔒 Expert Data Ingestion",
        "input_placeholder": "Ask a groundwater question about a Tamil Nadu district/firka...",
        "confidence": "Confidence Score",
        "language_toggle": "தமிழ் பதிப்பு (Tamil Version)",
        "upload_label": "Upload raw reports or datasets (PDF, Excel, CSV)",
        "upload_btn": "Process File",
        "voice_input": "Enable Voice Input (Microphone)",
        "clear_btn": "Clear Session"
    },
    "ta": {
        "title": "அக்வாமைண்ட் ஏஐ தளம்",
        "subtitle": "தமிழ்நாடு நிலத்தடி நீர் நுண்ணறிவு மற்றும் முடிவு ஆதரவு",
        "chat_tab": "💬 நீரியல் உரையாடல்",
        "data_tab": "📊 கண்காணிப்பு & விளக்கப்படங்கள்",
        "expert_tab": "🔒 நிபுணர் தரவு பதிவேற்றம்",
        "input_placeholder": "தமிழ்நாடு மாவட்டம்/பிர்கா பற்றிய நிலத்தடி நீர் கேள்வியைக் கேளுங்கள்...",
        "confidence": "நம்பிக்கை மதிப்பெண்",
        "language_toggle": "English Version",
        "upload_label": "அறிக்கைகள் அல்லது கோப்புகளைப் பதிவேற்றவும் (PDF, Excel, CSV)",
        "upload_btn": "கோப்பைச் செயலாக்கு",
        "voice_input": "குரல் உள்ளீட்டை இயக்கு",
        "clear_btn": "அமர்வு நீக்கு"
    }
}

lang = st.session_state.language
trans = T[lang]

# ----------------- SIDEBAR CONTENT -----------------
with st.sidebar:
    st.image("https://img.icons8.com/color/120/water.png", width=70)
    st.title("AquaMind AI")
    st.write(trans["subtitle"])
    st.write("---")
    
    # Language switch button
    if st.button(trans["language_toggle"]):
        st.session_state.language = "ta" if lang == "en" else "en"
        st.rerun()

    if st.button(trans["clear_btn"]):
        st.session_state.session_id = "session_" + datetime.utcnow().strftime("%Y%m%d%H%M%S")
        st.session_state.history = []
        st.session_state.active_map = None
        st.session_state.active_charts = []
        st.session_state.pdf_reports = []
        st.rerun()
        
    st.write("---")
    st.subheader("Available PDF Reports")
    for r_path in st.session_state.pdf_reports:
        r_name = os.path.basename(r_path)
        try:
            with open(r_path, "rb") as f:
                st.download_button(
                    label=f"📥 Download {r_name}",
                    data=f.read(),
                    file_name=r_name,
                    mime="application/pdf",
                    key=r_name
                )
        except Exception as e:
            st.error(f"Failed to load PDF {r_name}: {e}")

# ----------------- MAIN LAYOUT -----------------
st.markdown(
    f"""
    <div class="main-header">
        <h1 style="margin:0; font-weight:800; font-size:2.3rem;">💧 {trans["title"]}</h1>
        <p style="margin:0.5rem 0 0 0; opacity:0.85; font-size:1.1rem;">{trans["subtitle"]}</p>
    </div>
    """,
    unsafe_allow_html=True
)

tab1, tab2, tab3 = st.tabs([trans["chat_tab"], trans["data_tab"], trans["expert_tab"]])

# ----------------- TAB 1: CHAT COPILOT -----------------
with tab1:
    chat_container = st.container()
    
    # Fetch historical messages from DB to display
    context = MemoryEngine.get_context(db, st.session_state.session_id, limit=20)
    
    with chat_container:
        for msg in context["history"]:
            bubble_class = "chat-bubble-user" if msg["sender"] == "user" else "chat-bubble-assistant"
            align = "right" if msg["sender"] == "user" else "left"
            st.markdown(
                f'<div class="{bubble_class}">{msg["content"]}</div>', 
                unsafe_allowed_html=True
            )
            
    # Audio inputs placeholder
    st.checkbox(trans["voice_input"], value=False)
            
    # Chat Input Box
    user_query = st.chat_input(trans["input_placeholder"])
    
    if user_query:
        # Show user message immediately
        st.markdown(f'<div class="chat-bubble-user">{user_query}</div>', unsafe_allowed_html=True)
        
        # Save to DB memory
        MemoryEngine.save_message(db, st.session_state.session_id, "user", user_query, language=lang)
        
        with st.spinner("Analyzing groundwater records..."):
            try:
                # Prepare Agent Graph input
                state_input = {
                    "session_id": st.session_state.session_id,
                    "query": user_query,
                    "original_query": user_query,
                    "language": lang,
                    "intent": "knowledge",
                    "resolved_location": None,
                    "resolved_location_type": None,
                    "resolved_year": None,
                    "context_data": None,
                    "context_knowledge": None,
                    "context_prediction": None,
                    "context_simulation": None,
                    "context_recommendations": None,
                    "context_analytics": None,
                    "chart_paths": [],
                    "map_html": None,
                    "pdf_report_path": None,
                    "routing_history": [],
                    "current_node": "supervisor",
                    "response": "",
                    "confidence_score": 0.0,
                    "confidence_reason": "",
                    "citations": [],
                    "evaluation": None
                }
                
                # Execute multi-agent Graph pipeline
                result = agent_graph.invoke(state_input)
                
                # Fetch output parameters
                response = result["response"]
                conf_score = result["confidence_score"]
                conf_reason = result["confidence_reason"]
                map_html = result["map_html"]
                chart_paths = result["chart_paths"]
                pdf_path = result["pdf_report_path"]
                citations = result["citations"]
                
                # Display assistant response
                st.markdown(f'<div class="chat-bubble-assistant">{response}</div>', unsafe_allowed_html=True)
                
                # Save assistant output to database memory
                MemoryEngine.save_message(
                    db, 
                    st.session_state.session_id, 
                    "assistant", 
                    response,
                    language=lang,
                    confidence_score=conf_score,
                    confidence_reason=conf_reason,
                    agent_routing=result["routing_history"],
                    citations=citations
                )
                
                # Save visual states in Streamlit session state
                if map_html:
                    st.session_state.active_map = map_html
                if chart_paths:
                    st.session_state.active_charts = chart_paths
                if pdf_path:
                    st.session_state.pdf_reports.append(pdf_path)
                    
                # Rerun to refresh message bubbles, sidebar downloads, and visualization tabs
                st.rerun()
                
            except Exception as e:
                logger.error(f"Error executing agent graph workflow: {e}", exc_info=True)
                st.error(f"Execution Error: {e}")

# ----------------- TAB 2: VISUALIZATIONS -----------------
with tab2:
    st.header("Interactive Hydrology & GIS Analytics")
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.subheader("Groundwater Stress & Aquifer Map")
        if st.session_state.active_map:
            st.components.v1.html(st.session_state.active_map, height=500, scrolling=True)
        else:
            # Render a default map of Tamil Nadu centered if nothing is active
            m = folium.Map(location=[11.1271, 78.6569], zoom_start=7)
            map_html = m._repr_html_()
            st.components.v1.html(map_html, height=500)
            
    with col2:
        st.subheader("Recharge & Trend Analysis")
        if st.session_state.active_charts:
            for cpath in st.session_state.active_charts:
                if os.path.exists(cpath):
                    st.image(cpath, use_container_width=True)
        else:
            st.info("No comparative trend charts compiled for this session yet. Ask comparative or statistical queries to generate graphs.")

# ----------------- TAB 3: EXPERT INGESTION PANEL -----------------
with tab3:
    st.header(trans["expert_tab"])
    st.write(trans["upload_label"])
    
    uploaded_file = st.file_uploader("Select PDF, CSV, or Excel GEC reports:", type=["pdf", "csv", "xlsx", "xls"])
    
    if uploaded_file:
        filename = uploaded_file.name
        st.write(f"Selected file: `{filename}`")
        
        if st.button(trans["upload_btn"]):
            # Save uploaded file to workspace temp upload folder
            upload_dir = Config.BASE_DIR / "uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            filepath = upload_dir / filename
            with open(filepath, "wb") as f:
                f.write(uploaded_file.getbuffer())
                
            st.success(f"File uploaded successfully to {filepath}")
            
            with st.spinner("Ingesting file, validating schema, generating embeddings, and updating FAISS search index..."):
                try:
                    pipeline = IngestionPipeline(db)
                    result_count = pipeline.ingest_file(str(filepath), force=True)
                    
                    if result_count == "duplicate":
                        st.warning("This file checksum matches an existing dataset in manifest.json. Ingestion skipped.")
                    else:
                        st.balloons()
                        st.success(f"Ingestion Complete! Processed {result_count} records/text chunks successfully.")
                except Exception as e:
                    st.error(f"Failed to ingest file: {e}")
                    
db.close()
