import json
from llm_client import get_completion, get_reasoning_completion
from web_ops import fetch_url_content
import notion_ops
import vector_ops 

try:
    from file_ops import read_pdf_content
except ImportError:
    read_pdf_content = None

# --- 🛠️ 基础工具 ---
def safe_json_parse(input_data, context=""):
    if not input_data: return None
    if isinstance(input_data, dict): return input_data
    try:
        text = str(input_data).strip()
        clean_text = text.replace("```json", "").replace("```", "")
        start = clean_text.find("{")
        end = clean_text.rfind("}") + 1
        if start != -1 and end != -1: clean_text = clean_text[start:end]
        return json.loads(clean_text)
    except Exception as e:
        print(f"❌ [{context}] JSON Parse Error: {e}")
        return None

# ==========================================
# 🕵️‍♂️ Agent 1: 研究员 (The Researcher)
# ==========================================
class ResearcherAgent:
    def __init__(self):
        print("🕵️‍♂️ Researcher Agent initialized.")

    def perceive(self, user_input=None, uploaded_file=None):
        if uploaded_file:
            if not read_pdf_content: raise Exception("Missing file_ops")
            print("📂 Researcher: Reading PDF...")
            return read_pdf_content(uploaded_file), None
        elif user_input:
            if user_input.strip().startswith("http"):
                url = user_input.strip()
                print(f"🌐 Researcher: Fetching URL {url}...")
                content = fetch_url_content(url)
                return f"[Source] {url}\n{content}", url
            return user_input, None
        return None, None

    def analyze_intent(self, text):
        prompt = f"""
        Analyze content type. First 800 chars: {text[:800]}
        Return JSON with "type":
        1. "Spanish": Language learning (Grammar, Vocab, Spanish videos).
        2. "Tech": AI, Coding, Engineering, Software, Hard Science.
        3. "Humanities": Politics, Economy, History, Philosophy, Social Science, News.
        """
        res = get_completion(prompt)
        return safe_json_parse(res, "Classify") or {"type": "Humanities"}

    def consult_memory(self, text):
        print("🧠 Researcher: Consulting Knowledge Base (Vector Search)...")
        return vector_ops.search_memory(text[:1000])

    def draft_content(self, text, intent_type):
        if intent_type == 'Spanish':
            print("🚀 Researcher: Drafting Spanish content (R1)...")
            prompt = f"""
            You are a Spanish teacher. Process content: {text[:10000]}
            Output JSON (No Markdown):
            {{
                "title": "Title", "category": "Vocab/Grammar", "summary": "Summary",
                "blocks": [
                    {{ "type": "heading", "content": "1. Vocab" }},
                    {{ "type": "table", "content": {{ "headers": ["ES","CN","Ex"], "rows": [["a","b","c"]] }} }}
                ]
            }}
            """
            content, _ = get_reasoning_completion(prompt)
            return safe_json_parse(content, "Spanish Draft")
        else:
            print("🚀 Researcher: Drafting General content (R1 - Enhanced)...")
            prompt = f"""
            You are a professional Tech/Research Editor. 
            Analyze and restructure the content: {text[:12000]} 
            Output JSON Format:
            {{
                "title": "Article Title",
                "summary": "Detailed Summary",
                "tags": ["Tag1", "Tag2"],
                "blocks": [
                    {{ "type": "heading", "content": "1. Introduction" }},
                    {{ "type": "text", "content": "Detailed explanation..." }},
                    {{ "type": "list", "content": ["Point A", "Point B"] }}
                ]
            }}
            """
            content, _ = get_reasoning_completion(prompt)
            return safe_json_parse(content, "General Draft")

# ==========================================
# ✍️ Agent 2: 主编 (The Editor)
# ==========================================
class EditorAgent:
    def __init__(self):
        print("✍️ Editor Agent initialized.")

    def decide_merge(self, new_text, existing_page_id):
        structure_text, tables = notion_ops.get_page_structure(existing_page_id)
        if not tables: return {"action": "append_text"}
        prompt = f"""
        Editor Logic. Structure: {structure_text}. Tables: {json.dumps(tables)}. New: {new_text[:800]}
        Output JSON: {{ "action": "insert_row", "table_id": "...", "row_data": [...] }} OR {{ "action": "append_text" }}
        """
        return safe_json_parse(get_completion(prompt), "Merge Decision") or {"action": "append_text"}

    def publish(self, draft, intent_type, memory_match, raw_text, original_url=None):
        if not draft:
            print("❌ Editor: Draft is empty.")
            return False

        page_title = draft.get('title', 'Untitled')
        page_id = None
        merge_success = False

        # === 尝试合并 (Merge Attempt) ===
        if memory_match.get('match'):
            existing_id = memory_match['page_id']
            existing_title = memory_match['title']
            print(f"💡 Editor: Merging into existing record: 《{existing_title}》")
            
            # 尝试执行合并操作
            if intent_type == 'Spanish':
                strategy = self.decide_merge(raw_text, existing_id)
                if strategy.get('action') == 'insert_row':
                    merge_success = notion_ops.add_row_to_table(strategy['table_id'], strategy['row_data'])
                else:
                    merge_success = notion_ops.append_to_page(existing_id, draft.get('summary'), draft.get('blocks'))
            else:
                # 通用模式合并
                # 兼容 key_points 和 blocks
                blocks = draft.get('blocks') or draft.get('key_points', [])
                merge_success = notion_ops.append_to_page(existing_id, draft.get('summary'), blocks)
            
            if merge_success:
                page_id = existing_id
            else:
                print("⚠️ Editor: Merge failed (Page might be deleted). Switching to CREATE mode...")
                # 如果合并失败，merge_success 为 False，会自动流转到下面的新建逻辑

        # === 新建逻辑 (Create) - 只要没合并成功，就新建 ===
        if not page_id: # 如果上面没拿到 ID (合并失败或本来就是新主题)
            print(f"🆕 Editor: Publishing new edition: 《{page_title}》")
            blocks = draft.get('blocks') or draft.get('key_points', [])
            
            if intent_type == 'Spanish':
                page_id = notion_ops.create_study_note(
                    page_title, 
                    draft.get('category', 'General'), 
                    draft.get('summary'), 
                    blocks, 
                    original_url
                )
            else:
                target_db = notion_ops.DB_TECH_ID if intent_type == 'Tech' else notion_ops.DB_HUMANITIES_ID
                page_id = notion_ops.create_general_note(draft, target_db, original_url)

        # === 记忆归档 ===
        if page_id:
            print("🧠 Editor: Archiving to Vector Memory...")
            vector_ops.add_memory(page_id, raw_text[:2000], page_title, intent_type)
            return True
        
        return False