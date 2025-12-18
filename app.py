import streamlit as st
import sys
import os
from io import StringIO
from main import main_workflow

# --- Page Configuration ---
st.set_page_config(
    page_title="AI Knowledge Agent",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 🎨 CSS Styles ---
st.markdown("""
    <style>
    /* 按钮样式 */
    button[kind="primary"] {
        background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%) !important;
        border: none !important;
    }
    button[kind="primaryFormSubmit"] {
        background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%) !important;
        border: none !important;
    }
    section[data-testid="stSidebar"] button {
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    /* 悬停效果 */
    button[kind="primary"]:hover, 
    button[kind="primaryFormSubmit"]:hover {
        box-shadow: 0 4px 15px rgba(0, 242, 254, 0.4) !important;
        transform: translateY(-2px);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 🛠️ 状态初始化 (State Init) ---
if "input_area" not in st.session_state:
    st.session_state["input_area"] = ""

# 核心修改：使用计数器来控制 File Uploader 的重置
if "uploader_key_id" not in st.session_state:
    st.session_state["uploader_key_id"] = 0

# --- 🧹 清除功能的逻辑 (Key Rotation) ---
def clear_inputs():
    # 1. 清空文本框
    st.session_state["input_area"] = ""
    # 2. 让上传组件的 ID +1，强制 Streamlit 重新渲染一个空的组件
    st.session_state["uploader_key_id"] += 1

# ===========================
#  Sidebar: All Inputs Here
# ===========================
with st.sidebar:
    st.markdown("""
        <h1 style='text-align: left; color: #fff; font-size: 24px; font-family: "Helvetica Neue", sans-serif; font-weight: 700; margin-bottom: 0;'>
            <span>💠</span>
            <span style='background: linear-gradient(45deg, #4facfe 0%, #00f2fe 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
               AI Knowledge
            </span>
            &nbsp;
            <span style='font-size: 24px; color: #fff; font-weight: 700;'>
                Agent
            </span>
        </h1>
        """, unsafe_allow_html=True)
    st.markdown("*Your All-in-One Knowledge Partner*")
    st.divider()

    # --- Header & Clear Button ---
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header("📥 Input Source")
    with col2:
        # 🗑️ 垃圾桶按钮
        st.button("🗑️", on_click=clear_inputs, help="Clear all inputs")
    
    # --- Input Form ---
    with st.form(key="input_form"):
        # 1. File Upload 
        # 核心修改：key 是动态的，每次点击清除按钮，key 就会变，从而清空文件
        dynamic_key = f"file_uploader_{st.session_state['uploader_key_id']}"
        
        uploaded_file = st.file_uploader(
            "📄 Upload PDF Document", 
            type=["pdf"], 
            key=dynamic_key 
        )
        
        # 2. Text/URL Input
        user_input = st.text_area(
            "🔗 Or paste URL / Text:", 
            height=200, 
            key="input_area", # 这个 key 对应 session_state
            placeholder="Paste URL or Text here..."
        )
        
        st.divider()
        
        # Submit Button
        submit_btn = st.form_submit_button("🚀 Start Processing", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("© 2025 AI Knowledge Agent.")


# ===========================
#  Main Interface
# ===========================

if not submit_btn:
    # 图片加载逻辑：优先本地，失败则网络
    if os.path.exists("banner.jpg"):
        st.image("banner.jpg", caption="Knowledge is power.", use_container_width=True)
    else:
        st.image(
            "https://cdn.pixabay.com/photo/2018/03/19/18/20/tea-time-3240766_1280.jpg",
            caption="“Knowledge is a universe waiting to be explored.”",
            use_container_width=True
        )
    st.info("👈 Please provide a URL, text, or upload a PDF in the sidebar to begin.")


if submit_btn:
    if not user_input and not uploaded_file:
        st.warning("⚠️ Please provide input via URL/Text OR upload a file in the sidebar.")
    else:
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
                # === Core Workflow ===
                main_workflow(user_input=user_input, uploaded_file=uploaded_file)
                
                status.update(label="✅ Mission Complete! Knowledge secured in Notion.", state="complete", expanded=False)
                st.balloons()
                st.success("🎉 Successfully processed and saved to your Notion database!")
                
                # Success Image
                st.image(
                    "https://images.unsplash.com/photo-1499750310159-5b5f38e31638?q=80&w=2000&auto=format&fit=crop",
                    caption="Knowledge integrated.",
                    use_container_width=True
                )

            except Exception as e:
                status.update(label="❌ Mission Failed", state="error")
                st.error(f"Runtime Error: {str(e)}")
            finally:
                sys.stdout = old_stdout