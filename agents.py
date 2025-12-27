import json
import re
from llm_client import get_completion, get_reasoning_completion
import notion_ops
import vector_ops

try:
    from file_ops import read_pdf_content
except ImportError:
    read_pdf_content = None


# =========================================================
# Utilities
# =========================================================
def safe_json_parse(input_data, context=""):
    if not input_data:
        return None
    if isinstance(input_data, dict):
        return input_data
    try:
        text = str(input_data).strip()
        clean = text.replace("```json", "").replace("```", "")
        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start != -1 and end != -1:
            clean = clean[start:end]
        return json.loads(clean)
    except Exception as e:
        print(f"❌ [{context}] JSON parse error:", e)
        return None


# =========================================================
# Researcher Agent
# =========================================================
class ResearcherAgent:
    def __init__(self):
        print("🕵️‍♂️ Researcher Agent initialized.")

    def perceive(self, user_input=None, uploaded_file=None):
        if uploaded_file:
            if not read_pdf_content:
                raise RuntimeError("PDF support missing")
            print("📂 Reading PDF...")
            return read_pdf_content(uploaded_file), None

        if user_input:
            # 🟢 无论输入什么，都直接原样返回
            return user_input, None

        return None, None

    def analyze_intent(self, text):
        # 🛑 关键防御：如果内容是报错信息，直接中断
        if text.strip().startswith("❌ Error"):
            print("🛑 Error detected in content, skipping analysis.")
            return {"type": "Error", "error": text}

        prompt = f"""
        Analyze content type. First 800 chars:
        {text[:800]}

        Return JSON:
        {{ "type": "Spanish" | "Tech" | "Humanities" }}
        """
        res = get_completion(prompt)
        return safe_json_parse(res, "Intent") or {"type": "Humanities"}

    def consult_memory(self, text, domain=None):
        print(f"🧠 Memory search (domain={domain})")
        return vector_ops.search_memory(text[:1000], category_filter=domain)

    
    def draft_content(self, text, intent_type, error_context=""):
        # 🛑 错误处理分支
        if text.strip().startswith("❌ Error"):
            return {
                "title": "⚠️ Content Fetch Failed",
                "summary": "Unable to retrieve content from the provided link.",
                "body": text, # 把报错信息显示在正文
                "blocks": [{"type": "paragraph", "content": text}],
                "category": "Error"
            }
        err = f"PREVIOUS ERROR: {error_context}" if error_context else ""

        # ---------- Spanish (已修复 Prompt) ----------
        if intent_type == "Spanish":
            prompt = f"""
            You are a Spanish teacher.
            {err}
            Input: {text[:20000]}
            
            Analyze the content and Output STRICT JSON.
            
            LANGUAGE REQUIREMENT:
            - **MUST USE SIMPLIFIED CHINESE (简体中文)** for all explanations, titles, and summaries.
            - Do NOT use Traditional Chinese.
            
            STRUCTURE REQUIREMENTS:
            1. "blocks" must be a list of objects.
            2. Each block MUST have a "type" and "content".
            3. Allowed types: "heading_2", "paragraph", "bulleted_list_item".
            
            JSON SCHEMA:
            {{
                "title": "string",
                "category": "Grammar | Vocabulary | Culture",
                "summary": "string",
                "body": "Full text of the article for backup",
                "blocks": [
                    {{
                        "type": "heading_2",
                        "content": "Section Title"
                    }},
                    {{
                        "type": "paragraph",
                        "content": "Explanation text..."
                    }},
                    {{
                        "type": "bulleted_list_item",
                        "content": "List item example"
                    }}
                ]
            }}
            """
            content, _ = get_reasoning_completion(prompt)
            draft = safe_json_parse(content, "Spanish Draft") or {}

            # Spanish 兜底
            if not isinstance(draft.get("summary"), str):
                draft["summary"] = text[:300]
            if not isinstance(draft.get("blocks"), list):
                draft["blocks"] = []
            
            # 🟢 Spanish 模式必须手动填充 body，否则 EditorAgent 没法兜底
            if not draft.get("body"):
                draft["body"] = text[:3000] # 如果 AI 没生成，就用原文前3000字

            return draft

        # ---------- General / Tech / Humanities (已优化类型) ----------
        prompt = f"""
        You are a professional research editor.

        Analyze the following content and output STRICT JSON.
        
        LANGUAGE REQUIREMENT:
        - **MUST USE SIMPLIFIED CHINESE (简体中文)** for title, summary, and analysis.

        Input Content:
        {text[:20000]}

        OUTPUT REQUIREMENTS (VERY IMPORTANT):
        1. Output MUST be valid JSON.
        2. You MUST include ALL fields below.
        3. "blocks" MUST be a JSON ARRAY (can be empty).
        4. "body" MUST be a FULL, CONTINUOUS rewritten article.
        5. Even if blocks fail, body must be complete.

        JSON SCHEMA:
        {{
          "title": "string",
          "summary": "string",
          "body": "string",
          "blocks": [
            {{
              "type": "heading_2 | paragraph | bulleted_list_item | code",
              "content": "string"
            }}
          ],
          "tags": ["string"],
          "category": "string"
        }}
        """

        content, _ = get_reasoning_completion(prompt)
        draft = safe_json_parse(content, "General Draft") or {}

        # ===== 强制兜底（防止正文丢失）=====
        if not isinstance(draft.get("body"), str) or not draft["body"].strip():
            draft["body"] = text[:3000]

        if not isinstance(draft.get("summary"), str):
            draft["summary"] = draft["body"][:300]

        if not isinstance(draft.get("blocks"), list):
            draft["blocks"] = []

        if not isinstance(draft.get("title"), str):
            draft["title"] = "Untitled"

        if not isinstance(draft.get("tags"), list):
            draft["tags"] = []

        return draft


