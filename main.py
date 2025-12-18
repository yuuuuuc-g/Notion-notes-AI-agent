import json
import os
import re
from dotenv import load_dotenv
from llm_client import get_completion, get_reasoning_completion # 导入 R1 函数
from web_ops import fetch_url_content
import notion_ops

try:
    from file_ops import read_pdf_content
except ImportError:
    read_pdf_content = None

load_dotenv()

# --- 🛠️ 核心修复：全能解析器 ---
def safe_json_parse(input_data, context=""):
    """
    带调试功能的解析器
    """
    if not input_data:
        print(f"❌ [Error] LLM returned EMPTY response for: {context}")
        return None

    if isinstance(input_data, dict):
        return input_data
    
    try:
        text = str(input_data).strip()
        clean_text = text.replace("```json", "").replace("```", "")
        start = clean_text.find("{")
        end = clean_text.rfind("}") + 1
        if start != -1 and end != -1:
            clean_text = clean_text[start:end]
            
        return json.loads(clean_text)
    except json.JSONDecodeError as e:
        print(f"❌ JSON Decode Error: {e}")
        return None
    except Exception as e:
        print(f"❌ Unknown Parse Error: {e}")
        return None

# --- 🧠 Brain A: Classifier (保持 V3，因为它够快) ---
def classify_intent(text):
    prompt = f"""
    Analyze the content type. First 800 chars: {text[:800]}
    Return JSON: {{ "type": "Spanish" }} OR {{ "type": "General" }}
    """
    res = get_completion(prompt)
    return safe_json_parse(res, "Classify") or {"type": "General"}

# --- 🧠 Brain B: Spanish Logic (升级为 R1) ---
def check_topic_match(new_text, existing_pages):
    if not existing_pages: return {"match": False}
    titles_str = "\n".join([f"ID: {p['id']}, Title: {p['title']}" for p in existing_pages])
    prompt = f"""
    Library check. Existing: {titles_str}. New: {new_text[:800]}.
    Output JSON: {{ "match": true, "page_id": "...", "page_title": "..." }} OR {{ "match": false }}
    """
    res = get_completion(prompt) # 查重比较简单，V3 够用
    return safe_json_parse(res, "Topic Match") or {"match": False}

def generate_spanish_content(text):
    """
    [R1 升级版] 使用推理模型提取西语知识
    """
    print("🚀 启动 DeepSeek-R1 进行语言分析...")
    prompt = f"""
    You are a Spanish teacher. Process this content: {text[:15000]}
    
    Output JSON (No Markdown):
    {{
        "title": "Title", 
        "category": "Vocab", 
        "summary": "Summary",
        "blocks": [
            {{ "type": "heading", "content": "1. Vocab" }},
            {{ "type": "table", "content": {{ "headers": ["ES","CN","Ex"], "rows": [["a","b","c"]] }} }}
        ]
    }}
    """
    # 🌟 调用 R1
    content, reasoning = get_reasoning_completion(prompt)
    
    # 打印思考过程 (可选：如果你想看它在想什么)
    print(f"\n🧠 [R1 思考链]:\n{reasoning[:500]}...\n")
    
    return safe_json_parse(content, "Spanish Content R1")

def decide_merge_strategy(new_text, structure, tables):
    prompt = f"""
    Merge Logic. Structure: {structure}. Tables: {json.dumps(tables)}. New: {new_text[:800]}
    Output JSON: {{ "action": "insert_row", "table_id": "...", "row_data": [...] }} OR {{ "action": "append_text" }}
    """
    return safe_json_parse(get_completion(prompt), "Merge Strategy") or {"action": "append_text"}

# --- 🧠 Brain C: General Logic (升级为 R1) ---
def process_general_knowledge(text):
    """
    [R1 升级版] 使用推理模型进行深度阅读
    """
    print("🚀 启动 DeepSeek-R1 进行深度阅读...")
    prompt = f"""
    You are a professional research assistant. 
    Analyze the following content deeply: 
    {text[:12000]} 
    
    **CRITICAL INSTRUCTION**: 
    1. Output strictly valid JSON.
    2. Do NOT summarize too briefly. 
    
    JSON Format:
    {{
        "title": "Chinese Title",
        "summary": "Chinese Summary (Detailed)",
        "tags": ["Tag1", "Tag2"],
        "key_points": [
            "Point 1: Detailed explanation...",
            "Point 2: Detailed explanation..."
        ]
    }}
    """
    
    # 🌟 调用 R1
    content, reasoning = get_reasoning_completion(prompt)
    
    print(f"\n🧠 [R1 思考链]:\n{reasoning[:500]}...\n")
    
    return safe_json_parse(content, "General Knowledge R1")

# --- 🎩 Main Workflow ---
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
            raise Exception("❌ PDF is empty or unreadable.")
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
                res = notion_ops.create_study_note(data.get('title'), data.get('category', 'General'), data.get('summary'), data.get('blocks'), original_url)
                if not res: raise Exception("Failed to create Notion page.")

    else:
        print("🌍 General Knowledge Mode...")
        existing_titles = notion_ops.get_all_page_titles(notion_ops.DB_GENERAL_ID)
        match = check_topic_match(processed_text, existing_titles)
        
        print("🧠 Generating notes (Deep Analysis)...")
        data = process_general_knowledge(processed_text)
        
        if not data:
            raise Exception("❌ AI failed to generate valid JSON notes.")

        if match.get('match'):
            print(f"💡 Topic Exists! Merging into: 《{match.get('page_title')}》")
            notion_ops.append_to_page(match.get('page_id'), data.get('summary'), data.get('key_points'))
        else:
            print("🆕 Creating General Note...")
            res = notion_ops.create_general_note(data, original_url)
            if not res: raise Exception("Failed to write to Notion (Check DB ID).")

    print("✅ Processing Complete!")
    