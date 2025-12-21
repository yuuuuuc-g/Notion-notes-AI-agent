# --- 💉 必须放在最前面：修复 Streamlit Cloud 的 SQLite 版本问题 ---
import sys
import os
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass
# -----------------------------------------------------------

import streamlit as st
from io import StringIO
from main import main_workflow

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

# --- 🛠️ 状态初始化 ---
if "input_area" not in st.session_state:
    st.session_state["input_area"] = ""

if "uploader_key_id" not in st.session_state:
    st.session_state["uploader_key_id"] = 0

# --- 🧹 清除功能 ---
def clear_inputs():
    st.session_state["input_area"] = ""
    st.session_state["uploader_key_id"] += 1

# ===========================
#  Sidebar: All Inputs Here
# ===========================
with st.sidebar:
    # 🌟 标题修复：带渐变色的 Second Brain Pipeline
    st.markdown("""
        <h1 style='text-align: left; color: #333; font-size: 22px; font-family: sans-serif; font-weight: 800; margin-bottom: 5px;'>
            <span style='font-size: 26px;'>💠</span>
            <span style='background: linear-gradient(45deg, #4facfe 0%, #00f2fe 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
               Second Brain Pipeline
            </span>
        </h1>
        <p style='font-size: 12px; color: #666; margin-bottom: 20px;'>
            Your Personal AI Second Brain
        </p>
        """, unsafe_allow_html=True)
    
    st.divider()

    # 布局：输入区标题 + 清除按钮
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("**📥 Input Zone**")
    with col2:
        st.button("🗑️", on_click=clear_inputs, help="Clear all inputs", use_container_width=True)
    
    # --- 统一输入卡片 ---
    with st.form(key="input_form"):
        with st.container(border=True):
            # 1. 动态 Key 用于重置
            dynamic_key = f"file_uploader_{st.session_state['uploader_key_id']}"
            
            # 2. 文件上传区
            uploaded_file = st.file_uploader(
                "📎 Upload PDF (Drag & Drop supported)", 
                type=["pdf"], 
                key=dynamic_key
            )
            
            # 3. 文本输入区
            user_input = st.text_area(
                "Or paste text/link below:", 
                height=150, 
                key="input_area",
                placeholder="https://... or Paste text here",
                label_visibility="visible"
            )
        
        # 4. 提交按钮
        submit_btn = st.form_submit_button("🚀 Start Processing", type="primary", use_container_width=True)

    # 底部版权
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #999; font-size: 12px;'>© 2025 Second Brain Pipeline</div>", 
        unsafe_allow_html=True
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

if submit_btn:
    if not user_input and not uploaded_file:
        st.warning("⚠️ Please provide input via URL/Text OR upload a file.")
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
                # === 调用主逻辑 ===
                main_workflow(user_input=user_input, uploaded_file=uploaded_file)
                
                status.update(label="✅ Mission Complete!", state="complete", expanded=False)
                st.balloons()
                st.success("🎉 Successfully processed and saved to your Notion database!")
                
                # 成功后的插图
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