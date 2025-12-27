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
        # 清洗可能存在的 Markdown 代码块标记
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
            return user_input, None

        return None, None

    def analyze_intent(self, text):
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
        if text.strip().startswith("❌ Error"):
            return {
                "title": "⚠️ Content Fetch Failed",
                "summary": "Unable to retrieve content from the provided source.",
                "markdown_body": f"# Error Details\n\nThe system encountered an error while processing your request:\n\n> {text}\n\nPlease check the input and try again.",
                "category": "Error",
                "tags": ["Error"]
            }

        current_error = error_context
        
        # === 循环重试逻辑 (Max 3次) ===
        for attempt in range(3):
            print(f"🔄 Draft Generation Attempt {attempt + 1}/3...")
            
            err_msg_block = ""
            if current_error:
                err_msg_block = (
                    f"\n\n--- PREVIOUS ERROR ---\n"
                    f"Your previous attempt failed with the following error:\n{current_error}\n"
                    f"Please FIX the JSON format and content based on this error.\n"
                    f"----------------------\n"
                )

            # ---------- 1. 根据 intent_type 构建 Prompt ----------
            if intent_type == "Spanish":
                prompt = f"""
                You are a Spanish teacher.
                {err_msg_block}
                Input: {text[:20000]}
                
                Analyze the content and Output STRICT JSON.
                
                LANGUAGE REQUIREMENT:
                - **MUST USE SIMPLIFIED CHINESE (简体中文)** for all explanations, titles, and summaries.
                
                OUTPUT REQUIREMENTS:
                1. "markdown_body" MUST be a string containing the full article content in Markdown format.
                2. Use H1 (#), H2 (##), bullet points (-), and bold (**) for formatting.
                
                JSON SCHEMA:
                {{
                    "title": "string",
                    "category": "Grammar | Vocabulary | Culture",
                    "summary": "string",
                    "markdown_body": "# 标题\\n这里是正文...\\n- 列表项",
                    "tags": ["string"]
                }}
                """
                tag = "Spanish Draft"
                
            else: # General / Tech / Humanities
                prompt = f"""
                You are a professional research editor.
                {err_msg_block}

                Analyze the following content and output STRICT JSON.
                
                LANGUAGE REQUIREMENT:
                - **MUST USE SIMPLIFIED CHINESE (简体中文)** for title, summary, and analysis.

                Input Content:
                {text[:20000]}

                OUTPUT REQUIREMENTS (VERY IMPORTANT):
                1. Output MUST be valid JSON.
                2. Use "markdown_body" to write the FULL article.
                3. Do NOT use "blocks" list anymore.
                4. Use standard Markdown syntax (#, ##, -, >, **) in "markdown_body".

                JSON SCHEMA:
                {{
                  "title": "string",
                  "summary": "string",
                  "markdown_body": "# 章节一\\n这里是详细的正文内容...\\n## 子标题\\n- 要点1\\n- 要点2",
                  "tags": ["string"],
                  "category": "string"
                }}
                """
                tag = "General Draft"

            # ---------- 2. 请求 LLM ----------
            content, _ = get_reasoning_completion(prompt)
            
            # ---------- 3. 解析与校验 ----------
            draft = safe_json_parse(content, tag)
            
            if draft and isinstance(draft, dict) and draft.get("markdown_body"):
                if not isinstance(draft.get("summary"), str):
                    draft["summary"] = draft.get("markdown_body", "")[:300]
                if not isinstance(draft.get("title"), str):
                    draft["title"] = "Untitled"
                if not isinstance(draft.get("tags"), list):
                    draft["tags"] = []
                
                print(f"✅ Attempt {attempt + 1} Success.")
                return draft
            
            # ---------- 4. 失败处理 ----------
            print(f"⚠️ Attempt {attempt + 1} Failed. Parsing error or missing 'markdown_body'.")
            current_error = (
                f"JSON Parsing Failed. The output was not valid JSON or missing 'markdown_body' key.\n"
                f"Your raw output start was: {content[:500]}..."
            )

        # === 5. 兜底 ===
        print("❌ All 3 attempts failed. Using fallback.")
        return {
            "title": "Untitled (Parse Error)",
            "summary": "Automatic parsing failed after 3 attempts.",
            "markdown_body": f"# Original Content\n\n{text[:3000]}\n\n> Note: AI generation failed.",
            "tags": ["Error"],
            "category": "Uncategorized"
        }

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
        
        blocks = draft.get("blocks", [])
        markdown_body = draft.get("markdown_body")

        if not markdown_body and not blocks:
            draft["markdown_body"] = raw_text[:3000]

        # 1️⃣ Resolve database
        if database_id:
            target_db = database_id
        elif domain == "spanish_learning":
            target_db = notion_ops.DB_SPANISH_ID
        elif domain == "tech_knowledge":
            target_db = notion_ops.DB_TECH_ID
        else:
            target_db = notion_ops.DB_HUMANITIES_ID

        # 2️⃣ Merge Logic (读取 -> 融合 -> 重写)
        page_id = None
        
        if memory_match.get("match"):
            existing_id = memory_match.get("page_id")
            print(f"🔗 Found related page ({existing_id}). Starting Merge Process...")
            
            try:
                # A. 读取旧笔记 (依赖 notion_ops.get_page_text)
                old_text = notion_ops.get_page_text(existing_id)
                
                if old_text:
                    # B. 调用内部融合函数
                    merged_draft = self._internal_merge(old_text, draft, intent_type)
                    
                    if merged_draft and merged_draft.get("markdown_body"):
                        # C. 重写 Notion 页面 (依赖 notion_ops.overwrite_page_content)
                        success = notion_ops.overwrite_page_content(existing_id, merged_draft)
                        if success:
                            page_id = existing_id
                            print(f"✅ Successfully merged and updated page: {merged_draft.get('title')}")
                
            except Exception as e:
                print(f"⚠️ Merge failed ({e}), falling back to create new page.")

        # 3️⃣ Create (如果 Merge 没发生或失败)
        if not page_id:
            page_id = notion_ops.create_general_note(draft, target_db, original_url)

        if not page_id:
            return {"success": False, "page_id": None, "title": None, "target_db_id": target_db}

        return {
            "success": True,
            "page_id": page_id,
            "title": title,
            "target_db_id": target_db,
        }
        
    def _internal_merge(self, old_text, new_draft, intent_type):
        """
        Helper: 融合新旧文本
        """
        # 获取新草稿的 Markdown 文本
        new_text = new_draft.get("markdown_body", "") or str(new_draft)
        
        prompt = f"""
        Act as a Knowledge Manager. Merge the following two texts into one comprehensive Markdown article.
        
        GOAL: Create a single, unified article that contains the best information from both sources.
        
        REQUIREMENTS:
        1. **Eliminate duplicates**: Do not repeat the same information.
        2. **Logical Flow**: The merged text should read like one cohesive article, not two separate parts pasted together.
        3. **Language**: SIMPLIFIED CHINESE (简体中文).
        4. **Format**: Standard Markdown (H1, H2, bullets).

        --- OLD TEXT (From Database) ---
        {old_text[:6000]}
        
        --- NEW TEXT (Input) ---
        {new_text[:6000]}
        
        OUTPUT JSON SCHEMA: 
        {{ 
            "title": "Merged Title", 
            "summary": "Merged Summary", 
            "markdown_body": "# Merged Title\\n...content..." 
        }}
        """
        res, _ = get_reasoning_completion(prompt)
        return safe_json_parse(res, "Merge")