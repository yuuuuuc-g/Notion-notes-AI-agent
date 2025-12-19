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
    """JSON 解析防呆工具"""
    if not input_data: return None
    if isinstance(input_data, dict): return input_data
    try:
        text = str(input_data).strip()
        clean_text = text.replace("```json", "").replace("```", "")
        # 尝试提取第一个 { 到最后一个 }
        start = clean_text.find("{")
        end = clean_text.rfind("}") + 1
        if start != -1 and end != -1: 
            clean_text = clean_text[start:end]
            
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
        """1. 感知阶段：获取纯文本"""
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
        """2. 认知阶段：意图分类 (三元)"""
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
        """3. 记忆阶段：查询向量数据库"""
        print("🧠 Researcher: Consulting Knowledge Base (Vector Search)...")
        # 搜索前1000个字符作为摘要索引
        return vector_ops.search_memory(text[:1000])

    def draft_content(self, text, intent_type):
        """4. 撰写阶段：根据类型生成结构化草稿 (V3 版)"""
        
        # === A. 西语模式 (Smart Restructuring) ===
        if intent_type == 'Spanish':
            print("🚀 Researcher: Drafting Spanish content (V3 - Fast)...")
            prompt = f"""
            You are a professional Spanish teacher. 
            Analyze and restructure the following content into a high-quality study note.
            
            Input Content:
            {text[:12000]}
            
            【Your Mission】
            Not just summarization, but **Lossless Restructuring**.
            You must preserve all examples, grammar rules, and nuances, but organize them into a clean Notion structure.

            【Formatting Rules】
            1. **Smart Table**: If you see comparisons (A vs B) or vocabulary lists, MUST use "table" blocks.
            2. **Smart List**: If you see enumeration or steps, MUST use "list" blocks.
            3. **Preserve Context**: Do not delete the detailed explanation or scenario descriptions. Use "text" blocks for them.
            
            【Output JSON Format】
            {{
                "title": "Clear and Descriptive Title", 
                "category": "Grammar/Vocabulary/Reading", 
                "summary": "Concise Chinese summary.",
                "blocks": [
                    {{ "type": "heading", "content": "1. Core Concept" }},
                    {{ "type": "text", "content": "Detailed explanation..." }},
                    {{ 
                        "type": "table", 
                        "content": {{
                            "headers": ["Spanish", "Chinese", "Notes"],
                            "rows": [["Hola", "Hello", "Greeting"], ["Adios", "Bye", "Farewell"]]
                        }}
                    }},
                    {{ "type": "heading", "content": "2. Key Examples" }},
                    {{ "type": "list", "content": ["Example 1", "Example 2"] }}
                ]
            }}
            """
            # 🌟 修改：降级为 V3，不需要 reasoning
            content = get_completion(prompt)
            return safe_json_parse(content, "Spanish Draft")
            
        # === B. 通用模式 (Tech / Humanities) - 升级版 ===
        else:
            print("🚀 Researcher: Drafting General content (V3 - Fast)...")
            prompt = f"""
            You are a professional Tech/Research Editor. 
            Analyze and restructure the following content into a high-quality Notion page.
            
            Input Content: 
            {text[:15000]} 
            
            **CRITICAL INSTRUCTION**: 
            1. Do NOT summarize too briefly. I need detailed, comprehensive notes.
            2. **Reconstruct structure**: Use Heading, List, Table to organize knowledge.
            3. If there is code, try to explain logic in text or list.
            
            **Output JSON Format**:
            {{
                "title": "Article Title",
                "summary": "Detailed Summary",
                "tags": ["Tag1", "Tag2"],
                "blocks": [
                    {{ "type": "heading", "content": "1. Introduction" }},
                    {{ "type": "text", "content": "Detailed explanation..." }},
                    {{ "type": "list", "content": ["Point A", "Point B"] }},
                    {{ "type": "table", "content": {{ "headers": ["Col1", "Col2"], "rows": [["Val1", "Val2"]] }} }}
                ]
            }}
            """
            # 🌟 修改：降级为 V3，不需要 reasoning
            content = get_completion(prompt)
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
        
        if not tables:
            return {"action": "append_text"}

        prompt = f"""
        Editor Logic. 
        Page Structure: {structure_text}
        Existing Tables: {json.dumps(tables)}
        New Content: {new_text[:800]}
        
        Task: Can the new content be inserted as a new row into an existing table?
        Output JSON: {{ "action": "insert_row", "table_id": "...", "row_data": [...] }} OR {{ "action": "append_text" }}
        """
        return safe_json_parse(get_completion(prompt), "Merge Decision") or {"action": "append_text"}

    def publish(self, draft, intent_type, memory_match, raw_text, original_url=None):
        """执行发布流程"""
        if not draft:
            print("❌ Editor: Draft is empty.")
            return False

        page_title = draft.get('title', 'Untitled')
        page_id = None
        
        # 统一获取 blocks
        blocks = draft.get('blocks') or draft.get('key_points', [])

        # === 场景 A: 命中记忆 (合并) ===
        if memory_match.get('match'):
            existing_id = memory_match['page_id']
            existing_title = memory_match['title']
            print(f"💡 Editor: Merging into existing record: 《{existing_title}》")
            
            if intent_type == 'Spanish':
                strategy = self.decide_merge(raw_text, existing_id)
                if strategy.get('action') == 'insert_row':
                    success = notion_ops.add_row_to_table(strategy['table_id'], strategy['row_data'])
                    if success: return True 
            
            success = notion_ops.append_to_page(existing_id, draft.get('summary'), blocks)
            if success: page_id = existing_id

        # === 场景 B: 新建 (Create) ===
        if not page_id:
            print(f"🆕 Editor: Publishing new edition: 《{page_title}》")
            
            if intent_type == 'Spanish':
                page_id = notion_ops.create_study_note(
                    draft.get('title'), 
                    draft.get('category', 'General'), 
                    draft.get('summary'), 
                    blocks, 
                    original_url
                )
            else:
                target_db = notion_ops.DB_TECH_ID if intent_type == 'Tech' else notion_ops.DB_HUMANITIES_ID
                page_id = notion_ops.create_general_note(draft, target_db, original_url)

        # === 归档阶段：存入向量记忆 ===
        if page_id:
            print("🧠 Editor: Archiving to Vector Memory...")
            vector_ops.add_memory(page_id, raw_text[:2000], page_title, intent_type)
            return True
        
        return False