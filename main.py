import json
import os
import re
from dotenv import load_dotenv
from llm_client import get_completion, get_reasoning_completion
from web_ops import fetch_url_content
import notion_ops
import podcast_ops 

try:
    from file_ops import read_pdf_content
except ImportError:
    read_pdf_content = None

load_dotenv()

# --- 🛠️ 核心修复：全能解析器 ---
def safe_json_parse(input_data, context=""):
    if not input_data:
        print(f"❌ [Error] LLM returned EMPTY response for: {context}")
        return None
    if isinstance(input_data, dict): return input_data
    try:
        text = str(input_data).strip()
        clean_text = text.replace("```json", "").replace("```", "")
        start = clean_text.find("{")
        end = clean_text.rfind("}") + 1
        if start != -1 and end != -1: clean_text = clean_text[start:end]
        return json.loads(clean_text)
    except Exception as e:
        print(f"❌ Parse Error: {e}")
        return None

# --- 🧠 Brain A: Classifier ---
def classify_intent(text):
    prompt = f"""
    Analyze the language and content type. First 800 chars: {text[:800]}
    
    Return JSON: {{ "type": "Spanish" }} OR {{ "type": "General" }}
    
    Logic:
    1. **Spanish**: Any text written in Spanish language, OR content about learning Spanish.
    2. **General**: Text written in English/Chinese about Tech, News, etc.
    """
    res = get_completion(prompt)
    return safe_json_parse(res, "Classify") or {"type": "General"}

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
    print("🚀 启动 DeepSeek-R1 进行语言分析...")
    prompt = f"""
    You are a Spanish expert. Process this content: {text[:15000]}
    
    The content might be a complex article.
    1. Summarize it in Chinese.
    2. Extract key Spanish vocabulary/expressions (even if it's advanced).
    3. Extract 2-3 key sentences (quotes).
    
    Output JSON (No Markdown):
    {{
        "title": "Article Title", 
        "category": "Reading", 
        "summary": "Summary",
        "blocks": [
            {{ "type": "heading", "content": "1. Core Expressions" }},
            {{ "type": "table", "content": {{ "headers": ["Spanish","Chinese","Context"], "rows": [["Word","Meaning","Context"]] }} }}
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
        "title": "Chinese Title", "summary": "Chinese Summary", "tags": ["Tag1"], "key_points": ["Point 1..."]
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
    content_type = intent.get('type', 'General')
    print(f"👉 Type: {content_type}")

    current_page_id = None 

    # 3. 处理流程
    if content_type == 'Spanish':
        print("🇪🇸 Spanish Mode...")
        existing_titles = notion_ops.get_all_page_titles(notion_ops.DB_SPANISH_ID)
        match = check_topic_match(processed_text, existing_titles)
        
        if match.get('match'):
            page_id = match.get('page_id')
            current_page_id = page_id # ✅ 记录 ID
            print(f"💡 Merging into: {match.get('page_title')}")
            
            structure, tables = notion_ops.get_page_structure(page_id)
            if tables:
                strategy = decide_merge_strategy(processed_text, structure, tables)
                if strategy.get('action') == 'insert_row':
                    notion_ops.add_row_to_table(strategy['table_id'], strategy['row_data'])
                else:
                    data = generate_spanish_content(processed_text)
                    if data: notion_ops.append_to_page(page_id, data.get('summary'), data.get('blocks'))
            else:
                data = generate_spanish_content(processed_text)
                if data: notion_ops.append_to_page(page_id, data.get('summary'), data.get('blocks'))
        else:
            print("🆕 Creating New Spanish Note...")
            data = generate_spanish_content(processed_text)
            if data:
                # ✅ 这里接收返回值 ID
                current_page_id = notion_ops.create_study_note(data.get('title'), data.get('category', 'General'), data.get('summary'), data.get('blocks'), original_url)

    else:
        print("🌍 General Knowledge Mode...")
        existing_titles = notion_ops.get_all_page_titles(notion_ops.DB_GENERAL_ID)
        match = check_topic_match(processed_text, existing_titles)
        
        print("🧠 Generating notes (R1)...")
        data = process_general_knowledge(processed_text)
        
        if not data: raise Exception("AI failed.")

        if match.get('match'):
            page_id = match.get('page_id')
            current_page_id = page_id # ✅ 记录 ID
            print(f"💡 Merging into: {match.get('page_title')}")
            notion_ops.append_to_page(page_id, data.get('summary'), data.get('key_points'))
        else:
            print("🆕 Creating General Note...")
            # ✅ 这里接收返回值 ID
            current_page_id = notion_ops.create_general_note(data, original_url)

    # === 🎙️ 4. 播客生成 (按需开启) ===
    audio_file = None
    
    # 🌟 核心判断逻辑：
    # 1. 必须有写入成功的页面 (current_page_id)
    # 2. 必须是西语模式 (content_type == 'Spanish')
    # 3. 必须不是 PDF (not uploaded_file)
    # 4. 必须不是 URL (not original_url)
    should_generate_podcast = (
        current_page_id 
        and content_type == 'Spanish' 
        and not uploaded_file 
        and not original_url
    )

    if should_generate_podcast:
        print("🎙️ Generating Podcast for Spanish text...")
        # 传入原始文本
        script, audio_file = podcast_ops.run_podcast_workflow(processed_text)
        
        if script:
            # 追加到 Notion
            notion_ops.append_podcast_script(current_page_id, script)
    else:
        if content_type == 'Spanish':
            if uploaded_file or original_url:
                print("🔇 Skipping podcast (File/URL input)")
            elif not current_page_id:
                print("🔇 Skipping podcast (Notion write failed)")
        else:
            print("🔇 Skipping podcast (Not Spanish content)")
    
    print("✅ Processing Complete!")
    return audio_file