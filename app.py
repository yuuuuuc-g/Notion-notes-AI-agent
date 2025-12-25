import sys
import os
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import streamlit as st
import uuid
from io import StringIO

# 🌟 导入 LangGraph 的图对象和枚举
from graph_agent import app_graph, KnowledgeDomain

# --- Page Configuration ---
st.set_page_config(
    page_title="Second Brain Pipeline",
    page_icon="💠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS Styles ---
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
    st.session_state["thread_id"] = str(uuid.uuid4()) # 每个任务唯一的会话 ID

if "graph_state" not in st.session_state:
    st.session_state["graph_state"] = "IDLE" # IDLE, RUNNING, PAUSED, COMPLETED

if "input_area" not in st.session_state: st.session_state["input_area"] = ""
if "uploader_key_id" not in st.session_state: st.session_state["uploader_key_id"] = 0

def clear_inputs():
    st.session_state["input_area"] = ""
    st.session_state["uploader_key_id"] += 1
    st.session_state["graph_state"] = "IDLE"
    st.session_state["thread_id"] = str(uuid.uuid4()) # 重置 Session ID

# ===========================
#  Sidebar
# ===========================
with st.sidebar:
    st.markdown("""
        <h1 style='text-align: left; color: #333; font-size: 20px; font-family: sans-serif; font-weight: 800;'>
            <span style='font-size: 24px;'>💠</span> Second Brain Pipeline
        </h1>
        <p style='font-size: 12px; color: #666;'>Powered by LangGraph</p>
        """, unsafe_allow_html=True)
    st.divider()

    col1, col2 = st.columns([3, 1])
    with col1: st.header("📥 Input")
    with col2: st.button("🗑️", on_click=clear_inputs)
    
    with st.form(key="input_form"):
        with st.container(border=True):
            dynamic_key = f"file_uploader_{st.session_state['uploader_key_id']}"
            uploaded_file = st.file_uploader("📎 Upload PDF", type=["pdf"], key=dynamic_key)
            user_input = st.text_area("Or paste text/link:", height=150, key="input_area")
        
        # 只有在空闲状态才允许点击开始
        submit_btn = st.form_submit_button(
            "🚀 Start Workflow", 
            type="primary", 
            use_container_width=True, 
            disabled=(st.session_state["graph_state"] != "IDLE")
        )

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
    
# 配置 LangGraph 的运行参数 (通过 thread_id 记忆上下文)
config = {"configurable": {"thread_id": st.session_state["thread_id"]}}

# --- 阶段 1: 启动逻辑 (从 IDLE 到 PAUSED) ---
if submit_btn and st.session_state["graph_state"] == "IDLE":
    if not user_input and not uploaded_file:
        st.warning("⚠️ Please provide input!")
    else:
        st.session_state["graph_state"] = "RUNNING"
        
        with st.status("🤖 Agent is thinking...", expanded=True) as status:
            st.write("🔵 Initializing Perception...")
            
            # 初始状态输入
            initial_state = {
                "user_input": user_input,
                "uploaded_file": uploaded_file,
                "retry_count": 0
            }
            
            # 运行图！(Stream 模式可以看到每个节点的输出)
            # 这里的 stream_mode="values" 会返回每个步骤更新后的 state
            current_step = "Starting"
            
            for event in app_graph.stream(initial_state, config, stream_mode="values"):
                # 根据 state 的变化显示日志
                if "intent_type" in event:
                    intent = event['intent_type']
                    if current_step != intent:
                        st.write(f"👉 Intent Detected: **{intent}**")
                        current_step = intent
                
                if "memory_match" in event and event['memory_match'].get('match'):
                    st.write(f"💡 Memory Hit: *{event['memory_match'].get('title')}*")

                if "error_message" in event and event['error_message']:
                    st.error(f"❌ Validation failed: {event['error_message']} (Retrying...)")

            # 运行结束后，检查是否停在了 'human_review' 断点
            snapshot = app_graph.get_state(config)
            if snapshot.next and snapshot.next[0] == "human_review":
                status.update(label="🟠 Paused for Human Review", state="running", expanded=False)
                st.session_state["graph_state"] = "PAUSED"
                st.rerun() # 强制刷新页面，进入审核界面

# --- 阶段 2: 暂停/审核界面 (从 PAUSED 到 COMPLETED) ---
if st.session_state["graph_state"] == "PAUSED":
    st.info("✋ **Human-in-the-loop**: The Agent has drafted a note. Please review and approve.")
    
    # 获取当前的 State 快照 (Memory)
    snapshot = app_graph.get_state(config)
    current_draft = snapshot.values.get("draft", {})
    current_domain = snapshot.values.get("knowledge_domain", "tech_knowledge")
    
    # --- 编辑区域 ---
    with st.container(border=True):
        st.subheader("📝 Draft Preview")
        
        # 让用户可以修改标题和摘要
        new_title = st.text_input("Title", value=current_draft.get("title", ""))
        new_summary = st.text_area("Summary", value=current_draft.get("summary", ""), height=100)
        
        # 允许用户手动修正数据库分类
        # 这里的 options 来自 graph_agent.py 里的 KnowledgeDomain 枚举
        domain_options = [d.value for d in KnowledgeDomain]
        try:
            default_index = domain_options.index(current_domain.value if hasattr(current_domain, 'value') else current_domain)
        except:
            default_index = 0
            
        selected_db = st.selectbox(
            "📚 Target Database",
            options=domain_options,
            index=default_index,
            format_func=lambda x: x.replace("_", " ").title()
        )
        
        # 显示详细 JSON (只读)
        with st.expander("View Full Blocks JSON"):
            st.json(current_draft)
            
        col_Approve, col_Reject = st.columns([1, 1])
        
        # [A] 批准按钮
        if col_Approve.button("✅ Approve & Publish", type="primary", use_container_width=True):
            # 1. 更新 State (把用户的修改写回内存)
            current_draft["title"] = new_title
            current_draft["summary"] = new_summary
            
            # 这里不仅更新 draft，还允许更新 knowledge_domain (从而改变写入的数据库)
            # update_state 会把这些字段 merge 到当前的 state 里
            app_graph.update_state(config, {
                "draft": current_draft,
                "knowledge_domain": KnowledgeDomain(selected_db)
            })
            
            # 2. 继续运行 (Resume from 'human_review')
            # 传入 None 表示不输入新数据，只继续执行后续节点 (publisher)
            with st.status("🚀 Publishing to Notion...", expanded=True) as status:
                for event in app_graph.stream(None, config, stream_mode="values"):
                     if "final_output" in event and event["final_output"]:
                         st.write(event["final_output"])
                
                status.update(label="✅ Workflow Completed!", state="complete", expanded=False)
                st.session_state["graph_state"] = "COMPLETED"
                st.balloons()
                st.success("🎉 Knowledge successfully saved to Notion!")
                
        # [B] 拒绝按钮
        if col_Reject.button("❌ Reject & Reset", use_container_width=True):
            clear_inputs()
            st.rerun()

# --- 阶段 3: 完成状态 ---
if st.session_state["graph_state"] == "COMPLETED":
    if st.button("Start New Task"):
        clear_inputs()
        st.rerun()