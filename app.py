import sys
import os
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import streamlit as st
import json
import uuid
from io import StringIO

# 导入 LangGraph 构建好的图
from graph_agent import app_graph

# --- Page Configuration ---
st.set_page_config(
    page_title="Second Brain Pipeline",
    page_icon="💠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 🎨 CSS Styles ---
st.markdown("""
    <style>
    /* 按钮样式优化 */
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
    
    /* 垃圾桶按钮 */
    button[kind="secondary"] {
        border: none !important;
        background: transparent !important;
    }
    button[kind="secondary"]:hover {
        color: #ff4b4b !important;
        background: #fff0f0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- State Init ---
if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = str(uuid.uuid4()) # 每个用户唯一的会话 ID

if "graph_state" not in st.session_state:
    st.session_state["graph_state"] = "IDLE" # IDLE, RUNNING, PAUSED, COMPLETED

if "input_area" not in st.session_state: st.session_state["input_area"] = ""
if "uploader_key_id" not in st.session_state: st.session_state["uploader_key_id"] = 0

def clear_inputs():
    st.session_state["input_area"] = ""
    st.session_state["uploader_key_id"] += 1
    st.session_state["graph_state"] = "IDLE"
    st.session_state["thread_id"] = str(uuid.uuid4()) # 重置会话

# ===========================
#  Sidebar
# ===========================
with st.sidebar:
    # 标题
    st.markdown("""
        <h1 style='text-align: left; color: #333; font-size: 20px; font-family: sans-serif; font-weight: 800; margin-bottom: 5px;'>
            <span style='font-size: 24px;'>💠</span> Second Brain Pipeline
        </h1>
        <p style='font-size: 12px; color: #666; margin-bottom: 20px;'>
            Your Personal AI Second Brain
        </p>
        """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])
    with col1: st.header("📥 Input")
    with col2: st.button("🗑️", on_click=clear_inputs)
    
    with st.form(key="input_form"):
        with st.container(border=True):
            dynamic_key = f"file_uploader_{st.session_state['uploader_key_id']}"
            uploaded_file = st.file_uploader("📎 Upload PDF", type=["pdf"], key=dynamic_key)
            user_input = st.text_area("Or paste text/link:", height=150, key="input_area")
        
        # 只有在空闲状态才显示开始按钮
        submit_btn = st.form_submit_button("🚀 Start Workflow", type="primary", use_container_width=True, disabled=(st.session_state["graph_state"] != "IDLE"))

# ===========================
#  Main Interface
# ===========================
if not submit_btn:
    # 默认主图
    if os.path.exists("banner.jpg"):
        st.image("banner.jpg", use_container_width=True) 
    else:
        st.image(
            "https://cdn.pixabay.com/photo/2018/03/19/18/20/tea-time-3240766_1280.jpg",
            caption="“Knowledge is a universe waiting to be explored.”",
            use_container_width=True
        )
    
    st.info("👈 **Start here**: Upload a file or paste content in the sidebar.")

# 配置 LangGraph 的运行参数
config = {"configurable": {"thread_id": st.session_state["thread_id"]}}

# 1. 启动逻辑 (IDLE -> PAUSED)
if submit_btn and st.session_state["graph_state"] == "IDLE":
    if not user_input and not uploaded_file:
        st.warning("⚠️ Please provide input!")
    else:
        st.session_state["graph_state"] = "RUNNING"
        with st.status("🤖 Agent is thinking...", expanded=True) as status:
            st.write("🔵 Creating perceptions...")
            # 初始输入
            initial_state = {
                "user_input": user_input,
                "uploaded_file": uploaded_file
            }
            
            # 运行图，直到断点 (human_review)
            for event in app_graph.stream(initial_state, config, stream_mode="values"):
                # 实时显示当前的 State keys 变化
                if "intent_type" in event:
                    st.write(f"👉 Intent Detected: **{event['intent_type']}**")
                if "memory_match" in event:
                    match = event['memory_match']
                    if match.get('match'):
                        st.write(f"💡 Found existing note: *{match.get('title')}*")
            
            # 检查是否停在了 human_review
            snapshot = app_graph.get_state(config)
            if snapshot.next and snapshot.next[0] == "human_review":
                status.update(label="🟠 Paused for Human Review", state="running", expanded=False)
                st.session_state["graph_state"] = "PAUSED"
                st.rerun() # 刷新页面以显示审核界面

# 2. 暂停/审核界面 (PAUSED -> COMPLETED)
if st.session_state["graph_state"] == "PAUSED":
    st.info("✋ **Human-in-the-loop**: The Agent has drafted a note. Please review and approve.")
    
    # 获取当前的 State 快照
    snapshot = app_graph.get_state(config)
    current_draft = snapshot.values.get("draft", {})
    
    # --- 编辑区域 ---
    with st.container(border=True):
        st.subheader("📝 Draft Preview")
        
        # 让用户可以修改标题和摘要
        new_title = st.text_input("Title", value=current_draft.get("title", ""))
        new_summary = st.text_area("Summary", value=current_draft.get("summary", ""), height=100)
        
        # 显示详细的 JSON 结构 (只读，因为太复杂)
        with st.expander("View Full JSON Blocks"):
            st.json(current_draft)
            
        col_Approve, col_Reject = st.columns([1, 1])
        
        # --- 批准按钮 ---
        if col_Approve.button("✅ Approve & Publish", type="primary", use_container_width=True):
            # 更新 State 中的 draft
            current_draft["title"] = new_title
            current_draft["summary"] = new_summary
            
            # 更新图的状态
            app_graph.update_state(config, {"draft": current_draft})
            
            # 继续运行 (Resume)
            with st.status("🚀 Publishing to Notion...", expanded=True) as status:
                # 传入 None 表示从断点继续
                for event in app_graph.stream(None, config, stream_mode="values"):
                     if "final_output" in event:
                         st.write(event["final_output"])
                
                status.update(label="✅ Workflow Completed!", state="complete", expanded=False)
                st.session_state["graph_state"] = "COMPLETED"
                st.balloons()
                st.success("🎉 Knowledge successfully saved to Notion!")
                
        # --- 拒绝按钮 ---
        if col_Reject.button("❌ Reject & Reset", use_container_width=True):
            clear_inputs()
            st.rerun()

# 3. 完成状态
if st.session_state["graph_state"] == "COMPLETED":
    if st.button("Start New Task"):
        clear_inputs()
        st.rerun()