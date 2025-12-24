import operator
from typing import Annotated, TypedDict, Union, List, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver # 🌟 关键：内存检查点

# ==========================================
# Knowledge Domain Routing
# ==========================================

DOMAIN_SPANISH = "spanish_learning"
DOMAIN_TECH = "tech_knowledge"
DOMAIN_HUMANITIES = "humanities_social_science"
DOMAIN_GENERAL = "general"

INTENT_TO_DOMAIN = {
    "SpanishLearning": DOMAIN_SPANISH,
    "Spanish": DOMAIN_SPANISH,
    "Language": DOMAIN_SPANISH,

    "Tech": DOMAIN_TECH,
    "Technology": DOMAIN_TECH,
    "AI": DOMAIN_TECH,
    "Science": DOMAIN_TECH,

    "Humanities": DOMAIN_HUMANITIES,
    "SocialScience": DOMAIN_HUMANITIES,
    "History": DOMAIN_HUMANITIES,
    "Philosophy": DOMAIN_HUMANITIES,
}

# 导入业务逻辑
from agents import ResearcherAgent, EditorAgent

# 初始化智能体（执行层）
researcher = ResearcherAgent()
editor = EditorAgent()

def default_state() -> dict:
    return {
        "user_input": "",
        "uploaded_file": None,
        "raw_text": "",
        "original_url": "",
        "intent_type": "",
        "memory_match": {},
        "draft": {},
        "retry_count": 0,
        "error_message": "",
        "final_output": "",
        "human_feedback": "",
        "review_status": "pending",
        "human_decision": "",
        "override_database_id": "",
    }

# ==========================================
# 1. 定义状态
# ==========================================
class AgentState(TypedDict):
    # 输入
    user_input: str
    uploaded_file: Any
    
    # 中间变量
    raw_text: str
    original_url: str
    intent_type: str
    knowledge_domain: str
    memory_match: Dict
    
    # 核心产物
    draft: Dict
    
    # 控制流
    retry_count: int
    error_message: str
    final_output: str

    human_feedback: str
    review_status: str

    human_decision: str   # "approve" | "reroute" | "edit"
    override_database_id: str

from pydantic import BaseModel, ValidationError

class DraftSchema(BaseModel):
    title: str
    content: str

# ==========================================
# 2. 填充节点逻辑 (Real Logic)
# ==========================================

def node_perceiver(state: AgentState) -> AgentState:
    """感知：读取输入"""
    print("🔵 [Graph] Perceiver: Reading input...")
    # 调用 Researcher 的真实感知能力
    raw_text, url = researcher.perceive(state.get('user_input'), state.get('uploaded_file'))
    
    if not raw_text:
        raise ValueError("Input processing failed (Empty content).")
        
    return {
        "raw_text": raw_text, 
        "original_url": url,
    }

def node_classifier(state: AgentState) -> AgentState:
    """分类：判断意图"""
    print("🔵 [Graph] Classifier: Analyzing intent...")
    intent_data = researcher.analyze_intent(state['raw_text'])
    return {"intent_type": intent_data.get('type', 'General')}

def node_domain_router(state: AgentState) -> AgentState:
    """
    根据 intent_type 映射到具体知识库 / 向量库领域
    """
    intent = state.get("intent_type", "")
    domain = INTENT_TO_DOMAIN.get(intent, DOMAIN_GENERAL)

    print(f"🧭 [Graph] Domain Router: intent='{intent}' -> domain='{domain}'")
    return {"knowledge_domain": domain}

def node_memory(state: AgentState) -> AgentState:
    """记忆：单一向量库 + domain 作为 metadata"""
    domain = state.get("knowledge_domain", DOMAIN_GENERAL)
    print(f"🔵 [Graph] Memory: Searching vector DB (domain={domain})...")

    try:
        # 新版接口：支持 domain 作为过滤条件
        match = researcher.consult_memory(
            query=state["raw_text"],
            domain=domain
        )
    except TypeError:
        # 旧版接口：不支持 domain，Graph 仍然保留语义信息
        print("⚠️ [Graph] consult_memory() does not support domain, fallback to default")
        match = researcher.consult_memory(state["raw_text"])

    # 🌱 关键：把 domain 作为 metadata 注入 memory_match
    if isinstance(match, dict):
        match["domain"] = domain

    return {"memory_match": match}

def node_researcher(state: AgentState) -> AgentState:
    """研究员：生成草稿"""
    print(f"🔵 [Graph] Researcher: Drafting content (Attempt {state.get('retry_count', 0) + 1})...")
    
    # 这里的草稿生成逻辑已经包含了对西语/通用的不同处理
    try:
        # 新版接口：支持 error_context
        draft = researcher.draft_content(
            state["raw_text"],
            state["intent_type"],
            error_context=state.get("error_message", "")
        )
    except TypeError:
        # 旧版接口：不支持 error_context
        print("⚠️ [Graph] draft_content() does not support error_context, fallback to basic mode")
        draft = researcher.draft_content(
            state["raw_text"],
            state["intent_type"]
        )
    return {"draft": draft}

