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
        """感知输入"""
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
        """意图分类 (3元)"""
        prompt = f"""
        Analyze content type. First 800 chars: {text[:800]}
        Return JSON with "type":
        1. "Spanish": Language learning (Grammar, Vocab, Spanish videos).
        2. "Tech": AI, Coding, Engineering, Software, Hard Science.
        3. "Humanities": Politics, Economy, History, Philosophy, Social Science, News.
        
        JSON Example: {{ "type": "Tech" }}
        """
        res = get_completion(prompt)
        return safe_json_parse(res, "Classify") or {"type": "Humanities"}

    def consult_memory(self, text):
        """查询向量记忆"""
        print("🧠 Researcher: Consulting Knowledge Base (Vector Search)...")
        return vector_ops.search_memory(text[:1000])

    def draft_content(self, text, intent_type):
        """撰写草稿 (核心大脑)"""
        
        # === 西语模式 ===
        if intent_type == 'Spanish':
            print("🚀 Researcher: Drafting Spanish content (R1)...")
            prompt = f"""
            You are a Spanish teacher. Process content: {text[:10000]}
            
            Output JSON (No Markdown):
            {{
                "title": "Title", "category": "Vocab", "summary": "Summary",
                "blocks": [
                    {{ "type": "heading", "content": "1. Vocab" }},
                    {{ "type": "table", "content": {{ "headers": ["ES","CN","Ex"], "rows": [["a","b","c"]] }} }}
                ]
            }}
            """
            content, _ = get_reasoning_completion(prompt)
            return safe_json_parse(content, "Spanish Draft")
            
        # === 通用模式 (Tech / Humanities) ===
        else:
            print("🚀 Researcher: Drafting General content (R1 - Enhanced)...")
            # ⚠️ 这里使用了增强版的 Prompt，要求返回 blocks 而不仅是 key_points
            prompt = f"""
            You are a professional Tech/Research Editor. 
            Analyze and restructure the content: {text[:12000]} 
            
            **Task**:
            1. Create a descriptive Title.
            2. Write a detailed Summary.
            3. **Reconstruct content**: Convert lists to "list" blocks, comparisons to "table" blocks, code explanation to "text".
            
            **Output JSON Format**:
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
        """决策合并策略"""
        structure_text, tables = notion_ops.get_page_structure(existing_page_id)
        if not tables: return {"action": "append_text"}

        prompt = f"""
        Editor Logic. Structure: {structure_text}. Tables: {json.dumps(tables)}. New: {new_text[:800]}
        Output JSON: {{ "action": "insert_row", "table_id": "...", "row_data": [...] }} OR {{ "action": "append_text" }}
        """
        return safe_json_parse(get_completion(prompt), "Merge Decision") or {"action": "append_text"}

    def publish(self, draft, intent_type, memory_match, raw_text, original_url=None):
        """发布到 Notion"""
        if not draft:
            print("❌ Editor: Draft is empty.")
            return False

        page_title = draft.get('title', 'Untitled')
        page_id = None
        
        # 为了兼容通用模式生成的 blocks (有时候 AI 会忘了给 blocks，只给 key_points)
        # 这里做一个简单的兼容处理
        blocks = draft.get('blocks') or draft.get('key_points', [])

        # === A. 合并逻辑 (Merge) ===
        if memory_match.get('match'):
            existing_id = memory_match['page_id']
            print(f"💡 Editor: Merging into: 《{memory_match['title']}》")
            
            # 只有西语模式才尝试表格插入，通用模式直接追加
            if intent_type == 'Spanish':
                strategy = self.decide_merge(raw_text, existing_id)
                if strategy.get('action') == 'insert_row':
                    notion_ops.add_row_to_table(strategy['table_id'], strategy['row_data'])
                    return True 
            
            # 通用追加
            notion_ops.append_to_page(existing_id, draft.get('summary'), blocks)
            page_id = existing_id

        # === B. 新建逻辑 (Create) ===
        else:
            print(f"🆕 Editor: Publishing new: 《{page_title}》")
            
            if intent_type == 'Spanish':
                page_id = notion_ops.create_study_note(
                    draft.get('title'), 
                    draft.get('category', 'General'), 
                    draft.get('summary'), 
                    blocks, 
                    original_url
                )
            else:
                # 路由数据库
                target_db = notion_ops.DB_TECH_ID if intent_type == 'Tech' else notion_ops.DB_HUMANITIES_ID
                
                # 调用 notion_ops (注意：create_general_note 已经在 notion_ops 升级为支持 blocks 了)
                page_id = notion_ops.create_general_note(draft, target_db, original_url)

        # === C. 记忆归档 ===
        if page_id:
            print("🧠 Editor: Archiving to Vector Memory...")
            vector_ops.add_memory(page_id, raw_text[:2000], page_title, intent_type)
            return True
        
        return False