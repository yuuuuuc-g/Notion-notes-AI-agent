import sys
import os
import uuid
from io import StringIO
from dotenv import load_dotenv # 确保能读取 env


# 加载环境变量
load_dotenv()

try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import streamlit as st

# 导入 LangGraph
from graph_agent import app_graph, KnowledgeDomain
# 🌟 导入文件处理工具
try:
    from file_ops import read_pdf_content
except ImportError:
    read_pdf_content = None

# --- Page Configuration ---
st.set_page_config(
    page_title="InfoPrism",
    page_icon="💠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS Styles ---
st.markdown("""
    <style>
    button[kind="primary"], button[kind="primaryFormSubmit"] {
        background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%) !important;
        border: none !important;
        color: white !important;
        font-weight: bold !important;
    }
    button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover {
        box-shadow: 0 4px 15px rgba(0, 242, 254, 0.4) !important;
        transform: translateY(-2px);
    }
    </style>
    """, unsafe_allow_html=True)

# --- State Init ---
if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = str(uuid.uuid4()) 

if "graph_state" not in st.session_state:
    st.session_state["graph_state"] = "IDLE" 

if "input_area" not in st.session_state: st.session_state["input_area"] = ""
if "uploader_key_id" not in st.session_state: st.session_state["uploader_key_id"] = 0

# --- Helper: Hard Reset ---
def reset_pipeline():
    """彻底重置所有状态，为新任务做准备"""
    st.session_state["graph_state"] = "IDLE"
    st.session_state["thread_id"] = str(uuid.uuid4()) # 🟢 关键：生成新 ID，隔离记忆
    st.session_state["uploader_key_id"] += 1
    # 清空可能残留的 session 数据
    for key in ["input_area"]:
        if key in st.session_state:
            del st.session_state[key]

# ===========================
#  Sidebar
# ===========================
with st.sidebar:
    st.markdown("""
        <h1 style='text-align: left; font-family: sans-serif; font-weight: 800; margin-bottom: 5px;'>
            <span style='font-size: 34px;'>💠</span>
            <span style='font-size: 30px; background: linear-gradient(to right, #4facfe 0%, #00f2fe 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
                InfoPrism
            </span>
        </h1>
        <p style='font-size: 16px; color: #666; margin-bottom: 20px;'>
            Your Personal AI Second Brain
        </p>
        """, unsafe_allow_html=True)

    col1, col2 = st.columns([4, 1])
    with col1: st.markdown("**📥 Input Zone**")
    with col2: st.button("🗑️", on_click=reset_pipeline, help="Clear all inputs")
    
    with st.form(key="input_form"):
        with st.container(border=True):
            dynamic_key = f"file_uploader_{st.session_state['uploader_key_id']}"
            uploaded_file = st.file_uploader("📎 Upload PDF", type=["pdf"], key=dynamic_key)
            user_input = st.text_area("Paste article content here (No URLs):", height=150, key="input_area")
        
        submit_btn = st.form_submit_button("🚀 Start Processing", type="primary", use_container_width=True, disabled=(st.session_state["graph_state"] != "IDLE"))

# ===========================
#  Main Interface
# ===========================

# 🟢 配置 Config (每次都用当前的 thread_id)
config = {"configurable": {"thread_id": st.session_state["thread_id"]}}

if not submit_btn and st.session_state["graph_state"] == "IDLE":
    if os.path.exists("banner.jpg"):
        st.image("banner.jpg", use_container_width=True) 
    else:
        st.info("👈 **Start here**: Upload a file or paste content in the sidebar.")

# 1. 启动逻辑
if submit_btn and st.session_state["graph_state"] == "IDLE":
    if not user_input and not uploaded_file:
        st.warning("⚠️ Please provide input!")
    else:
        # 🟢 核心修复 1：每次点击开始，强制生成新线程 ID，防止读取旧缓存
        st.session_state["thread_id"] = str(uuid.uuid4())
        config = {"configurable": {"thread_id": st.session_state["thread_id"]}}
        
        st.session_state["graph_state"] = "RUNNING"
        
        with st.status("🌌 Navigating the cosmos of knowledge...", expanded=True) as status:
            old_stdout = sys.stdout
            result_buffer = StringIO()
            log_placeholder = st.empty()
            
            class StreamlitLogger:
                def write(self, msg):
                    if msg.strip():
                        result_buffer.write(msg + "\n")
                        log_placeholder.markdown(f"```text\n{result_buffer.getvalue()}\n```")
                def flush(self): pass
            sys.stdout = StreamlitLogger()
            
            try:
                pre_processed_text = ""
                original_source = None
                
                if uploaded_file:
                    st.write("📂 Reading PDF file...")
                    if read_pdf_content:
                        pre_processed_text = read_pdf_content(uploaded_file)
                        original_source = uploaded_file.name
                    else:
                        raise Exception("file_ops module missing.")
                
                elif user_input:
                    # 🟢 修改点：不再检查 http，直接把输入当成正文
                    st.write("📝 Processing pasted text...")
                    pre_processed_text = user_input
                    original_source = "User Pasted Text"

                # 构造初始状态
                initial_state = {
                    "raw_text": pre_processed_text,
                    "original_url": None, # URL 来源彻底置空
                    "retry_count": 0
                }
                
                # Stream Graph
                for event in app_graph.stream(initial_state, config, stream_mode="values"):
                    if "intent_type" in event:
                        st.write(f"👉 Intent Detected: **{event['intent_type']}**")
                    if "memory_match" in event and event['memory_match'].get('match'):
                        st.write(f"💡 Memory Hit: *{event['memory_match'].get('title')}*")

                # Check Snapshot for Pause
                snapshot = app_graph.get_state(config)
                if snapshot.next and snapshot.next[0] == "human_review":
                    status.update(label="🟠 Paused for Human Review", state="running", expanded=False)
                    st.session_state["graph_state"] = "PAUSED"
                    st.rerun()

            except Exception as e:
                status.update(label="❌ Mission Failed", state="error")
                st.error(f"Runtime Error: {str(e)}")
            finally:
                sys.stdout = old_stdout

# 2. 审核界面
if st.session_state["graph_state"] == "PAUSED":
    st.info("✋ **Human-in-the-loop**: Please review the draft.")
    snapshot = app_graph.get_state(config)
    current_draft = snapshot.values.get("draft", {})
    current_domain = snapshot.values.get("knowledge_domain", "tech_knowledge")
    
    with st.container(border=True):
        st.subheader("📝 Draft Preview")
        new_title = st.text_input("Title", value=current_draft.get("title", ""))
        new_summary = st.text_area("Summary", value=current_draft.get("summary", ""), height=100)
        
        # 🟢 数据库选项映射
        domain_options = [d.value for d in KnowledgeDomain]
        
        # 获取当前默认值
        try:
            current_val = current_domain.value if hasattr(current_domain, 'value') else current_domain
            default_index = domain_options.index(current_val)
        except: 
            default_index = 0
            
        selected_db_name = st.selectbox(
            "📚 Target Database", 
            options=domain_options, 
            index=default_index, 
            format_func=lambda x: x.replace("_", " ").title()
        )
        
        with st.expander("View JSON Blocks"): st.json(current_draft)
            
        col1, col2 = st.columns([1, 1])
        if col1.button("✅ Approve & Publish", type="primary", use_container_width=True):
            current_draft["title"] = new_title
            current_draft["summary"] = new_summary
            
            # 🟢 核心修复 2：将 UI 选择映射为真实 Database ID
            db_id_map = {
                "tech_knowledge": os.environ.get("NOTION_DATABASE_ID_TECH"),
                "humanities": os.environ.get("NOTION_DATABASE_ID_HUMANITIES"),
                "spanish_learning": os.environ.get("NOTION_DATABASE_ID") # 假设西班牙语是默认ID
            }
            target_db_id = db_id_map.get(selected_db_name)

            # 更新状态，并显式传入 override_database_id
            app_graph.update_state(
                config, 
                {
                    "draft": current_draft, 
                    "knowledge_domain": KnowledgeDomain(selected_db_name),
                    "override_database_id": target_db_id  # 👈 这里必须传 ID，不能是 None
                }
            )
            
            with st.status("🚀 Publishing...", expanded=True) as status:
                for event in app_graph.stream(None, config, stream_mode="values"):
                     if "final_output" in event: st.write(event["final_output"])
                status.update(label="✅ Workflow Completed!", state="complete", expanded=False)
                st.session_state["graph_state"] = "COMPLETED"
                st.balloons()
                st.success(f"🎉 Saved to Notion! (DB: {selected_db_name})")
                
        if col2.button("❌ Reject & Reset", use_container_width=True):
            reset_pipeline()
            st.rerun()

# 3. 完成状态
if st.session_state["graph_state"] == "COMPLETED":
    if st.button("Start New Task", type="primary"):
        reset_pipeline()
        st.rerun()