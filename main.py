import json
import os
from dotenv import load_dotenv
from llm_client import get_completion
from web_ops import fetch_url_content
import notion_ops

# 尝试导入 file_ops
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

# --- 🧠 Brain B: Spanish Logic ---
def check_topic_match(new_text, existing_pages):
    if not existing_pages: return {"match": False}
    titles_str = "\n".join([f"ID: {p['id']}, Title: {p['title']}" for p in existing_pages])
    prompt = f"""
    Library check. Existing: {titles_str}. New: {new_text[:800]}.
    Output JSON: {{ "match": true, "page_id": "...", "page_title": "..." }} OR {{ "match": false }}
    """
    try:
        return json.loads(get_completion(prompt).replace("```json", "").replace("```", "").strip())
    except:
        return {"match": False}

def generate_spanish_content(text):
    prompt = f"""
    Spanish Teacher Mode. Content: {text[:15000]}
    Output JSON (No Markdown):
    {{
        "title": "Title", "category": "Vocab", "summary": "Summary",
        "blocks": [
            {{ "type": "heading", "content": "1. Vocab" }},
            {{ "type": "table", "content": {{ "headers": ["ES","CN","Ex"], "rows": [["a","b","c"]] }} }}
        ]
    }}
    """
    try:
        return json.loads(get_completion(prompt).replace("```json", "").replace("```", "").strip())
    except:
        return None

def decide_merge_strategy(new_text, structure, tables):
    prompt = f"""
    Merge Logic. Structure: {structure}. Tables: {json.dumps(tables)}. New: {new_text[:1000]}
    Output JSON: {{ "action": "insert_row", "table_id": "...", "row_data": [...] }} OR {{ "action": "append_text" }}
    """
    try:
        return json.loads(get_completion(prompt).replace("```json", "").replace("```", "").strip())
    except:
        return {"action": "append_text"}

# --- 🧠 Brain C: General Logic ---
def process_general_knowledge(text):
    prompt = f"""
    Research Assistant. Analyze deeply: {text[:25000]} 
    **CRITICAL**: Be comprehensive. 8-15 key points. 100+ words each.
    Output JSON:
    {{
        "title": "Chinese Title",
        "summary": "Detailed Chinese Summary",
        "tags": ["Tag1", "Tag2"],
        "key_points": ["Point 1...", "Point 2..."]
    }}
    """
    try:
        return json.loads(get_completion(prompt).replace("```json", "").replace("```", "").strip())
    except Exception as e:
        print(f"LLM JSON Error: {e}")
        return None

# --- 🎩 Main Workflow (Strict Error Handling) ---
def main_workflow(user_input=None, uploaded_file=None):
    processed_text = ""
    original_url = None
    
    # 1. 获取输入
    if uploaded_file:
        if not read_pdf_content:
            raise Exception("❌ file_ops.py not found or failed to import.")
        
        print("📂 Reading PDF...")
        processed_text = read_pdf_content(uploaded_file)
        if not processed_text:
            # 🔥 关键修改：如果没有读到字，直接抛出异常，让 UI 变红
            raise Exception("❌ PDF is empty or unreadable (might be an image scan).")
            
    elif user_input:
        if user_input.strip().startswith("http"):
            original_url = user_input.strip()
            print(f"🌐 Fetching URL: {original_url}")
            processed_text = fetch_url_content(original_url)
            processed_text = f"[Source] {original_url}\n{processed_text}"
        else:
            processed_text = user_input
    
    if not processed_text:
        raise Exception("⚠️ No input provided.")

    # 2. 路由
    print("🚦 Routing content...")
    intent = classify_intent(processed_text)
    content_type = intent.get('type', 'General')
    print(f"👉 Type: {content_type}")

    # 3. 处理流程
    if content_type == 'Spanish':
        print("🇪🇸 Spanish Mode...")
        existing_titles = notion_ops.get_all_page_titles(notion_ops.DB_SPANISH_ID)
        match = check_topic_match(processed_text, existing_titles)
        
        if match.get('match'):
            print(f"💡 Merging into: {match.get('page_title')}")
            structure, tables = notion_ops.get_page_structure(match.get('page_id'))
            if tables:
                strategy = decide_merge_strategy(processed_text, structure, tables)
                if strategy.get('action') == 'insert_row':
                    notion_ops.add_row_to_table(strategy['table_id'], strategy['row_data'])
                    return 
            
            data = generate_spanish_content(processed_text)
            if data:
                notion_ops.append_to_page(match.get('page_id'), data.get('summary'), data.get('blocks'))
        else:
            print("🆕 Creating New Spanish Note...")
            data = generate_spanish_content(processed_text)
            if data:
                res = notion_ops.create_study_note(data.get('title'), data.get('category'), data.get('summary'), data.get('blocks'), original_url)
                if not res: raise Exception("Failed to create Notion page.")

    else:
        print("🌍 General Knowledge Mode...")
        existing_titles = notion_ops.get_all_page_titles(notion_ops.DB_GENERAL_ID)
        match = check_topic_match(processed_text, existing_titles)
        
        print("🧠 Generating notes (Deep Analysis)...")
        data = process_general_knowledge(processed_text)
        
        if not data:
            # 🔥 关键修改：LLM 生成失败也报错
            raise Exception("❌ AI failed to generate valid JSON notes.")

        if match.get('match'):
            print(f"💡 Topic Exists! Merging into: 《{match.get('page_title')}》")
            notion_ops.append_to_page(match.get('page_id'), data.get('summary'), data.get('key_points'))
        else:
            print("🆕 Creating General Note...")
            res = notion_ops.create_general_note(data, original_url)
            if not res: raise Exception("Failed to write to Notion (Check DB ID).")

    print("✅ Processing Complete!")