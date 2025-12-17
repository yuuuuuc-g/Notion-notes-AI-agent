import streamlit as st
import os
from main import main_workflow

# 设置页面配置
st.set_page_config(page_title="AI assistant notes", page_icon="🤖", layout="wide")

st.title("🤖 AI assistant notes")
st.markdown("---")

# 侧边栏
with st.sidebar:
    st.header("Instructions")
    st.info("Enter one of the following below:\nText or URL")
    st.divider()
    if st.button("Clear Input"):
        st.session_state["user_input"] = ""

# 输入框 (绑定 session_state 以便清空)
user_input = st.text_area("Enter content or paste URL here:", height=200, key="user_input")

if st.button("🚀 Start Processing", type="primary"):
    if not user_input:
        st.warning("Please enter content first!")
    else:
        # 使用 st.status 显示动态日志
        with st.status("Processing...", expanded=True) as status:
            # 重定向 print 输出到 Streamlit 界面
            import sys
            from io import StringIO
            
            # 捕获 stdout
            old_stdout = sys.stdout
            result_buffer = StringIO()
            
            # 创建一个占位符用于实时更新日志
            log_placeholder = st.empty()
            
            class StreamlitLogger:
                def write(self, msg):
                    if msg.strip():
                        # 实时更新页面上的代码块
                        result_buffer.write(msg + "\n")
                        log_placeholder.code(result_buffer.getvalue(), language="text")
                def flush(self):
                    pass

            sys.stdout = StreamlitLogger()
            
            try:
                # === 核心调用 ===
                main_workflow(user_input)
                
                status.update(label="✅ Processing Complete!", state="complete", expanded=False)
                st.success("Note successfully saved to Notion!")
                
            except Exception as e:
                status.update(label="❌ Error Occurred", state="error")
                st.error(f"程序运行出错: {str(e)}")
            finally:
                # 恢复标准输出
                sys.stdout = old_stdout