# =========================================================
# Editor Agent
# =========================================================
class EditorAgent:
    def __init__(self):
        print("✍️ Editor Agent initialized.")

    def publish(
        self,
        draft: dict,
        intent_type: str,
        memory_match: dict,
        raw_text: str,
        original_url: str = None,
        *,
        domain: str = None,
        database_id: str = None,
    ) -> dict:
        if not draft:
            return {"success": False, "page_id": None, "title": None, "target_db_id": None}

        title = draft.get("title", "Untitled")
        blocks = draft.get("blocks") or []

        # ===== 兜底：如果没有结构化 blocks，用 body 生成正文 =====
    
        if not blocks:
            body = (draft.get("body") or "").strip()
            if body:
                blocks = [
                    {
                        "type": "text", # 这里的 type 必须匹配 notion_ops 里的清洗逻辑
                        "content": body
                    }
                ]
            else:
                # 终极兜底：如果连 body 都没有，直接用 raw_text
                blocks = [{"type": "text", "content": raw_text[:2000] + "..."}]

        # 🟢 修复3：一定要把计算出来的 blocks 写回 draft，
        # 否则 create_general_note 还是会用 draft 里那个空的 blocks
        draft["blocks"] = blocks 

        # 1️⃣ Resolve database
        if database_id:
            target_db = database_id
        elif domain == "spanish_learning":
            target_db = notion_ops.DB_SPANISH_ID
        elif domain == "tech_knowledge":
            target_db = notion_ops.DB_TECH_ID
        else:
            target_db = notion_ops.DB_HUMANITIES_ID

        # 2️⃣ Merge (safe)
        page_id = None
        if memory_match.get("match"):
            try:
                ok = notion_ops.append_to_page(
                    memory_match["page_id"],
                    draft.get("summary", ""),
                    blocks, 
                )
                if ok:
                    page_id = memory_match["page_id"]
            except Exception:
                pass

        # 3️⃣ Create
        if not page_id:
            if intent_type == "Spanish":
                page_id = notion_ops.create_study_note(
                    title,
                    draft.get("category", "General"),
                    draft.get("summary", ""),
                    blocks, 
                    original_url,
                )
            else:
                # 🟢 修复4：create_general_note 内部用的是 draft.get('blocks')
                # 因为我们在上面做了 `draft["blocks"] = blocks`，所以这里传 draft 是安全的
                page_id = notion_ops.create_general_note(draft, target_db, original_url)

        if not page_id:
            return {"success": False, "page_id": None, "title": None, "target_db_id": target_db}

        return {
            "success": True,
            "page_id": page_id,
            "title": title,
            "target_db_id": target_db,
        }