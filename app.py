import streamlit as st
import sys
from io import StringIO
from main import main_workflow

# Page Configuration
st.set_page_config(page_title="AI Knowledge Agent", page_icon="🧠", layout="wide")

st.title("🧠 AI Knowledge Agent (All-in-One)")
st.markdown("---")

# Initialize session state
if "user_input" not in st.session_state:
    st.session_state["user_input"] = ""

# --- Sidebar: Input Area ---
with st.sidebar:
    st.header("📥 Input Source")
    
    # Option 1: File Upload
    uploaded_file = st.file_uploader("Upload PDF Document", type=["pdf"])
    
    st.divider()
    
    # Option 2: Text/URL Input
    user_input = st.text_area(
        "Or paste URL / Text:", 
        height=150, 
        key="input_area",
        placeholder="https://youtube.com/...\nhttps://medium.com/...\nOr paste text directly here"
    )
    
    st.divider()
    
    # Action Button
    start_btn = st.button("🚀 Start Processing", type="primary")

# --- Main Interface: Logs & Results ---
if start_btn:
    if not user_input and not uploaded_file:
        st.warning("⚠️ Please upload a file or enter content!")
    else:
        # Status container
        with st.status("🤖 AI is processing...", expanded=True) as status:
            # Redirect stdout to capture logs
            old_stdout = sys.stdout
            result_buffer = StringIO()
            log_placeholder = st.empty()
            
            class StreamlitLogger:
                def write(self, msg):
                    if msg.strip():
                        result_buffer.write(msg + "\n")
                        log_placeholder.code(result_buffer.getvalue(), language="text")
                def flush(self): pass

            sys.stdout = StreamlitLogger()
            
            try:
                # === Core Workflow ===
                main_workflow(user_input=user_input, uploaded_file=uploaded_file)
                
                status.update(label="✅ Processing Complete!", state="complete", expanded=False)
                st.success("🎉 Knowledge saved to Notion successfully!")
                
            except Exception as e:
                status.update(label="❌ Error Occurred", state="error")
                st.error(f"Runtime Error: {str(e)}")
            finally:
                # Restore standard output
                sys.stdout = old_stdout