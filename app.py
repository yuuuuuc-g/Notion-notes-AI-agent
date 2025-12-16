import streamlit as st
import json
import os
from dotenv import load_dotenv

# 导入我们之前写好的核心功能
# 注意：确保 main.py 和 notion_ops.py 在同一目录下
from main import (
    analyze_new_note, 
    check_topic_match, 
    generate_full_content, 
    decide_merge_strategy, 
    parse_json
)
from notion_ops import (
    get_all_page_titles, 
    get_page_structure, 
    add_row_to_table, 
    append_to_page, 
    create_study_note
)

# 加载环境变量
load_dotenv()
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# --- 页面配置 ---
st.set_page_config(
    page_title="Spanish AI agent",
    page_icon="🇪🇸",
    layout="centered"
)

# --- 标题区 ---
st.title("🇪🇸 Spanish AI agent")
st.markdown("给牛马喂饭🍚")

# 侧边栏：状态检查
with st.sidebar:
    st.header("⚙️ 系统状态")
    if os.getenv("OPENAI_API_KEY"):
        st.success("DeepSeek API: 已连接")
    else:
        st.error("DeepSeek API: 未配置")
        
    if os.getenv("NOTION_TOKEN"):
        st.success("Notion API: 已连接")
    else:
        st.error("Notion API: 未配置")
        
    st.info(f"Database ID: ...{str(NOTION_DATABASE_ID)[-4:]}")

# --- 主输入区 ---
raw_input = st.text_area(
    "在此粘贴你的笔记：", 
    height=2000, 
    placeholder="例如：动词 Ser 的变位：Yo soy, Tú eres... 或者关于虚拟式的补充笔记..."
)

# --- 核心逻辑区 ---
if st.button("🚀 GO", type="primary"):
    if not raw_input.strip():
        st.warning("⚠️ 请先输入笔记内容！")
        st.stop()

    # 使用 st.status 创建一个动态的状态流 (非常有科技感)
    with st.status("🤖 AI 正在大脑风暴中...", expanded=True) as status:
        
        # 1. 检索阶段
        st.write("🔍 正在读取 Notion 现有知识库...")
        all_pages = get_all_page_titles()
        st.write(f"📚 已索引 {len(all_pages)} 条现有笔记。")
        
        # 2. 语义分析阶段
        st.write("🧠 正在进行语义查重与主题分析...")
        match_result = parse_json(check_topic_match(raw_input, all_pages))
        
        if match_result and match_result.get('match'):
            # === 分支 A: 找到旧笔记 ===
            page_title = match_result['page_title']
            page_id = match_result['page_id']
            
            status.update(label=f"💡 发现已有主题：{page_title}", state="running")
            st.info(f"匹配到已有页面：《{page_title}》，准备融合...")
            
            # 读取结构
            st.write("👀 正在读取页面结构...")
            structure_text, tables = get_page_structure(page_id)
            
            if tables:
                st.write(f"📊 发现 {len(tables)} 个表格，思考融合策略...")
                merge_decision = parse_json(decide_merge_strategy(raw_input, structure_text, tables))
                
                if merge_decision and merge_decision.get('action') == 'insert_row':
                    status.update(label="🚀 执行：表格行插入", state="running")
                    st.write("💡 策略：将新知识插入现有表格...")
                    
                    success = add_row_to_table(
                        merge_decision['table_id'], 
                        merge_decision['row_data']
                    )
                    if success:
                        st.success(f"✅ 已插入表格：{merge_decision['row_data']}")
                    else:
                        st.error("❌ 插入表格失败")
                else:
                    status.update(label="🚀 执行：文末追加", state="running")
                    st.write("💡 策略：内容不匹配现有表格，追加到文末...")
                    
                    # 生成积木
                    full_content = parse_json(generate_full_content(raw_input))
                    if full_content:
                        success = append_to_page(page_id, full_content['summary'], full_content['blocks'])
                        if success:
                            st.success("✅ 追加成功！")
            else:
                st.write("📝 页面无表格，直接追加内容...")
                full_content = parse_json(generate_full_content(raw_input))
                if full_content:
                    success = append_to_page(page_id, full_content['summary'], full_content['blocks'])
                    if success:
                        st.success("✅ 追加成功！")
                        
        else:
            # === 分支 B: 新主题 ===
            new_title = match_result.get('suggested_title', '新笔记') if match_result else "新笔记"
            status.update(label=f"🆕 创建新主题：{new_title}", state="running")
            st.write("✨ 这是一个全新的知识点，正在生成结构化页面...")
            
            full_content = parse_json(generate_full_content(raw_input))
            if full_content:
                # 使用 AI 生成的标题可能更准
                final_title = full_content.get('title', new_title)
                success = create_study_note(
                    title=final_title,
                    category=full_content.get('category', '语法'),
                    summary=full_content.get('summary', ''),
                    blocks=full_content.get('blocks', [])
                )
                if success:
                    st.success(f"✅ 页面《{final_title}》创建成功！")
                else:
                    st.error("❌ 创建失败")

        status.update(label="🎉 处理完成！", state="complete", expanded=False)

    # --- 结果展示区 ---
    st.markdown("### ✨ 整理预览")
    st.markdown(f"https://www.notion.so/2c535e6b0ea580ce8170d8c0bebff29a?v=2c535e6b0ea58089abb8000cd021315e&source=copy_link")
    
    # 调试用：显示一下 AI 分析出的 JSON (折叠起来)
    with st.expander("🔍 查看 AI 分析的原始数据 (Debug)"):
        if 'full_content' in locals() and full_content:
            st.json(full_content)
        if 'merge_decision' in locals() and merge_decision:
            st.write("融合决策:")
            st.json(merge_decision)