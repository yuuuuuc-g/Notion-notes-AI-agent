import json
import re
import os
from dotenv import load_dotenv
from llm_client import get_completion
from web_ops import fetch_url_content
from notion_ops import (
    create_study_note,          
    create_general_note,        
    get_all_page_titles, 
    append_to_page, 
    get_page_structure, 
    add_row_to_table
)

load_dotenv()

# 获取两个数据库的 ID
DB_SPANISH = os.getenv("NOTION_DATABASE_ID") 
DB_GENERAL = os.getenv("NOTION_DATABASE_ID_GENERAL") 

# --- 辅助函数 ---
def parse_json(text):
    cleaned_text = re.sub(r"```json|```", "", text).strip()
    try: return json.loads(cleaned_text)
    except: return None

def read_input_file():
    file_path = "note.txt"
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f: f.write("请在此粘贴笔记或URL")
        return None
    with open(file_path, "r", encoding="utf-8") as f: return f.read().strip()

# --- 🧠 核心大脑：分类器 (Router) ---
def classify_intent(text):
    prompt = f"""
    你是一个内容分发总监。请分析以下文本的内容类型。
    
    【文本前800字】
    {text[:800]}
    
    【判断逻辑】
    1. **Spanish**: 内容包含西班牙语单词、语法讲解，或者看起来像是一段西语教学视频的字幕。
    2. **General**: 宏观经济、政治、AI 技术、编程代码、职场感悟等非语言学习类。
    
    【输出 JSON】
    {{ "type": "Spanish" }} 或 {{ "type": "General" }}
    """
    result = get_completion(prompt)
    return parse_json(result)

# --- 🧠 大脑 B：通用内容处理器 ---
def process_general_knowledge(text):
    prompt = f"""
    你是一个资深的研究员。请整理这份素材，提取核心洞察。
    
    输入内容：
    {text[:12000]} 
    
    任务：
    1. 拟定一个吸引人的标题。
    2. 提取 3-5 个关键标签 (Tags)。
    3. 写一段 100-200 字的深度摘要。
    4. 将正文整理为清晰的笔记结构 (Blocks)，保留数据、代码和论点。
    
    输出 JSON: {{ "title": "...", "tags": [], "summary": "...", "blocks": [...] }}
    """
    return get_completion(prompt)

# --- 🧠 大脑 A：西语处理器 (升级版) ---
def check_topic_match(new_text, existing_pages):
    titles_list = [f"ID: {p['id']}, Title: {p['title']}" for p in existing_pages]
    titles_str = "\n".join(titles_list) if titles_list else "暂无现有笔记"
    
    prompt = f"""
    你是一个智能图书管理员。
    【现有西语笔记列表】
    {titles_str}
    【新素材前1000字】
    {new_text[:1000]}
    【任务】判断新素材的核心主题是否已存在？
    输出 JSON: 
    {{ "match": true, "page_id": "...", "page_title": "..." }} 
    或 
    {{ "match": false, "suggested_title": "..." }}
    """
    return get_completion(prompt)

def generate_spanish_content(raw_text):
    """
    核心生成逻辑：针对长字幕进行了专门优化
    """
    prompt = f"""
    你是一个精通西班牙语教学的高级编辑。
    用户的输入可能是一份笔记，也可能是一段长视频的【字幕原文】。
    
    【输入内容】
    {raw_text[:15000]}  <-- 关键修改：读取前 15000 字，确保读到完整内容！
    
    【你的任务】
    不要只是总结！必须进行**“知识萃取”**。
    
    1. **识别核心词汇**：如果输入是字幕，必须从中提取出至少 5-10 个核心生词/短语，制作成表格。
    2. **提取地道例句**：找到原文本中出现的精彩句子，保留西语原文并附带中文解释。
    3. **结构化重组**：使用 Heading, List, Table 将内容排版。
    
    【JSON 输出结构】
    {{
        "title": "精准的标题 (如果是视频，用视频主题)",
        "category": "听力/词汇/语法",
        "summary": "200字左右的内容简介，概括视频主要场景和话题",
        "blocks": [
            {{ "type": "heading", "content": "1. 核心词汇 (Vocabulario)" }},
            {{ 
                "type": "table", 
                "content": {{
                    "headers": ["西语", "中文含义", "备注/场景"],
                    "rows": [
                        ["el cajero", "收银员", "商场结账场景"],
                        ["pagar con tarjeta", "刷卡支付", "常用短语"]
                    ]
                }}
            }},
            {{ "type": "heading", "content": "2. 精彩例句 (Frases Clave)" }},
            {{ "type": "list", "content": ["Me gustaría probarme esta camisa. (我想试试这件衬衫)", "¿Tienen este pantalón en talla M? (这条裤子有M码吗?)"] }},
            {{ "type": "heading", "content": "3. 语法/文化要点" }},
            {{ "type": "text", "content": "这里放语法解析或文化背景..." }}
        ]
    }}
    
    只输出 JSON。
    """
    return get_completion(prompt)

