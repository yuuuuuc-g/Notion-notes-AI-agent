import json
import os
import re
from dotenv import load_dotenv
from llm_client import get_completion, get_reasoning_completion
from web_ops import fetch_url_content
import notion_ops
# 🌟 引入新的向量模块
import vector_ops 

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
    Analyze the content type. First 800 chars: {text[:800]}
    Return JSON with "type":
    1. "Spanish": Language learning (Grammar, Vocab, Spanish videos).
    2. "Tech": AI, Coding, Engineering, Software, Hard Science.
    3. "Humanities": Politics, Economy, History, Philosophy, Social Science, News, Culture.
    """
    res = get_completion(prompt)
    return safe_json_parse(res, "Classify") or {"type": "Humanities"}

# --- 🧠 Brain B: Spanish Logic ---

# 🌟 [移除] 旧的 check_topic_match 函数 (LLM版)
# 🌟 [新增] 我们现在直接在 main_workflow 里调用 vector_ops.search_memory

def generate_spanish_content(text):
    print("🚀 启动 DeepSeek-R1 进行语言分析...")
    prompt = f"""
    You are a Spanish expert. Process this content: {text[:10000]}
    
    Output JSON (No Markdown):
    {{
        "title": "Note Title", 
        "category": "Vocab", 
        "summary": "Summary",
        "blocks": [
            {{ "type": "heading", "content": "1. Vocab" }},
            {{ "type": "table", "content": {{ "headers": ["ES","CN","Ex"], "rows": [["a","b","c"]] }} }}
        ]
    }}
    """
    content, reasoning = get_reasoning_completion(prompt)
    if reasoning: print(f"\n🧠 [R1 思考链]:\n{reasoning[:200]}...\n")
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
        "title": "Chinese Title", "summary": "Summary", "tags": ["Tag1"], "key_points": ["Point 1..."]
    }}
    """
    content, reasoning = get_reasoning_completion(prompt)
    if reasoning: print(f"\n🧠 [R1 思考链]:\n{reasoning[:200]}...\n")
    return safe_json_parse(content, "General Knowledge R1")

# --- 🎩 Main Workflow ---
def main_workflow(user_input=None, uploaded_file=None):
    processed_text = ""
    original_url = None
    
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

    print("🚦 Routing...")
    intent = classify_intent(processed_text)
    content_type = intent.get('type', 'General')
    print(f"👉 Type: {content_type}")

    current_page_id = None 

    # === 🌟 向量查重 (Vector Retrieval) ===
    # 不再每次去 Notion 遍历所有标题，而是查本地向量库，毫秒级响应
    print("🧠 Searching Knowledge Base (Vector)...")
    
    # 搜索最相似的1条
    vector_match = vector_ops.search_memory(processed_text[:1000])
    
    if vector_match['match']:
        # === 命中旧笔记 ===
        print(f"💡 Vector Hit! Merging into: 《{vector_match['title']}》")
        page_id = vector_match['page_id']
        current_page_id = page_id
        
        # 无论是西语还是通用，只要命中了，逻辑类似
        if content_type == 'Spanish':
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
            # 通用模式合并
            data = process_general_knowledge(processed_text)
            if data: notion_ops.append_to_page(page_id, data.get('summary'), data.get('key_points'))
            
    else:
        # === 新主题 (Vector Miss) ===
        print("🆕 New Topic Detected. Processing...")
        
        if content_type == 'Spanish':
            data = generate_spanish_content(processed_text)
            if data:
                current_page_id = notion_ops.create_study_note(
                    data.get('title'), 
                    data.get('category', 'General'), 
                    data.get('summary'), 
                    data.get('blocks'), 
                    original_url
                )
                # 🌟 关键：新建成功后，存入向量库
                if current_page_id:
                    vector_ops.add_memory(current_page_id, processed_text[:2000], data.get('title'), "Spanish")
        else:
            # 通用模式
            target_db_id = notion_ops.DB_TECH_ID if content_type == 'Tech' else notion_ops.DB_HUMANITIES_ID
            data = process_general_knowledge(processed_text)
            if data:
                current_page_id = notion_ops.create_general_note(data, target_db_id, original_url)
                # 🌟 关键：新建成功后，存入向量库
                if current_page_id:
                    # 对于通用知识，存摘要可能比存全文更准，这里先存前2000字
                    vector_ops.add_memory(current_page_id, processed_text[:2000], data.get('title'), content_type)

    print("✅ Processing Complete!")
    return True