import streamlit as st
import sys
from io import StringIO
from main import main_workflow

# --- Page Configuration ---
# --- CSS Styles for Custom Button ---
st.markdown("""
    <style>
    /* 针对 Primary 按钮的定制样式 */
    div.stButton > button:first-child {
        background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%); /* 这里的颜色和标题对应 */
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s ease;
    }

    /* 鼠标悬停时的效果：稍微变亮 + 发光 */
    div.stButton > button:first-child:hover {
        background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%);
        box-shadow: 0 4px 15px rgba(0, 242, 254, 0.4); /* 蓝色光晕 */
        color: white;
        transform: translateY(-2px); /* 微微上浮 */
    }

    /* 点击时的效果 */
    div.stButton > button:first-child:active {
        transform: translateY(0px);
    }
    </style>
    """, unsafe_allow_html=True)

# --- Initialize session state ---
if "user_input" not in st.session_state:
    st.session_state["user_input"] = ""

# ===========================
#  Sidebar: All Inputs Here
# ===========================
with st.sidebar:    
    # 替换为以下自定义 HTML 代码：
    st.markdown("""
        <h1 style='text-align: left; color: #fff; font-size: 26px; font-family: "Helvetica Neue", sans-serif; font-weight: 700;'>
            <span style='background: linear-gradient(45deg, #4facfe 0%, #00f2fe 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
                💠 AI Knowledge Agent
            </span>
            <br>
            <span style='font-size: 18px; color: #888; font-weight: 400;'>
                
            </span>
        </h1>
        """, unsafe_allow_html=True)
        
    st.markdown("*Your All-in-One Knowledge Partner*")
    st.divider()

    st.header("📥 Input Source")
    
    # 🌟 关键修改：使用 st.form 将输入和按钮打包
    with st.form(key="input_form"):
        # 1. File Upload
        uploaded_file = st.file_uploader("📄 Upload PDF Document", type=["pdf"])
        
        # 2. Text/URL Input
        # 注意：在 form 里按 Cmd+Enter 会自动触发提交按钮
        user_input = st.text_area(
            "🔗 Or paste URL / Text:", 
            height=200, 
            key="input_area",
            placeholder="Example URLs:\n- https://youtube.com/watch?v=...\n- https://medium.com/@...\n\nOr directly paste any text/article content here."
        )
        
        st.divider()
        
        # Action Button
        # 🌟 关键修改：button -> form_submit_button
        # 只有在 form 里，Cmd+Enter 才会生效
        submit_btn = st.form_submit_button("🧬 Start Processing", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("© 2025 AI Knowledge Agent. Built and Streamlit.")


# ===========================
#  Main Interface: Visuals & Results
# ===========================

# 1. 梦幻插图 (当没有提交时显示)
if not submit_btn:
    st.image(
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=2072&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
        caption="“Knowledge is a universe waiting to be explored.”",
        use_column_width=True
    )
    st.info("👈 Please provide a URL, text, or upload a PDF in the sidebar to begin.")


# 2. 处理逻辑与日志显示
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
                    use_column_width=True
                )

            except Exception as e:
                status.update(label="❌ Mission Failed", state="error")
                st.error(f"Runtime Error: {str(e)}")
            finally:
                sys.stdout = old_stdout