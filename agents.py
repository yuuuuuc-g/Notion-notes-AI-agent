import json
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
        # Clean potential markdown code blocks
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
        
    def merge_content(self, old_text: str, new_input: str) -> dict:
        """
        合并旧笔记内容和新输入内容
        
        参数:
            old_text: 现有笔记的文本内容
            new_input: 新的输入内容
        
        返回:
            dict: 合并后的草稿，包含 title, summary, markdown_body, tags
        """
        print("⚗️ Researcher merging content...")
        prompt = f"""
        Act as a Knowledge Editor. 
        Task: Merge the NEW INPUT into the EXISTING NOTE.
        
        EXISTING NOTE:
        {old_text[:5000]}
        
        NEW INPUT:
        {new_input[:5000]}
        
        Output JSON (Markdown):
        {{
            "title": "Combined Title",
            "summary": "Summary of changes",
            "markdown_body": "# Title\\n\\nMerged content...",
            "tags": ["tag1", "tag2"]
        }}
        """
        res, _ = get_reasoning_completion(prompt)
        return safe_json_parse(res, "Merge Draft")

    def analyze_intent(self, text: str) -> dict:
        if text.strip().startswith("❌ Error"):
            print("🛑 Error detected in content, skipping analysis.")
            return {"intent": "Error", "category": "Error"}

        prompt = f"""
        Analyze the user input to determine the INTENT and CATEGORY.

        Input Preview: {text[:800]}

        DEFINITIONS:
        1. **intent**:
           - "save_note": The user wants to save, record, summarize, extract, or write down information.
           - "query_knowledge": The user is asking a question or looking for specific information.

        2. **category**:
           - "Spanish" (Language learning)
           - "Tech" (Programming, AI, Engineering)
           - "Humanities" (History, Economics, Philosophy, General)

        RETURN STRICT JSON:
        {{
            "intent": "save_note" | "query_knowledge",
            "category": "Spanish" | "Tech" | "Humanities"
        }}
        """
        res = get_completion(prompt)
        
        parsed = safe_json_parse(res, "Intent Analysis")
        if not parsed:
            return {"intent": "save_note", "category": "Humanities"}
        
        # Compatibility fix
        if "type" in parsed and "category" not in parsed:
            parsed["category"] = parsed["type"]
            
        return parsed

    def consult_memory(self, text: str, domain: str = None) -> dict:
        """
        从向量数据库中查询相关记忆
        
        参数:
            text: 查询文本
            domain: 领域过滤器，None 或 "All" 表示搜索所有领域
        
        返回:
            dict: 查询结果，包含 match、page_id、title 等字段
        """
        category_filter = None if domain == "All" else domain
        print(f"🧠 Memory search (Filter: {category_filter})...")
        return vector_ops.search_memory(text[:1000], category_filter=category_filter)

    def merge_content(self, old_text: str, new_input: str) -> dict:
        """
        根据文本内容生成结构化草稿
        
        参数:
            text: 原始文本内容
            category: 内容分类，可选值 "Spanish" | "Tech" | "Humanities"（默认为 "Humanities"）
            error_context: 错误上下文，用于重试时提供之前的错误信息
        
        返回:
            dict: 包含 title, summary, markdown_body, tags 等字段的草稿字典
        """
        if text.strip().startswith("❌ Error"):
            return {
                "title": "⚠️ Content Fetch Failed",
                "summary": "Unable to retrieve content.",
                "markdown_body": f"# Error Details\n\n> {text}",
                "category": "Error",
                "tags": ["Error"]
            }

        current_error = error_context
        
        for attempt in range(3):
            print(f"🔄 Draft Generation Attempt {attempt + 1}/3...")
            
            err_msg_block = ""
            if current_error:
                err_msg_block = f"\n\n--- PREVIOUS ERROR ---\n{current_error}\n----------------------\n"

            if category == "Spanish":
                prompt = f"""
                You are a Spanish teacher.
                {err_msg_block}
                Input: {text[:20000]}
                
                Analyze the content and Output STRICT JSON.
                LANGUAGE: SIMPLIFIED CHINESE.
                FORMAT: Markdown.
                
                JSON SCHEMA:
                {{
                    "title": "string",
                    "category": "Grammar | Vocabulary | Culture",
                    "summary": "string",
                    "markdown_body": "# Title\\nContent...",
                    "tags": ["string"]
                }}
                """
                tag = "Spanish Draft"
            else: 
                prompt = f"""
                You are a professional research editor.
                {err_msg_block}
                Input: {text[:20000]}

                Analyze and output STRICT JSON.
                LANGUAGE: SIMPLIFIED CHINESE.
                
                JSON SCHEMA:
                {{
                  "title": "string",
                  "summary": "string",
                  "markdown_body": "# Title\\nContent...",
                  "tags": ["string"],
                  "category": "string"
                }}
                """
                tag = "General Draft"

            content, _ = get_reasoning_completion(prompt)
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
            
            print(f"⚠️ Attempt {attempt + 1} Failed.")
            current_error = f"JSON Parsing Failed. Raw output start: {content[:500]}..."

        print("❌ All attempts failed.")
        return {
            "title": "Untitled (Parse Error)",
            "summary": "Parsing failed.",
            "markdown_body": f"# Original Content\n\n{text[:3000]}",
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
        """
        将草稿发布到 Notion
        
        参数:
            draft: 草稿字典，包含 title, summary, markdown_body, tags
            intent_type: 意图类型（目前未在逻辑中使用）
            memory_match: 记忆匹配结果（在新流程中通常为 None，合并逻辑在 workflow 中处理）
            raw_text: 原始文本
            original_url: 原始 URL（可选）
            domain: 领域名称（用于选择数据库，如果未提供 database_id）
            database_id: 目标数据库 ID（优先使用）
        
        返回:
            dict: 包含 success, page_id, title, target_db_id 的字典
        """
        if not draft:
            return {"success": False, "page_id": None}

        title = draft.get("title", "Untitled")
        markdown_body = draft.get("markdown_body") or raw_text[:3000]
        draft["markdown_body"] = markdown_body

        # 确定目标数据库（优先使用 database_id，否则根据 domain 选择）
        if database_id:
            target_db = database_id
        elif domain == "spanish_learning":
            target_db = notion_ops.DB_SPANISH_ID
        elif domain == "tech_knowledge":
            target_db = notion_ops.DB_TECH_ID
        else:
            target_db = notion_ops.DB_HUMANITIES_ID

        # 注意：新流程中合并逻辑在 workflow.py 的 node_draft_merge 中处理
        # 这里只处理新建页面的情况
        # （保留 merge 逻辑作为向后兼容，但在新流程中 memory_match 通常为 None）
        page_id = None
        if memory_match and memory_match.get("match") and intent_type != "query_knowledge":
            existing_id = memory_match.get("page_id")
            print(f"🔗 Found related page ({existing_id}). Starting Merge...")
            
            try:
                old_text = notion_ops.get_page_text(existing_id)
                if old_text:
                    merged_draft = self._internal_merge(old_text, draft, intent_type)
                    if merged_draft and merged_draft.get("markdown_body"):
                        success = notion_ops.overwrite_page_content(existing_id, merged_draft)
                        if success:
                            page_id = existing_id
                            print(f"✅ Merged: {merged_draft.get('title')}")
            except Exception as e:
                print(f"⚠️ Merge failed ({e}), creating new page.")

        # 创建新页面
        if not page_id:
            page_id = notion_ops.create_general_note(draft, target_db, original_url)

        if not page_id:
            return {"success": False}

        return {
            "success": True,
            "page_id": page_id,
            "title": title,
            "target_db_id": target_db,
        }
        
    def _internal_merge(self, old_text: str, new_draft: dict, intent_type: str) -> dict:
        """
        内部合并方法（由 publish 方法调用，用于向后兼容）
        
        参数:
            old_text: 旧笔记文本
            new_draft: 新草稿字典
            intent_type: 意图类型（未使用但保留参数兼容性）
        
        返回:
            dict: 合并后的草稿
        """
        new_text = new_draft.get("markdown_body", "") or str(new_draft)
        prompt = f"""
        Act as a Knowledge Manager. Merge these texts into one article.
        LANGUAGE: SIMPLIFIED CHINESE.
        FORMAT: Markdown.

        --- OLD ---
        {old_text[:6000]}
        
        --- NEW ---
        {new_text[:6000]}
        
        JSON SCHEMA: 
        {{ "title": "str", "summary": "str", "markdown_body": "str" }}
        """
        res, _ = get_reasoning_completion(prompt)
        return safe_json_parse(res, "Merge")