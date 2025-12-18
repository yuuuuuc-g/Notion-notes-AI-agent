import streamlit as st
import sys
from io import StringIO
from main import main_workflow

# --- Page Configuration ---
st.set_page_config(
    page_title="AI Knowledge Agent",
    page_icon="💠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 🎨 CSS Styles ---
st.markdown("""
    <style>
    /* 1. 针对普通 Primary 按钮 */
    button[kind="primary"] {
        background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%) !important;
        border: none !important;
    }

    /* 2. 针对表单提交按钮 (Form Submit) */
    button[kind="primaryFormSubmit"] {
        background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%) !important;
        border: none !important;
    }

    /* 3. 针对侧边栏里的所有按钮 (兜底) */
    section[data-testid="stSidebar"] button {
        background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%) !important;
        color: white !important;
        border: none !important;
        font-weight: bold !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* 4. 特殊处理：清除按钮 (使其看起来不同，可选) */
    /* 如果你想让清除按钮变灰，可以解开下面的注释，否则它也是蓝色的 */
    /*
    #section[data-testid="stSidebar"] button[kind="secondary"] {
    #    background: #f0f2f6 !important;
    #    color: #31333F !important;
    }
    */

    /* 悬停效果 */
    button[kind="primary"]:hover, 
    button[kind="primaryFormSubmit"]:hover,
    section[data-testid="stSidebar"] button:hover {
        background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%) !important;
        box-shadow: 0 4px 15px rgba(0, 242, 254, 0.4) !important;
        transform: translateY(-2px);
        color: white !important;
    }

    /* 去掉点击时的聚焦框 */
    button:focus {
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 🧹 Callback Function to Clear Inputs ---
def clear_inputs():
    # 清空文本框
    st.session_state["input_area"] = ""
    # 清空文件上传器 (设置为 None 即可)
    st.session_state["file_uploader_key"] = None

# --- Initialize session state ---
if "input_area" not in st.session_state:
    st.session_state["input_area"] = ""

# ===========================
#  Sidebar: All Inputs Here
# ===========================
with st.sidebar:
    # 标题
    st.markdown("""
        <h1 style='text-align: left; color: #fff; font-size: 24px; font-family: "Helvetica Neue", sans-serif; font-weight: 700; margin-bottom: 0;'>
            <span>💠</span>
            <span style='background: linear-gradient(45deg, #4facfe 0%, #00f2fe 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
               Knowledge
            </span>
            &nbsp;
            <span style='font-size: 24px; color: #fff; font-weight: 700;'>
                AI Agent
            </span>
        </h1>
        """, unsafe_allow_html=True)
        
    st.markdown("*Your All-in-One Knowledge Partner*")
    st.divider()

    # --- Header & Clear Button Layout ---
    # 使用 columns 把标题和清除按钮放在同一行
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header("📥 Input Source")
    with col2:
        # 🗑️ 清除按钮：点击时触发 clear_inputs 函数
        st.button("🗑️", on_click=clear_inputs, help="Clear all inputs")
    
    # --- Input Form ---
    with st.form(key="input_form"):
        # 1. File Upload (注意：这里加了 key="file_uploader_key")
        uploaded_file = st.file_uploader(
            "📄 Upload PDF Document", 
            type=["pdf"], 
            key="file_uploader_key" 
        )
        
        # 2. Text/URL Input (注意：key="input_area" 必须和 session_state 对应)
        user_input = st.text_area(
            "🔗 Or paste URL / Text:", 
            height=200, 
            key="input_area",
            placeholder="Example URLs:\n- https://youtube.com/watch?v=...\n- https://medium.com/@...\n\nOr directly paste any text/article content here."
        )
        
        st.divider()
        
        # Submit Button
        submit_btn = st.form_submit_button("🚀 Start Processing", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("© 2025 AI Knowledge Agent. ")


# ===========================
#  Main Interface: Visuals & Results
# ===========================

# === 在 app.py 底部找到这部分 ===

if not submit_btn:
    # 尝试加载本地图片，如果不存在则加载默认网络图（作为兜底）
    import os
    if os.path.exists("banner.jpg"):
        st.image("banner.jpg", caption="Knowledge is power.", use_container_width=True)
    else:
        # 这是一个备用的网络图片链接
        st.image(
            "https://cdn.pixabay.com/photo/2016/02/16/21/07/books-1204029_1280.jpg",
            caption="Knowledge is a universe waiting to be explored.",
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
                st.success("🎉 Successfully processed and saved to your Notion database!")
                
                st.image(
                    "https://images.unsplash.com/photo-1550537687-c9107a249001?q=80&w=2070&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
                    caption="Knowledge integrated.",
                    width=True
                )

            except Exception as e:
                status.update(label="❌ Mission Failed", state="error")
                st.error(f"Runtime Error: {str(e)}")
            finally:
                sys.stdout = old_stdout