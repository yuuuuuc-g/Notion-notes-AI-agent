import streamlit as st
import os
from main import main_workflow

# 设置页面配置
st.set_page_config(page_title="AI 助手笔记整理", page_icon="🤖", layout="wide")

st.title("🤖 AI 助手笔记整理")
st.markdown("---")

# 侧边栏
with st.sidebar:
    st.header("使用说明")
    st.info("直接在下方输入：\n1. 西语笔记/语法点\n2. YouTube 视频链接\n3. 技术/经济文章链接")
    st.divider()
    if st.button("清空输入"):
        st.session_state["user_input"] = ""

# 输入框 (绑定 session_state 以便清空)
user_input = st.text_area("请输入内容或粘贴 URL:", height=200, key="user_input")

if st.button("🚀 开始整理", type="primary"):
    if not user_input:
        st.warning("请先输入内容！")
    else:
        # 使用 st.status 显示动态日志
        with st.status("正在思考中...", expanded=True) as status:
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
                
                status.update(label="✅ 处理完成！", state="complete", expanded=False)
                st.success("笔记已成功存入 Notion！")
                
            except Exception as e:
                status.update(label="❌ 发生错误", state="error")
                st.error(f"程序运行出错: {str(e)}")
            finally:
                # 恢复标准输出
                sys.stdout = old_stdout