import streamlit as st
import pandas as pd
import os
import json
import csv
from datetime import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from agent import SQLQueryAgent
from visualizer import ResultVisualizer
from setup_db import create_sample_database

load_dotenv()

# Page configuration for a professional look
st.set_page_config(
    page_title="Daniel SQL AI | Agentic Data Intel",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Deep Premium CSS Design System
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        --primary: #00f2ff;
        --secondary: #7000ff;
        --background: #0a0b10;
        --surface: #161821;
        --text: #e2e8f0;
    }

    .main {
        background-color: var(--background);
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: radial-gradient(circle at 50% 0%, #1a1c2c 0%, #0a0b10 100%);
    }

    [data-testid="stSidebar"] {
        background-color: rgba(22, 24, 33, 0.95);
        border-right: 1px solid rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
    }

    h1, h2, h3 {
        font-family: 'Inter', sans-serif;
        font-weight: 700 !important;
        letter-spacing: -0.02em;
        background: linear-gradient(90deg, #fff 0%, #a5b4fc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .query-box {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        transition: all 0.3s ease;
    }

    .query-box:hover {
        border-color: var(--primary);
        box-shadow: 0 0 20px rgba(0, 242, 255, 0.1);
    }

    .stButton > button {
        background: linear-gradient(135deg, var(--secondary) 0%, #4a00ff 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.6rem 1.5rem !important;
        font-weight: 600 !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 15px rgba(112, 0, 255, 0.3) !important;
    }

    .stButton > button:hover {
        transform: translateY(-2px) scale(1.02) !important;
        box-shadow: 0 6px 20px rgba(112, 0, 255, 0.4) !important;
        background: linear-gradient(135deg, #8a2be2 0%, #5d00ff 100%) !important;
    }

    .stDataFrame {
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        overflow: hidden;
    }

    .stAlert {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        color: var(--text) !important;
        backdrop-filter: blur(5px);
    }

    .stSpinner > div {
        border-top-color: var(--primary) !important;
    }

    code {
        font-family: 'JetBrains Mono', monospace !important;
        background-color: #1e1e2e !important;
        color: #f8f8f2 !important;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .result-container {
        animation: fadeIn 0.5s ease-out forwards;
    }
</style>
""", unsafe_allow_html=True)

# Database Selection Logic (Strategic Improvement #1 - PostgreSQL Ready)
DB_TYPE = os.getenv("DATABASE_TYPE", "sqlite")
if DB_TYPE == "postgresql":
    DB_URI = os.getenv("POSTGRES_DB_URL")
    ENGINE_LABEL = "PostgreSQL Engine: Connected"
else:
    DB_PATH = "ecommerce.db"
    DB_URI = f"sqlite:///{DB_PATH}"
    ENGINE_LABEL = "SQLite Engine: Connected"
    if not os.path.exists(DB_PATH):
        with st.status("🏗️ Initializing Intelligence Layer...", expanded=True) as status:
            create_sample_database(DB_PATH)
            status.update(label="✅ Knowledge Base Ready", state="complete", expanded=False)

# Agent Singleton
@st.cache_resource
def get_agent():
    return SQLQueryAgent(DB_URI)

try:
    agent = get_agent()
except Exception as e:
    st.error(f"🚨 System Breach/Config Error: {e}")
    st.info("💡 Action Required: Validate API keys in .env environment.")
    st.stop()

# Result Caching for High Performance
@st.cache_data(show_spinner=False, ttl=3600)
def cached_query(question: str):
    return agent.query(question)

# Intelligence Feedback Persistence (Strategic Improvement #2)
def log_feedback(question, sql, answer, feedback):
    file_exists = os.path.isfile('evaluations.csv')
    with open('evaluations.csv', mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['Timestamp', 'Question', 'SQL', 'Answer', 'Feedback'])
        writer.writerow([datetime.now(), question, sql, answer, feedback])

# --- SIDEBAR: Control Center ---
with st.sidebar:
    logo_svg = """
    <svg width="60" height="60" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="#00f2ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M2 17L12 22L22 17" stroke="#7000ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M2 12L12 17L22 12" stroke="#00f2ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    """
    st.markdown(logo_svg, unsafe_allow_html=True)
    st.title("Daniel Control")
    st.markdown("*Advanced Agentic SQL Interface*")
    st.markdown("---")

    if hasattr(agent, 'history') and agent.history:
        st.markdown("### 🧠 Intelligence History")
        for i, entry in enumerate(reversed(agent.history)):
            curr_q = entry['q']
            if st.button(f"Re-run: {curr_q[:25]}...", key=f"hist_{i}", use_container_width=True):
                st.session_state.question = curr_q
                st.rerun()
        st.markdown("---")
    
    with st.expander("🛠️ System Ops", expanded=False):
        if st.button("🔄 Hard Reset Protocol", use_container_width=True):
            if DB_TYPE == "sqlite":
                create_sample_database(DB_PATH)
                st.toast("Database reconstructed from genesis.")
                st.rerun()
            else:
                st.warning("Hard Reset not supported for PostgreSQL via UI.")

    st.markdown("### 🔦 Discovery Hub")
    examples = [
        ("📈 Monthly Revenue Trend", "Show me total sales (total_amount) by month for the last 6 months."),
        ("🌐 Regional Performance", "What is the total revenue per country?"),
        ("👑 VIP Customers", "Who are the top 5 customers by total spending?"),
        ("📦 Inventory Health", "Which product categories have the highest and lowest average prices?"),
        ("🚛 Order Logistics", "List the 10 most recent orders with customer name and product details.")
    ]
    
    for label, q_text in examples:
        if st.button(label, use_container_width=True):
            st.session_state.question = q_text

    st.markdown("---")
    st.markdown("### 📡 Node Status")
    st.success("DeepSeek-V3: Online")
    st.success(ENGINE_LABEL)
    if DB_TYPE == "postgresql":
        st.info("Security: Row-Level Active")
    st.info("Schema Cache: Active")

# --- MAIN UI: Intelligence Interface ---
header_col1, header_col2 = st.columns([0.8, 0.2])
with header_col1:
    st.title("💎 Daniel Data Intelligence")
    st.markdown("#### Autonomous Semantic Data Layer")
with header_col2:
    st.markdown("<br>", unsafe_allow_html=True)
    st.button("📄 Export Report", disabled=True)

with st.container():
    st.markdown('<div class="query-box">', unsafe_allow_html=True)
    
    if "question" not in st.session_state:
        st.session_state.question = ""

    user_q = st.text_area(
        "Enter your query in natural language",
        value=st.session_state.question,
        placeholder="e.g., 'Compare average order value between USA and UK'...",
        height=100,
        key="main_input"
    )
    
    col_run, col_clear, _ = st.columns([0.15, 0.15, 0.7])
    with col_run:
        run_query = st.button("⚡ EXECUTE", type="primary", use_container_width=True)
    with col_clear:
        if st.button("🧹 CLEAR", use_container_width=True):
            st.session_state.question = ""
            st.rerun()
            
    st.markdown('</div>', unsafe_allow_html=True)

if run_query and user_q:
    with st.spinner("🤖 Daniel Agent is thinking..."):
        result = cached_query(user_q)
        
        if result["success"]:
            st.markdown('<div class="result-container">', unsafe_allow_html=True)
            
            tab1, tab2, tab3 = st.tabs(["📊 Analytics", "📋 Source Data", "🧠 Neural Logic"])
            
            # --- Tab 1: Analytics & Insights ---
            with tab1:
                st.markdown("### 💡 Executive Summary")
                st.write(result["answer"])
                
                # Feedback System (Strategic Improvement #2)
                st.markdown("---")
                f_col1, f_col2, f_col3 = st.columns([0.2, 0.2, 0.6])
                with f_col1:
                    if st.button("👍 Correct"):
                        log_feedback(user_q, "N/A", result["answer"], "Correct")
                        st.success("Log saved!")
                with f_col2:
                    if st.button("👎 Incorrect"):
                        log_feedback(user_q, "N/A", result["answer"], "Incorrect")
                        st.error("Log saved!")
                st.markdown("---")

                last_sql = ""
                for action, _ in reversed(result["steps"]):
                    if hasattr(action, 'tool_input') and isinstance(action.tool_input, str) and "SELECT" in action.tool_input.upper():
                        last_sql = action.tool_input
                        break
                    elif hasattr(action, 'tool_input') and isinstance(action.tool_input, dict) and 'query' in action.tool_input:
                        last_sql = action.tool_input['query']
                        break
                
                if last_sql:
                    try:
                        engine = create_engine(DB_URI)
                        with engine.connect() as conn:
                            df = pd.read_sql(text(last_sql), conn)
                            if not df.empty:
                                fig = ResultVisualizer.auto_visualize(df, title=f"Visual Analysis: {user_q[:30]}...")
                                if fig:
                                    st.plotly_chart(fig, use_container_width=True, theme="streamlit")
                                st.markdown("#### 📝 Key Metrics")
                                st.code(ResultVisualizer.get_summary_stats(df), language="text")
                    except Exception as e:
                        st.caption(f"Visual layer skip: {e}")

            with tab2:
                if 'df' in locals() and not df.empty:
                    st.markdown("### 📥 Underlying Dataset")
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No structured data returned for this semantic query.")

            with tab3:
                st.markdown("### ⛓️ Chain of Thought")
                for i, (action, observation) in enumerate(result["steps"]):
                    with st.expander(f"Step {i+1}: AI Strategic Action", expanded=(i == len(result["steps"])-1)):
                        st.markdown("**Strategic Intent:**")
                        try:
                            st.json(action.to_json())
                        except:
                            st.code(str(action))
                        st.markdown("**Field Observation:**")
                        st.code(observation, language="sql" if "SELECT" in observation.upper() else "text")

            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.error(f"🚫 Analysis Pipeline Interrupted: {result['error']}")

st.markdown("<br><br>", unsafe_allow_html=True)
footer_col1, footer_col2, footer_col3 = st.columns(3)
with footer_col2:
    st.markdown("""
        <div style="text-align: center; color: #64748b; font-size: 0.8rem;">
            <b>Daniel SQL AI v1.0</b><br>
            Enterprise Grade AI Data Interface<br>
            © 2026 Daniel Lopez
        </div>
    """, unsafe_allow_html=True)
