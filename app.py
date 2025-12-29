import sys
import os
import uuid
import time
from io import StringIO
from dotenv import load_dotenv
import streamlit as st

# Load Environment Variables
load_dotenv()

# Compatibility fix for some environments
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

# Import Workflow
from workflow import app_graph, KnowledgeDomain


# Import File Ops
try:
    from file_ops import read_pdf_content
except ImportError:
    read_pdf_content = None

# ===========================
#  Page Configuration
# ===========================
st.set_page_config(
    page_title="InfoPrism Chat",
    page_icon="💠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS: Keep the original Gradient Styling ---
st.markdown("""
    <style>
    /* Hide default top padding */
    .block-container {
        padding-top: 2rem;
    }
    /* Gradient Button Styling */
    button[kind="primary"] {
        background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%);
        border: none;
        color: white;
        font-weight: bold;
        transition: all 0.3s;
    }
    button[kind="primary"]:hover {
        box-shadow: 0 4px 15px rgba(0, 242, 254, 0.4);
        transform: translateY(-2px);
    }
    /* Chat Bubble Styling */
    .stChatMessage {
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 0.5rem;
    }
    </style>
    """, unsafe_allow_html=True)

# ===========================
#  State Init
# ===========================
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "👋 **Hello! I'm InfoPrism, your AI Second Brain.**\n\nYou can **paste an article** to save it, or **ask a question** to query your knowledge base.\n\n*(PDF upload is available in the sidebar)*"}
    ]

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = str(uuid.uuid4())

if "graph_state" not in st.session_state:
    st.session_state["graph_state"] = "IDLE"  # IDLE, RUNNING, PAUSED

if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

# ===========================
#  Sidebar (Config & Upload)
# ===========================
with st.sidebar:
    st.markdown(
        """
        <h1 style='text-align: left; font-family: sans-serif; font-weight: 800; margin-bottom: 5px;'>
            <span style='font-size: 32px;'>💠</span>
            <span style='font-size: 30px; background: linear-gradient(to right, #4facfe 0%, #00f2fe 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
                InfoPrism
            </span>
        </h1>
        <p style='font-size: 16px; color: #666; margin-bottom: 20px;'>
            Your Personal AI Second Brain
        </p>
        """, unsafe_allow_html=True
    )
    st.caption("Knowledge Graph Agent")
    
    st.divider()
    
    # File Uploader
    st.markdown("### 📎 Attachments")
    uploaded_file = st.file_uploader(
        "Upload PDF (Context for current chat)", 
        type=["pdf"], 
        key=f"uploader_{st.session_state['uploader_key']}"
    )
    
    st.divider()
    
    # Reset Button
    if st.button("🗑️ Clear Chat & Reset", use_container_width=True):
        # Keep the welcome message
        st.session_state["messages"] = [st.session_state["messages"][0]] 
        st.session_state["thread_id"] = str(uuid.uuid4())
        st.session_state["graph_state"] = "IDLE"
        st.session_state["uploader_key"] += 1
        st.rerun()

# ===========================
#  Chat Interface Logic
# ===========================

