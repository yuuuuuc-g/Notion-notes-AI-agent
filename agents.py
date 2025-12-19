import json
import re
from llm_client import get_completion, get_reasoning_completion
# 导入工具集 (Skills)
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
        start = clean_text.find("{")
        end = clean_text.rfind("}") + 1
        if start != -1 and end != -1: clean_text = clean_text[start:end]
        return json.loads(clean_text)
    except Exception as e:
        print(f"❌ [{context}] JSON Parse Error: {e}")
        return None

# ==========================================
# 🕵️‍♂️ Agent 1: 研究员 (The Researcher)
# 职责：感知输入、意图分类、记忆检索、草稿撰写
# ==========================================
class ResearcherAgent:
    def __init__(self):
        print("🕵️‍♂️ Researcher Agent initialized.")

    def perceive(self, user_input=None, uploaded_file=None):
        """1. 感知阶段：处理多模态输入 -> 纯文本"""
        if uploaded_file:
            if not read_pdf_content: raise Exception("Missing file_ops")
            print("📂 Researcher: Reading PDF...")
            return read_pdf_content(uploaded_file)
        elif user_input:
            if user_input.strip().startswith("http"):
                url = user_input.strip()
                print(f"🌐 Researcher: Fetching URL {url}...")
                content = fetch_url_content(url)
                return f"[Source] {url}\n{content}", url # 返回内容和URL
            return user_input, None
        return None, None

    def analyze_intent(self, text):
        """2. 认知阶段：意图分类"""
        prompt = f"""
        Analyze content type. First 800 chars: {text[:800]}
        Return JSON: {{ "type": "Spanish" }} OR {{ "type": "General" }}
        Logic:
        - Spanish: Language learning, Grammar, Vocab.
        - General: Tech, News, History, Politics.
        """
        res = get_completion(prompt)
        return safe_json_parse(res, "Classify") or {"type": "General"}

    def consult_memory(self, text):
        """3. 记忆阶段：查询向量数据库"""
        print("🧠 Researcher: Consulting Knowledge Base (Vector Search)...")
        # 搜索前1000个字符作为摘要索引
        return vector_ops.search_memory(text[:1000])

    def draft_content(self, text, intent_type):
        """4. 撰写阶段：根据类型生成草稿"""
        if intent_type == 'Spanish':
            print("🚀 Researcher: Drafting Spanish content (using R1)...")
            prompt = f"""
            You are a Spanish expert. Process content: {text[:10000]}
            Output JSON:
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
            print("🚀 Researcher: Drafting General content (using R1)...")
            prompt = f"""
            Research Assistant. Analyze: {text[:12000]} 
            Output strictly JSON:
            {{
                "title": "Chinese Title", "summary": "Detailed Summary", "tags": ["Tag1"], "key_points": ["Point 1..."]
            }}
            """
            content, _ = get_reasoning_completion(prompt)
            return safe_json_parse(content, "General Draft")

# ==========================================
# ✍️ Agent 2: 主编 (The Editor)
# 职责：决策合并策略、排版、最终发布 (Notion)
# ==========================================
class EditorAgent:
    def __init__(self):
        print("✍️ Editor Agent initialized.")

    def decide_merge(self, new_text, existing_page_id):
        """决策阶段：如果有旧笔记，决定如何合并"""
        structure_text, tables = notion_ops.get_page_structure(existing_page_id)
        
        if not tables:
            return {"action": "append_text"}

        prompt = f"""
        Editor Logic. 
        Page Structure: {structure_text}
        Existing Tables: {json.dumps(tables)}
        New Content: {new_text[:800]}
        Output JSON: {{ "action": "insert_row", "table_id": "...", "row_data": [...] }} OR {{ "action": "append_text" }}
        """
        # 这里用 V3 即可，决策逻辑不需要太深
        return safe_json_parse(get_completion(prompt), "Merge Decision") or {"action": "append_text"}

    def publish(self, draft, intent_type, memory_match, raw_text, original_url=None):
        """执行阶段：发布到 Notion"""
        if not draft:
            print("❌ Editor: Draft is empty. Rejection.")
            return False

        page_title = draft.get('title', 'Untitled')
        page_id = None

        # === 场景 A: 命中记忆 (合并) ===
        if memory_match.get('match'):
            existing_id = memory_match['page_id']
            existing_title = memory_match['title']
            print(f"💡 Editor: Merging into existing record: 《{existing_title}》")
            
            if intent_type == 'Spanish':
                # 西语特殊逻辑：尝试插入表格
                strategy = self.decide_merge(raw_text, existing_id)
                if strategy.get('action') == 'insert_row':
                    notion_ops.add_row_to_table(strategy['table_id'], strategy['row_data'])
                    return True # 插入行结束，不再追加
                
                # 否则追加 Block
                notion_ops.append_to_page(existing_id, draft.get('summary'), draft.get('blocks'))
                page_id = existing_id
            else:
                # 通用逻辑：直接追加 Key Points
                notion_ops.append_to_page(existing_id, draft.get('summary'), draft.get('key_points'))
                page_id = existing_id

        # === 场景 B: 新主题 (新建) ===
        else:
            print(f"🆕 Editor: Publishing new edition: 《{page_title}》")
            if intent_type == 'Spanish':
                page_id = notion_ops.create_study_note(
                    draft.get('title'), 
                    draft.get('category', 'General'), 
                    draft.get('summary'), 
                    draft.get('blocks'), 
                    original_url
                )
            else:
                # 确定目标库
                target_db = notion_ops.DB_TECH_ID if draft.get('tags') and 'Tech' in str(draft.get('tags')) else notion_ops.DB_HUMANITIES_ID
                # 简单处理：如果分类器说是 Tech，就存 Tech，或者根据 Tags 辅助判断。
                # 这里为了简单，复用 intent_type 里的逻辑，或者直接存社科保底
                # 实际可以更细，这里暂用传入的 target_db_id
                # 修正：我们让 Editor 根据 intent_type 决定数据库
                target_db = notion_ops.DB_TECH_ID if intent_type == 'Tech' else notion_ops.DB_HUMANITIES_ID
                
                page_id = notion_ops.create_general_note(draft, target_db, original_url)

        # === 归档阶段：存入向量记忆 ===
        if page_id:
            print("🧠 Editor: Archiving to Vector Memory...")
            # 存前2000字作为索引
            vector_ops.add_memory(page_id, raw_text[:2000], page_title, intent_type)
            return True
        
        return False