import json
import os
import re
from dotenv import load_dotenv
from llm_client import get_completion, get_reasoning_completion
from web_ops import fetch_url_content
import notion_ops

try:
    from file_ops import read_pdf_content
except ImportError:
    read_pdf_content = None

load_dotenv()

# --- 🛠️ 核心修复：全能解析器 ---
def safe_json_parse(input_data, context=""):
    if not input_data:
        print(f"❌ [Error] {context}: LLM 返回内容为空！")
        return None
    if isinstance(input_data, dict): return input_data
    try:
        text = str(input_data).strip()
        # 调试日志：看看 AI 到底回了什么
        # print(f"🔍 [Debug Raw] {text[:100]}...") 
        
        clean_text = text.replace("```json", "").replace("```", "")
        # 寻找 JSON 的起止点
        start = clean_text.find("{")
        end = clean_text.rfind("}") + 1
        if start != -1 and end != -1: 
            clean_text = clean_text[start:end]
            
        return json.loads(clean_text)
    except Exception as e:
        print(f"❌ [Error] {context} JSON 解析失败: {e}")
        return None

# --- 🧠 Brain A: Classifier ---
def classify_intent(text):
    prompt = f"""
    Analyze the content type. First 800 chars: {text[:800]}
    Return JSON with "type":
    1. "Spanish": Language learning (Grammar, Vocab, Spanish videos).
    2. "Tech": AI, Coding, Engineering, Software, Hard Science.
    3. "Humanities": Politics, Economy, History, Philosophy, Social Science, News, Culture.
    
    JSON Example: {{ "type": "Tech" }}
    """
    res = get_completion(prompt)
    return safe_json_parse(res, "Classify") or {"type": "Humanities"}

# --- 🧠 Brain B: Spanish Logic ---
def check_topic_match(new_text, existing_pages):
    if not existing_pages: return {"match": False}
    titles_str = "\n".join([f"ID: {p['id']}, Title: {p['title']}" for p in existing_pages])
    prompt = f"""
    Library check. Existing: {titles_str}. New: {new_text[:800]}.
    Output JSON: {{ "match": true, "page_id": "...", "page_title": "..." }} OR {{ "match": false }}
    """
    res = get_completion(prompt)
    return safe_json_parse(res, "Topic Match") or {"match": False}

def generate_spanish_content(text):
    print("🚀 启动 DeepSeek-R1 进行深度语言分析...")
    prompt = f"""
    You are a professional Spanish teacher. 
    Analyze and restructure the following content into a high-quality study note.
    
    Input Content:
    {text[:15000]}
    
    **Task**:
    1. Identify the core topic.
    2. Smart Formatting: Use Heading, Table, List, Text blocks.
    3. **Important**: If the text contains detailed explanations, preserve them as Text blocks. Do not summarize too much.
    
    **Output JSON Format**:
    {{
        "title": "Clear Title", 
        "category": "Grammar/Vocabulary/Reading", 
        "summary": "Chinese summary",
        "blocks": [
            {{ "type": "heading", "content": "..." }},
            {{ "type": "text", "content": "..." }},
            {{ "type": "table", "content": {{ "headers": [...], "rows": [...] }} }}
        ]
    }}
    """
    content, reasoning = get_reasoning_completion(prompt)
    if reasoning: print(f"\n🧠 [R1 思考链]:\n{reasoning[:500]}...\n")
    return safe_json_parse(content, "Spanish Content R1")

def decide_merge_strategy(new_text, structure, tables):
    prompt = f"""
    Merge Logic. Structure: {structure}. Tables: {json.dumps(tables)}. New: {new_text[:800]}
    Output JSON: {{ "action": "insert_row", "table_id": "...", "row_data": [...] }} OR {{ "action": "append_text" }}
    """
    return safe_json_parse(get_completion(prompt), "Merge Strategy") or {"action": "append_text"}

# --- 🧠 Brain C: General Logic ---
def process_general_knowledge(text):
    print("🚀 启动 DeepSeek-R1 进行深度阅读...")
    prompt = f"""
    Research Assistant. Analyze: {text[:15000]} 
    Output strictly JSON:
    {{
        "title": "Chinese Title", "summary": "Detailed Chinese Summary", "tags": ["Tag1"], "key_points": ["Point 1..."]
    }}
    """
    content, reasoning = get_reasoning_completion(prompt)
    if reasoning: print(f"\n🧠 [R1 思考链]:\n{reasoning[:500]}...\n")
    return safe_json_parse(content, "General Knowledge R1")

