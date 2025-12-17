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

# --- 🎨 CSS Styles (核弹级覆盖方案) ---
st.markdown("""
    <style>
    /* 1. 针对普通 Primary 按钮 */
    button[kind="primary"] {
        background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%) !important;
        border: none !important;
    }

    /* 2. 针对表单提交按钮 (Form Submit) - 关键！ */
    button[kind="primaryFormSubmit"] {
        background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%) !important;
        border: none !important;
    }

    /* 3. 针对所有侧边栏里的按钮 (兜底方案) */
    section[data-testid="stSidebar"] button {
        background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%) !important;
        color: white !important;
        border: none !important;
        font-weight: bold !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    /* 悬停效果 (让所有种类的按钮悬停都发蓝光) */
    button[kind="primary"]:hover, 
    button[kind="primaryFormSubmit"]:hover,
    section[data-testid="stSidebar"] button:hover {
        background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%) !important;
        box-shadow: 0 4px 15px rgba(0, 242, 254, 0.4) !important;
        transform: translateY(-2px);
        color: white !important;
    }

    /* 去掉点击时的红色边框和轮廓 */
    button:focus {
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
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
    # 标题部分 (双行设计)
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

    st.header("📥 Input Source")
    
    with st.form(key="input_form"):
        uploaded_file = st.file_uploader("📄 Upload PDF Document", type=["pdf"])
        
        user_input = st.text_area(
            "🔗 Or paste URL / Text:", 
            height=200, 
            key="input_area",
            placeholder="Example URLs:\n- https://youtube.com/watch?v=...\n- https://medium.com/@...\n\nOr directly paste any text/article content here."
        )
        
        st.divider()
        
        # 按钮
        submit_btn = st.form_submit_button("🚀 Start Processing", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("© 2025 AI Knowledge Agent.")


# ===========================
#  Main Interface: Visuals & Results
# ===========================

if not submit_btn:
    st.image(
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=2072&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
        caption="“Knowledge is a universe waiting to be explored.”",
        use_column_width=True
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