def decide_merge_strategy(new_text, existing_structure_text, available_tables):
    prompt = f"""
    你是一个智能编辑。
    【页面结构】{existing_structure_text}
    【现有表格】{json.dumps(available_tables)}
    【新内容】{new_text[:2000]}
    任务：判断是否适合插入现有表格？
    输出 JSON: {{ "action": "insert_row", "table_id": "...", "row_data": [...] }} 或 {{ "action": "append_text" }}
    """
    return get_completion(prompt)

# --- 🎩 总指挥逻辑 ---
def main_workflow(raw_input):
    original_url = None
    
    # 1. 识别 URL
    url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    if url_pattern.match(raw_input.strip()):
        original_url = raw_input.strip()
        print(f"🌐 正在抓取 URL: {original_url}")
        content = fetch_url_content(original_url)
        if not content: return
        # 显式保留 URL 信息供后续使用
        processed_text = f"【来源 URL】{original_url}\n\n{content}"
    else:
        processed_text = raw_input

    # 2. 🚦 路由分类
    intent = classify_intent(processed_text)
    content_type = intent.get('type', 'General')
    print(f"👉 判定类型为：【{content_type}】")

    # === 通道 A: 西语学习 ===
    if content_type == 'Spanish':
        
        # 为了演示简单，这里假设 all_pages 仅来自西语库
        # 实际项目中应传入 DB_SPANISH
        all_pages = get_all_page_titles() 
        
        match_result = parse_json(check_topic_match(processed_text, all_pages))
        
        if match_result and match_result.get('match'):
            page_id = match_result.get('page_id')
            page_title = match_result.get('page_title', '未知标题')
            print(f"💡 融合旧笔记: 《{page_title}》")
            
            if not page_id: return

            structure_text, tables = get_page_structure(page_id)
            
            if tables:
                merge_decision = parse_json(decide_merge_strategy(processed_text, structure_text, tables))
                if merge_decision and merge_decision.get('action') == 'insert_row':
                    print("💡 策略：插入表格...")
                    add_row_to_table(merge_decision['table_id'], merge_decision['row_data'])
                else:
                    print("💡 策略：文末追加...")
                    full_content = parse_json(generate_spanish_content(processed_text))
                    if full_content:
                        append_to_page(page_id, full_content['summary'], full_content['blocks'])
            else:
                full_content = parse_json(generate_spanish_content(processed_text))
                if full_content:
                    append_to_page(page_id, full_content['summary'], full_content['blocks'])
        else:
            print("🆕 新建西语笔记...")
            full_content = parse_json(generate_spanish_content(processed_text))
            if full_content:
                create_study_note(
                    full_content['title'], 
                    full_content.get('category', '听力'), # 字幕通常归类为听力
                    full_content['summary'], 
                    full_content['blocks']
                )

    # === 通道 B: 通用知识 ===
    else:
        print("🌍 进入通用知识模式 (AI/经济/编程)...")
        if not DB_GENERAL:
            print("❌ 错误：未配置通用数据库 ID")
            return

        analysis = parse_json(process_general_knowledge(processed_text))
        if analysis:
            create_general_note(
                title=analysis.get('title', '未命名文档'),
                tags=analysis.get('tags', []),
                summary=analysis.get('summary', ''),
                url=original_url,
                content_blocks=analysis.get('blocks', []),
                db_id=DB_GENERAL
            )

if __name__ == "__main__":
    raw = read_input_file()
    if raw and "请在此粘贴" not in raw:
        main_workflow(raw)
        print("\n🎉 处理完成！")