# --- 🎩 Main Workflow ---
def main_workflow(user_input=None, uploaded_file=None):
    processed_text = ""
    original_url = None
    
    # 1. 获取输入
    if uploaded_file:
        if not read_pdf_content: raise Exception("Missing file_ops")
        print("📂 Reading PDF...")
        processed_text = read_pdf_content(uploaded_file)
    elif user_input:
        if user_input.strip().startswith("http"):
            original_url = user_input.strip()
            print(f"🌐 Fetching URL: {original_url}")
            processed_text = fetch_url_content(original_url)
            processed_text = f"[Source] {original_url}\n{processed_text}"
        else:
            processed_text = user_input
    
    if not processed_text: raise Exception("Empty input")

    # 2. 路由
    print("🚦 Routing...")
    intent = classify_intent(processed_text)
    content_type = intent.get('type', 'Humanities')
    print(f"👉 Type: {content_type}")

    current_page_id = None 

    # 3. 处理流程
    if content_type == 'Spanish':
        print("🇪🇸 Spanish Mode...")
        existing_titles = notion_ops.get_all_page_titles(notion_ops.DB_SPANISH_ID)
        match = check_topic_match(processed_text, existing_titles)
        
        if match.get('match'):
            page_id = match.get('page_id')
            current_page_id = page_id
            print(f"💡 Merging into: {match.get('page_title')}")
            
            structure, tables = notion_ops.get_page_structure(page_id)
            if tables:
                strategy = decide_merge_strategy(processed_text, structure, tables)
                if strategy.get('action') == 'insert_row':
                    notion_ops.add_row_to_table(strategy['table_id'], strategy['row_data'])
                else:
                    data = generate_spanish_content(processed_text)
                    if data: 
                        notion_ops.append_to_page(page_id, data.get('summary'), data.get('blocks'))
                    else:
                        print("❌ 错误: 西语追加内容生成失败 (Data is None)")
            else:
                data = generate_spanish_content(processed_text)
                if data: 
                    notion_ops.append_to_page(page_id, data.get('summary'), data.get('blocks'))
                else:
                    print("❌ 错误: 西语追加内容生成失败 (Data is None)")
        else:
            print("🆕 Creating New Spanish Note...")
            data = generate_spanish_content(processed_text)
            
            # --- 诊断点 ---
            if data:
                print(f"📦 数据生成成功，标题: {data.get('title')}")
                current_page_id = notion_ops.create_study_note(data.get('title'), data.get('category', 'General'), data.get('summary'), data.get('blocks'), original_url)
            else:
                print("❌ 严重错误: 西语笔记内容生成失败 (Data is None)！")
                print("可能原因：1. R1 思考超时 2. 返回格式 JSON 解析挂了")

    else:
        # 通用模式
        if content_type == 'Tech':
            print("💻 Tech Mode Activated...")
            target_db_id = notion_ops.DB_TECH_ID
        else:
            print("🌍 Humanities Mode Activated...")
            target_db_id = notion_ops.DB_HUMANITIES_ID
        
        if not target_db_id:
            raise Exception(f"❌ Error: Database ID for {content_type} is not configured.")

        existing_titles = notion_ops.get_all_page_titles(target_db_id)
        match = check_topic_match(processed_text, existing_titles)
        
        print("🧠 Generating notes (R1)...")
        data = process_general_knowledge(processed_text)
        
        if not data: 
            print("❌ 严重错误: 通用笔记生成失败 (Data is None)")
        else:
            if match.get('match'):
                page_id = match.get('page_id')
                current_page_id = page_id
                print(f"💡 Merging into: {match.get('page_title')}")
                notion_ops.append_to_page(page_id, data.get('summary'), data.get('key_points'))
            else:
                print(f"🆕 Creating New {content_type} Note...")
                current_page_id = notion_ops.create_general_note(data, target_db_id, original_url)

    print("✅ Processing Complete!")
    return True