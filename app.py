import streamlit as st
import sys
from io import StringIO
from main import main_workflow

# --- Page Configuration ---
st.set_page_config(
    page_title="AI Knowledge Agent",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded" # 默认展开侧边栏
)

# --- Initialize session state ---
if "user_input" not in st.session_state:
    st.session_state["user_input"] = ""

# ===========================
#  Sidebar: All Inputs Here
# ===========================
with st.sidebar:
    # 标题移到侧边栏
    st.title("🧠 AI Knowledge Agent")
    st.markdown("*Your All-in-One Knowledge Partner*")
    st.divider()

    st.header("📥 Input Source")
    
    # 1. File Upload
    uploaded_file = st.file_uploader("📄 Upload PDF Document", type=["pdf"])
    
    # 2. Text/URL Input (Moved Here!)
    user_input = st.text_area(
        "🔗 Or paste URL / Text:", 
        height=200, 
        key="input_area",
        placeholder="Example URLs:\n- https://youtube.com/watch?v=...\n- https://medium.com/@...\n\nOr directly paste any text/article content here."
    )
    
    st.divider()
    
    # Action Button
    # 使用 columns 让按钮居中更有仪式感
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        start_btn = st.button("🚀 Start Processing", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("© 2023 AI Knowledge Agent. Built with ❤️ and Streamlit.")


# ===========================
#  Main Interface: Visuals & Results
# ===========================

# 1. 梦幻插图 (当没有任务在运行时显示)
if not start_btn:
    # 这里使用一张 Unsplash 的高质量占位图，你也可以换成自己喜欢的本地图片
    # 例如: st.image("dreamy_illustration.png", use_column_width=True)
    st.image(
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?q=80&w=2072&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
        caption="“Knowledge is a universe waiting to be explored.”",
        use_column_width=True
    )
    st.info("👈 Please provide a URL, text, or upload a PDF in the sidebar to begin.")


# 2. 处理逻辑与日志显示
if start_btn:
    if not user_input and not uploaded_file:
        st.warning("⚠️ Please provide input via URL/Text OR upload a file in the sidebar.")
    else:
        # 使用更宽的 status 栏，并给一个美好的标题
        with st.status("🌌 Navigating the cosmos of knowledge...", expanded=True) as status:
            # Redirect stdout to capture logs
            old_stdout = sys.stdout
            result_buffer = StringIO()
            log_placeholder = st.empty()
            
            class StreamlitLogger:
                def write(self, msg):
                    if msg.strip():
                        result_buffer.write(msg + "\n")
                        # 使用更大的字体显示日志，更有科技感
                        log_placeholder.markdown(f"```text\n{result_buffer.getvalue()}\n```")
                def flush(self): pass

            sys.stdout = StreamlitLogger()
            
            try:
                # === Core Workflow ===
                main_workflow(user_input=user_input, uploaded_file=uploaded_file)
                
                status.update(label="✅ Mission Complete! Knowledge secured in Notion.", state="complete", expanded=False)
                st.success("🎉 Successfully processed and saved to your Notion database!")
                
                # 处理完成后，可以再显示一张成功的插图，或者就留白
                st.image(
                    "https://images.unsplash.com/photo-1550537687-c9107a249001?q=80&w=2070&auto=format&fit=crop&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D",
                    caption="Knowledge integrated.",
                    use_column_width=True
                )

            except Exception as e:
                status.update(label="❌ Mission Failed", state="error")
                st.error(f"Runtime Error: {str(e)}")
            finally:
                # Restore standard output
                sys.stdout = old_stdout