# 1. Display Chat History
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 2. Handle Graph PAUSED State (Review Card)
# This card appears below history when the graph pauses for human review
if st.session_state["graph_state"] == "PAUSED":
    config = {"configurable": {"thread_id": st.session_state["thread_id"]}}
    snapshot = app_graph.get_state(config)
    
    # Get Draft Data
    current_draft = snapshot.values.get("draft", {})
    raw_domain = snapshot.values.get("knowledge_domain", "tech_knowledge")
    current_domain_val = raw_domain.value if hasattr(raw_domain, 'value') else str(raw_domain)

    # Display Review Card in Assistant Stream
    with st.chat_message("assistant"):
        st.info("✋ **Draft generated. Please review before publishing:**")
        
        with st.container(border=True):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                new_title = st.text_input("Title", value=current_draft.get("title", ""))
                new_summary = st.text_area("Summary", value=current_draft.get("summary", ""), height=100)
                with st.expander("📄 Preview Markdown Content"):
                    st.markdown(current_draft.get("markdown_body", ""))
            
            with col2:
                domain_options = ["tech_knowledge", "humanities", "spanish_learning"]
                try: default_idx = domain_options.index(current_domain_val)
                except: default_idx = 0
                
                selected_db = st.selectbox(
                    "Target Database", 
                    options=domain_options, 
                    index=default_idx,
                    format_func=lambda x: x.replace("_", " ").title()
                )
                st.caption(f"Detected Intent: {snapshot.values.get('intent_type', 'Unknown')}")

            btn_col1, btn_col2 = st.columns(2)
            
            # --- Approve Button ---
            if btn_col1.button("✅ Confirm & Publish", type="primary", use_container_width=True):
                # 1. Update State
                current_draft["title"] = new_title
                current_draft["summary"] = new_summary
                
                db_id_map = {
                    "tech_knowledge": os.environ.get("NOTION_DATABASE_ID_TECH"),
                    "humanities": os.environ.get("NOTION_DATABASE_ID_HUMANITIES"),
                    "spanish_learning": os.environ.get("NOTION_DATABASE_ID") 
                }
                
                app_graph.update_state(
                    config, 
                    {
                        "draft": current_draft, 
                        "knowledge_domain": selected_db, 
                        "override_database_id": db_id_map.get(selected_db)
                    }
                )
                
                # 2. Resume Graph Execution
                with st.status("🚀 Writing to Notion...", expanded=True) as status:
                    final_output = None
                    for event in app_graph.stream(None, config, stream_mode="values"):
                        if "final_output" in event:
                            final_output = event["final_output"]
                    status.update(label="✅ Published successfully!", state="complete", expanded=False)
                
                # 3. Append Success Message
                success_msg = f"✅ **Note Published!**\n\n📄 **{new_title}**\n📚 Database: `{selected_db}`\n\n{final_output}"
                st.session_state["messages"].append({"role": "assistant", "content": success_msg})
                
                # 4. Reset State
                st.session_state["graph_state"] = "IDLE"
                st.session_state["thread_id"] = str(uuid.uuid4()) # New thread for next turn
                st.rerun()

            # --- Reject Button ---
            if btn_col2.button("❌ Reject / Cancel", use_container_width=True):
                st.session_state["messages"].append({"role": "assistant", "content": "🚫 Operation cancelled."})
                st.session_state["graph_state"] = "IDLE"
                st.session_state["thread_id"] = str(uuid.uuid4())
                st.rerun()

# 3. Handle User Input (Chat Input)
# Only allow input when IDLE to prevent interruption during review
if st.session_state["graph_state"] == "IDLE":
    if prompt := st.chat_input("Type a message or ask a question..."):
        
        # A. Display User Message
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            if uploaded_file:
                st.caption(f"📎 Attached: {uploaded_file.name}")

        # B. Run Graph
        config = {"configurable": {"thread_id": st.session_state["thread_id"]}}
        
        with st.chat_message("assistant"):
            status_container = st.status("🤖 Thinking...", expanded=True)
            
            try:
                # Prepare Input
                raw_text = prompt
                if uploaded_file and read_pdf_content:
                    status_container.write("📂 Parsing PDF...")
                    pdf_text = read_pdf_content(uploaded_file)
                    raw_text = f"User Query: {prompt}\n\nPDF Content:\n{pdf_text}"
                
                initial_state = {
                    "user_input": prompt,
                    "raw_text": raw_text,
                    "original_url": None,
                    "retry_count": 0
                }

                # Stream Graph
                final_output = None
                intent_detected = None
                
                for event in app_graph.stream(initial_state, config, stream_mode="values"):
                    if "intent_type" in event and event["intent_type"]:
                        intent_detected = event["intent_type"]
                        if intent_detected == "query_knowledge":
                            status_container.write("🔍 Intent: **Query Knowledge Base**")
                        elif intent_detected == "save_note":
                            status_container.write("✍️ Intent: **Drafting Note**")
                    
                    if "memory_match" in event and event['memory_match'].get('match'):
                        status_container.write(f"🧠 Memory Recall: Found related note '{event['memory_match'].get('title')}'")
                    
                    if "final_output" in event:
                        final_output = event["final_output"]

                # C. Check Results
                snapshot = app_graph.get_state(config)
                
                # Case 1: Paused (Requires Human Review)
                if snapshot.next and snapshot.next[0] == "publisher":
                    status_container.update(label="🟠 Human Review Required", state="running", expanded=False)
                    st.session_state["graph_state"] = "PAUSED"
                    st.rerun() 
                
                # Case 2: Completed (Query Result)
                elif final_output:
                    status_container.update(label="✅ Completed", state="complete", expanded=False)
                    st.markdown(final_output) # Display result in current bubble
                    st.session_state["messages"].append({"role": "assistant", "content": final_output})
                
                # Case 3: Error/Empty
                else:
                    status_container.update(label="❌ No Output", state="error")
                    st.error("Graph finished without output.")

            except Exception as e:
                status_container.update(label="❌ Execution Error", state="error")
                st.error(f"Error: {e}")