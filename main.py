import json
import os
from dotenv import load_dotenv
from llm_client import get_completion
from web_ops import fetch_url_content
import notion_ops  # 导入完全体的 notion_ops

try:
    from file_ops import read_pdf_content
except ImportError:
    read_pdf_content = None

load_dotenv()

# --- 🧠 Brain A: Classifier ---
def classify_intent(text):
    prompt = f"""
    Analyze the content type. First 800 chars: {text[:800]}
    Return JSON: {{ "type": "Spanish" }} OR {{ "type": "General" }}
    """
    response = get_completion(prompt)
    if "Spanish" in response: return {"type": "Spanish"}
    return {"type": "General"}

# --- 🧠 Brain B: Spanish Logic (找回了高级 Prompt) ---
def check_topic_match(new_text, existing_pages):
    """查重逻辑"""
    titles_str = "\n".join([f"ID: {p['id']}, Title: {p['title']}" for p in existing_pages])
    prompt = f"""
    Library check.
    Existing Notes: {titles_str}
    New Content: {new_text[:800]}
    Check if topic exists.
    Output JSON: {{ "match": true, "page_id": "...", "page_title": "..." }} OR {{ "match": false }}
    """
    try:
        # 直接解析，不使用 parse_json 包装
        return json.loads(get_completion(prompt).replace("```json", "").replace("```", "").strip())
    except:
        return {"match": False}

def generate_spanish_content(text):
    """
    生成包含表格、列表的复杂西语笔记
    """
    prompt = f"""
    You are a Spanish teacher. Process this content: {text[:15000]}
    
    Output JSON with this structure (No Markdown code blocks):
    {{
        "title": "Note Title",
        "category": "Vocabulary/Listening/Grammar",
        "summary": "Chinese summary",
        "blocks": [
            {{ "type": "heading", "content": "1. Core Vocabulary" }},
            {{ 
                "type": "table", 
                "content": {{
                    "headers": ["Spanish", "Chinese", "Example"],
                    "rows": [
                        ["Word1", "Meaning1", "Ex1"],
                        ["Word2", "Meaning2", "Ex2"]
                    ]
                }}
            }},
            {{ "type": "heading", "content": "2. Key Sentences" }},
            {{ "type": "list", "content": ["Sentence 1", "Sentence 2"] }}
        ]
    }}
    """
    response = get_completion(prompt)
    clean_json = response.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(clean_json)
    except:
        return None

def decide_merge_strategy(new_text, structure_text, tables):
    """决策：是插入表格还是追加文本"""
    prompt = f"""
    Editor logic.
    Structure: {structure_text}
    Tables: {json.dumps(tables)}
    New Content: {new_text[:1000]}
    Output JSON: {{ "action": "insert_row", "table_id": "...", "row_data": ["Col1", "Col2", "Col3"] }} OR {{ "action": "append_text" }}
    """
    try:
        return json.loads(get_completion(prompt).replace("```json", "").replace("```", "").strip())
    except:
        return {"action": "append_text"}

# --- 🧠 Brain C: General Logic ---
def process_general_knowledge(text):
    prompt = f"""
    Knowledge Assistant. Analyze: {text[:15000]} 
    Output strictly JSON:
    {{
        "title": "Chinese Title",
        "summary": "Chinese Summary (200 words)",
        "tags": ["Tag1", "Tag2"],
        "key_points": ["Point 1 (50 words)", "Point 2", "Point 3"]
    }}
    """
    response = get_completion(prompt)
    clean_json = response.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(clean_json)
    except:
        return None

# --- 🎩 Main Workflow (完全体逻辑) ---
def main_workflow(user_input=None, uploaded_file=None):
    processed_text = ""
    original_url = None
    
    # 1. 获取输入
    if uploaded_file and read_pdf_content:
        print("📂 File detected...")
        processed_text = read_pdf_content(uploaded_file)
    elif user_input:
        if user_input.strip().startswith("http"):
            original_url = user_input.strip()
            print(f"🌐 Fetching URL: {original_url}")
            processed_text = fetch_url_content(original_url)
            processed_text = f"[Source] {original_url}\n{processed_text}"
        else:
            processed_text = user_input
    
    if not processed_text:
        print("⚠️ Empty input")
        return

    # 2. 路由
    print("🚦 Routing content...")
    intent = classify_intent(processed_text)
    content_type = intent.get('type', 'General')
    print(f"👉 Type: {content_type}")

    # 3. 处理流程
    if content_type == 'Spanish':
        print("🇪🇸 Spanish Mode Activated...")
        # A. 查重 (功能恢复!)
        # ⚠️ 注意: 确保 notion_ops.py 里有 get_all_page_titles
        existing_titles = notion_ops.get_all_page_titles(notion_ops.DB_SPANISH_ID)
        match = check_topic_match(processed_text, existing_titles)
        
        if match.get('match'):
            # B. 合并逻辑 (功能恢复!)
            page_id = match.get('page_id')
            title = match.get('page_title')
            print(f"💡 Merging with existing note: {title}")
            
            structure, tables = notion_ops.get_page_structure(page_id)
            if tables:
                strategy = decide_merge_strategy(processed_text, structure, tables)
                if strategy.get('action') == 'insert_row':
                    notion_ops.add_row_to_table(strategy['table_id'], strategy['row_data'])
                    return # 结束
            
            # 追加模式
            data = generate_spanish_content(processed_text)
            if data:
                notion_ops.append_to_page(page_id, data.get('summary'), data.get('blocks'))
        else:
            # C. 新建逻辑
            print("🆕 Creating New Spanish Note...")
            data = generate_spanish_content(processed_text)
            if data:
                notion_ops.create_study_note(
                    data.get('title'),
                    data.get('category', 'General'),
                    data.get('summary'),
                    data.get('blocks'), # 传入复杂 blocks
                    original_url
                )

    else:
        print("🌍 General Knowledge Mode...")
        # 通用模式逻辑
        data = process_general_knowledge(processed_text)
        if data:
            # 这里的 create_general_note 会调用 notion_ops 里升级过的 build_content_blocks
            notion_ops.create_general_note(data, original_url)

    print("✅ Processing Complete!")