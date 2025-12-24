import json
from llm_client import get_completion, get_reasoning_completion
from web_ops import fetch_url_content
import notion_ops
import vector_ops 

# --- 🛠️ 关键修改：显示 Import 错误 ---
try:
    from file_ops import read_pdf_content
except ImportError as e:
    print(f"❌ [Critical Warning] file_ops import failed: {e}")
    print("👉 Please check if 'file_ops.py' exists and 'PyPDF2' is in requirements.txt")
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
        """1. 感知阶段"""
        # 处理 PDF
        if uploaded_file:
            if read_pdf_content is None:
                # 这里会抛出更具体的错误
                raise Exception("file_ops 模块加载失败。请检查日志开头寻找 'Critical Warning'。")
            
            print("📂 Researcher: Reading PDF...")
            content = read_pdf_content(uploaded_file)
            if not content:
                raise Exception("PDF 内容为空或无法读取（可能是扫描版图片）。")
            return content, None
            
        # 处理 URL / 文本
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
            print("🚀 Researcher: Drafting Spanish content (V3)...")
            prompt = f"""
            You are a professional Spanish teacher. 
            Analyze and restructure:
            {text[:12000]}
            
            Output JSON:
            {{
                "title": "Title", "category": "Vocab", "summary": "Summary",
                "blocks": [
                    {{ "type": "heading", "content": "1. Concept" }},
                    {{ "type": "table", "content": {{ "headers": ["ES","CN"], "rows": [["Hola","Hi"]] }} }}
                ]
            }}
            """
            return safe_json_parse(get_completion(prompt), "Spanish Draft")
        else:
            print("🚀 Researcher: Drafting General content (V3)...")
            prompt = f"""
            You are a Tech/Research Editor. Analyze: 
            {text[:15000]} 
            
            Output JSON:
            {{
                "title": "Title", "summary": "Summary", "tags": ["Tag"],
                "blocks": [
                    {{ "type": "heading", "content": "Intro" }},
                    {{ "type": "list", "content": ["Point A"] }}
                ]
            }}
            """
            return safe_json_parse(get_completion(prompt), "General Draft")

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

    def publish(
        self,
        draft,
        intent_type,
        memory_match,
        raw_text,
        original_url=None,
        database_id=None,
        domain=None,
    ):
        """
        Industrial-grade publish logic.

        Authority order:
        1. Graph (database_id / domain)
        2. Human override
        3. Memory (only if same database)
        4. Intent fallback (legacy)
        """

        # --------------------------------------------------
        # 0. 基础校验
        # --------------------------------------------------
        if not draft:
            print("❌ Editor: Draft is empty.")
            return False

        page_title = draft.get("title", "Untitled")
        blocks = draft.get("blocks") or draft.get("key_points", [])
        page_id = None

        # --------------------------------------------------
        # 1. 决定目标数据库（唯一权威）
        # --------------------------------------------------
        if database_id:
            target_database = database_id
            print(f"📦 Editor: Target database decided by Graph → {target_database}")
        else:
            if intent_type == "Spanish":
                target_database = notion_ops.DB_SPANISH_ID
            elif intent_type == "Tech":
                target_database = notion_ops.DB_TECH_ID
            else:
                target_database = notion_ops.DB_HUMANITIES_ID

            print(f"📦 Editor: Target database fallback by intent → {target_database}")

        # --------------------------------------------------
        # 2. Memory Merge Gate
        # --------------------------------------------------
        can_merge = False
        existing_page_id = None

        if memory_match and memory_match.get("match"):
            mem_db = memory_match.get("database_id")
            existing_page_id = memory_match.get("page_id")

            if mem_db == target_database:
                can_merge = True
                print(f"💡 Editor: Memory match accepted → {existing_page_id}")
            else:
                print(
                    "⚠️ Editor: Memory match rejected (different database)\n"
                    f"    memory_db={mem_db}, target_db={target_database}"
                )

        # --------------------------------------------------
        # 3. Merge
        # --------------------------------------------------
        if can_merge and existing_page_id:
            success = notion_ops.append_to_page(
                existing_page_id,
                draft.get("summary"),
                blocks,
            )
            if success:
                page_id = existing_page_id

        # --------------------------------------------------
        # 4. Create new page
        # --------------------------------------------------
        if not page_id:
            print(f"🆕 Editor: Creating new page → {page_title}")
            page_id = notion_ops.create_general_note(
                draft,
                target_database,
                original_url,
            )

        # --------------------------------------------------
        # 5. Archive memory
        # --------------------------------------------------
        if page_id:
            print("🧠 Editor: Archiving to Vector Memory...")
            vector_ops.add_memory(
                page_id=page_id,
                content=raw_text[:2000],
                title=page_title,
                intent_type=intent_type,
                metadata={
                    "database_id": target_database,
                    "domain": domain,
                },
            )
            return True

        print("❌ Editor: Publish failed.")
        return False