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

    def consult_memory(self, text, domain=None):
        print(f"🧠 Researcher: Consulting Memory (Domain: {domain})...")
        return vector_ops.search_memory(text[:1000], category_filter=domain)

    def draft_content(self, text, intent_type, error_context=""):
        error_instruction = ""
        if error_context:
            error_instruction = f"PREVIOUS ERROR: {error_context}. Please fix JSON format."

        if intent_type == 'Spanish':
            print("🚀 Researcher: Drafting Spanish content (R1)...")
            prompt = f"""
            You are a professional Spanish teacher. 
            Analyze and restructure the following content into a high-quality study note.
            Input Content: {text[:12000]}
            {error_instruction}
            
            【Formatting Rules】
            1. **Smart Table**: Comparisons -> Table.
            2. **Smart List**: Enumeration -> List.
            3. **Preserve Context**: Keep detailed explanations.
            
            Output JSON:
            {{
                "title": "Title", "category": "Grammar/Vocab", "summary": "Summary",
                "blocks": [
                    {{ "type": "heading", "content": "1. Concept" }},
                    {{ "type": "table", "content": {{ "headers": ["ES","CN"], "rows": [["a","b"]] }} }}
                ]
            }}
            """
            content, _ = get_reasoning_completion(prompt)
            return safe_json_parse(content, "Spanish Draft")
        else:
            print("🚀 Researcher: Drafting General content (R1)...")
            prompt = f"""
            You are a Tech/Research Editor. Analyze: {text[:15000]} 
            {error_instruction}
            
            Output JSON:
            {{
                "title": "Title", "summary": "Summary", "tags": ["Tag"],
                "blocks": [
                    {{ "type": "heading", "content": "Intro" }},
                    {{ "type": "text", "content": "Details..." }},
                    {{ "type": "list", "content": ["Point A"] }}
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

    def publish(self, draft, intent_type, memory_match, raw_text, original_url=None, database_id=None, domain=None):
        """
        执行发布流程
        domain: 用户在界面上手动选择的分类 (priority: High)
        intent_type: AI 自动判断的分类 (priority: Low)
        """
        if not draft:
            print("❌ Editor: Draft is empty.")
            return False

        page_title = draft.get('title', 'Untitled')
        page_id = None
        
        # 统一获取 blocks
        blocks = draft.get('blocks') or draft.get('key_points', [])

        # =========================================================
        # 1. 🎯 核心修复：确定目标数据库 ID (Target Database Resolution)
        # =========================================================
        target_db_id = None
        
        # 逻辑：如果有人工指定的 domain，优先使用 domain 对应的数据库
        # 如果没有 domain，再使用 AI 判断的 intent_type
        
        # 归一化决策依据
        decision_source = domain if domain else intent_type
        
        # 映射到具体 ID
        if decision_source in ['Spanish', 'spanish_learning', 'Language']:
            target_db_id = notion_ops.DB_SPANISH_ID
            print(f"📦 Editor: Routing to [SPANISH] DB (Source: {decision_source})")
        elif decision_source in ['Tech', 'tech_knowledge', 'AI', 'Science']:
            target_db_id = notion_ops.DB_TECH_ID
            print(f"📦 Editor: Routing to [TECH] DB (Source: {decision_source})")
        else:
            # 默认为社科/Humanities
            target_db_id = notion_ops.DB_HUMANITIES_ID
            print(f"📦 Editor: Routing to [HUMANITIES] DB (Source: {decision_source})")

        # 兜底：如果外部直接传了 database_id (比如人工 review 指定了 ID)
        if database_id:
            target_db_id = database_id
            print(f"📦 Editor: Routing to [MANUAL OVERRIDE] ID: {database_id}")

        if not target_db_id:
            print("❌ Error: Could not resolve Target DB ID.")
            return False

        # =========================================================
        # 2. 查重与合并逻辑 (Merge Logic)
        # =========================================================
        
        # 只有当查到的旧笔记也在同一个目标库里，才执行合并！
        # 否则可能会把西语笔记合并到社科库里，导致混乱
        is_same_db_match = False
        
        # 这里我们需要做一个假设：我们无法轻易知道旧笔记属于哪个库
        # 但我们可以通过 memory_match 的 metadata 来判断，或者简化逻辑：
        # 如果用户明确改了分类，通常意味着它是新内容，或者是纠错，
        # 为了安全起见，如果分类变了，我们倾向于【新建】，除非非常确定。
        
        if memory_match.get('match'):
            existing_id = memory_match['page_id']
            print(f"💡 Editor: Potential merge target found: 《{memory_match['title']}》")
            
            # 尝试合并
            if decision_source in ['Spanish', 'spanish_learning']:
                strategy = self.decide_merge(raw_text, existing_id)
                if strategy.get('action') == 'insert_row':
                    success = notion_ops.add_row_to_table(strategy['table_id'], strategy['row_data'])
                    if success: return True 
            
            # 尝试追加
            success = notion_ops.append_to_page(existing_id, draft.get('summary'), blocks)
            if success: 
                page_id = existing_id
                print("✅ Editor: Merge Successful.")
            else:
                print("⚠️ Editor: Merge failed (Page not found/archived). Switching to CREATE mode.")

        # =========================================================
        # 3. 新建逻辑 (Create Logic)
        # =========================================================
        if not page_id:
            print(f"🆕 Editor: Publishing NEW page to DB {str(target_db_id)[-4:]}...")
            
            if decision_source in ['Spanish', 'spanish_learning']:
                page_id = notion_ops.create_study_note(
                    draft.get('title'), 
                    draft.get('category', 'General'), 
                    draft.get('summary'), 
                    blocks, 
                    original_url
                )
            else:
                page_id = notion_ops.create_general_note(
                    {**draft, "blocks": blocks}, # 确保 blocks 传进去
                    target_db_id, # 👈 确保这里用的是计算出的 target_db_id
                    original_url
                )

        # =========================================================
        # 4. 记忆归档
        # =========================================================
        if page_id:
            print("🧠 Editor: Archiving to Vector Memory...")
            # 记录最终的分类
            final_category = domain if domain else intent_type
            vector_ops.add_memory(page_id, raw_text[:2000], page_title, final_category)
            return True
        
        return False