def node_validator(state: AgentState) -> AgentState:
    print("🔵 [Graph] Validator: Checking draft schema...")

    draft = dict(state.get("draft", {}))

    # 🔧 Draft Adapter：兼容旧版 Researcher 输出
    if "content" not in draft:
        if "summary" in draft:
            draft["content"] = draft["summary"]
            print("🛠️ [Graph] Adapter: mapped 'summary' -> 'content'")
        elif "body" in draft:
            draft["content"] = draft["body"]
            print("🛠️ [Graph] Adapter: mapped 'body' -> 'content'")
        elif "text" in draft:
            draft["content"] = draft["text"]
            print("🛠️ [Graph] Adapter: mapped 'text' -> 'content'")

    try:
        DraftSchema(**draft)
        return {
            "draft": draft,   # ⚠️ 把修正后的 draft 写回 state
            "error_message": ""
        }
    except ValidationError as e:
        print("❌ [Graph] Validation Failed:", e)
        return {
            "error_message": str(e),
            "retry_count": state.get("retry_count", 0) + 1
        }

def node_human_review(state: AgentState) -> AgentState:
    """
    Human Review Node
    - human_decision:
        - approve   → 直接发布
        - reroute   → 人工指定新的 notion_database_id
        - edit      → 内容已被人工编辑（draft 已变）
    """
    print("🟠 [Graph] Human Review: Waiting for human decision...")

    decision = state.get("human_decision", "approve")

    if decision == "reroute":
        override_db = state.get("override_database_id")
        if override_db:
            print(f"🧠 [Human] Override database_id -> {override_db}")
            return {"notion_database_id": override_db}

    return {}

def node_publisher(state: AgentState) -> AgentState:
    """发布：写入 Notion"""
    print("🔵 [Graph] Publisher: Writing to Notion...")
    
    try:
        # 新版接口：支持 database_id（多数据库发布）
        success = editor.publish(
            draft=state['draft'],
            intent_type=state['intent_type'],
            memory_match=state['memory_match'],
            raw_text=state['raw_text'],
            original_url=state['original_url'],
            database_id=state.get("notion_database_id"),
            domain=state.get("knowledge_domain")  # 👈 新增（向后兼容）
        )
    except TypeError:
        # 旧版接口：不支持 database_id
        print("⚠️ [Graph] publish() does not support database_id, fallback to default database")
        success = editor.publish(
            draft=state['draft'],
            intent_type=state['intent_type'],
            memory_match=state['memory_match'],
            raw_text=state['raw_text'],
            original_url=state['original_url']
        )
    
    msg = "✅ Published Successfully" if success else "❌ Publication Failed"
    return {"final_output": msg}

# ==========================================
# 3. 路由逻辑
# ==========================================
def route_after_validation(state: AgentState):
    if not state.get('error_message'):
        return "human_review" # ✅ 通过 -> 人工审查
    
    if state.get('retry_count', 0) <= 2:
        return "researcher"   # ❌ 失败 -> 重试 (自我纠错)
    else:
        return "human_review" # 💀 次数用尽 -> 强行交给人去改

# ==========================================
# 4. 构建图
# ==========================================

workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("perceiver", node_perceiver)
workflow.add_node("classifier", node_classifier)
workflow.add_node("domain_router", node_domain_router)
workflow.add_node("memory", node_memory)
workflow.add_node("researcher", node_researcher)
workflow.add_node("validator", node_validator)
workflow.add_node("human_review", node_human_review)
workflow.add_node("publisher", node_publisher)

# 设置流程线
workflow.set_entry_point("perceiver")
workflow.add_edge("perceiver", "classifier")
workflow.add_edge("classifier", "domain_router")
workflow.add_edge("domain_router", "memory")
workflow.add_edge("memory", "researcher")
workflow.add_edge("researcher", "validator")

# 条件分支 (循环的核心)
workflow.add_conditional_edges(
    "validator",
    route_after_validation,
    {"human_review": "human_review", "researcher": "researcher"}
)

workflow.add_edge("human_review", "publisher")
workflow.add_edge("publisher", END)

# 初始化内存
checkpointer = MemorySaver()

# 编译图：指定在 'human_review' 节点前中断
app_graph = workflow.compile(
    checkpointer=checkpointer, 
    interrupt_before=["human_review"]
)

# ==========================================
# 5. 本地测试入口 (让文件可以独立运行)
# ==========================================
if __name__ == "__main__":
    print("🚀 Starting Graph Test (CLI Mode)...")
    
    # 模拟配置
    config = {"configurable": {"thread_id": "test_thread_1"}}
    
    # 模拟输入
    initial_state = {
        **default_state(),
        "user_input": "DeepSeek-V3 是一篇关于 AI 的论文...",
        "uploaded_file": None
    }
    
    print(f"📥 Testing with input: {initial_state['user_input'][:20]}...")
    
    # 运行图
    for event in app_graph.stream(initial_state, config, stream_mode="values"):
        # 打印当前步骤更新了哪些字段
        updated_keys = list(event.keys())
        print(f"🔄 Graph Update: {updated_keys}")
        
    print("\n🛑 Graph paused at 'human_review' (Expected behavior).")