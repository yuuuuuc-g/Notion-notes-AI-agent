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

# --- 🧠 Brain B: Spanish Logic ---
def check_topic_match(new_text, existing_pages):
    """查重逻辑 (通用)"""
    if not existing_pages:
        return {"match": False}
        
    titles_str = "\n".join([f"ID: {p['id']}, Title: {p['title']}" for p in existing_pages])
    prompt = f"""
    Library check.
    Existing Notes: {titles_str}
    New Content: {new_text[:800]}
    
    Task: Check if the new content belongs to an existing topic/book/note.
    Output JSON: {{ "match": true, "page_id": "...", "page_title": "..." }} OR {{ "match": false }}
    """
    try:
        # 直接解析，不使用 parse_json 包装
        return json.loads(get_completion(prompt).replace("```json", "").replace("```", "").strip())
    except:
        return {"match": False}

def generate_spanish_content(text):
    """
    西语模式：保持结构化输出
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
    """决策：西语表格合并策略"""
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

# --- 🧠 Brain C: General Logic (已增强：详尽模式) ---
def process_general_knowledge(text):
    """
    通用模式：大幅增加了提取的详细程度
    """
    prompt = f"""
    You are a professional research assistant. 
    Analyze the following content deeply: {text[:20000]} 
    
    **CRITICAL INSTRUCTION**: 
    Do NOT summarize too briefly. I need detailed, comprehensive notes.
    Capture ALL the nuance, logic, and technical details from the source.
    
    Output strictly JSON:
    {{
        "title": "Chinese Title (Clear & Professional)",
        "summary": "Chinese Summary (300-500 words). Be detailed. Cover the context, problem, and solution.",
        "tags": ["Tag1", "Tag2", "Tag3"],
        "key_points": [
            "Point 1: Detailed explanation (100+ words) of the first key concept...",
            "Point 2: Detailed explanation of the second concept...",
            ... (Extract 8-15 key points. Be exhaustive.)
        ]
    }}
    """
    response = get_completion(prompt)
    clean_json = response.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(clean_json)
    except:
        return None

# --- 🎩 Main Workflow (Pro版：双向查重) ---
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
        # A. 查重 (西语库)
        existing_titles = notion_ops.get_all_page_titles(notion_ops.DB_SPANISH_ID)
        match = check_topic_match(processed_text, existing_titles)
        
        if match.get('match'):
            # B. 合并逻辑
            page_id = match.get('page_id')
            title = match.get('page_title')
            print(f"💡 Merging with existing note: {title}")
            
            structure, tables = notion_ops.get_page_structure(page_id)
            if tables:
                strategy = decide_merge_strategy(processed_text, structure, tables)
                if strategy.get('action') == 'insert_row':
                    notion_ops.add_row_to_table(strategy['table_id'], strategy['row_data'])
                    return 
            
            # 追加文本
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
                    data.get('blocks'), 
                    original_url
                )

    else:
        print("🌍 General Knowledge Mode...")
        
        # === ✨ 新增功能：通用模式查重 ===
        # 1. 获取通用库的所有标题
        existing_titles = notion_ops.get_all_page_titles(notion_ops.DB_GENERAL_ID)
        
        # 2. 检查是否重复
        match = check_topic_match(processed_text, existing_titles)
        
        # 3. 生成内容 (现在是详尽版)
        print("🧠 Generating comprehensive notes...")
        data = process_general_knowledge(processed_text)
        
        if not data:
            print("❌ Content generation failed.")
            return

        if match.get('match'):
            # === 命中重复：追加内容 ===
            page_id = match.get('page_id')
            title = match.get('page_title')
            print(f"💡 Topic Exists! Merging into: 《{title}》")
            
            # 调用 append_to_page (notion_ops 会自动处理 list 类型的 key_points)
            notion_ops.append_to_page(
                page_id, 
                data.get('summary'), 
                data.get('key_points') # 这里传入的是字符串列表
            )
        else:
            # === 无重复：新建页面 ===
            print("🆕 Topic is new. Creating General Note...")
            notion_ops.create_general_note(data, original_url)

    print("✅ Processing Complete!")