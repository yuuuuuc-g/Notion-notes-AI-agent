import operator
from typing import TypedDict, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from enum import Enum
from pydantic import BaseModel, ValidationError

# 导入业务逻辑
from agents import ResearcherAgent, EditorAgent

# 初始化
researcher = ResearcherAgent()
editor = EditorAgent()

class KnowledgeDomain(str, Enum):
    SPANISH = "spanish_learning"
    TECH = "tech_knowledge"
    HUMANITIES = "humanities"

INTENT_TO_DOMAIN = {
    "Spanish": KnowledgeDomain.SPANISH,
    "Tech": KnowledgeDomain.TECH,
    "Humanities": KnowledgeDomain.HUMANITIES,
}

# --- State ---
class AgentState(TypedDict):
    user_input: str
    uploaded_file: Any
    raw_text: str
    original_url: str
    intent_type: str
    knowledge_domain: KnowledgeDomain
    memory_match: Dict
    draft: Dict
    retry_count: int
    error_message: str
    final_output: str
    # HITL
    human_feedback: str
    override_database_id: str
    # 发布
    notion_database_id: str
    
    # 🛠️ 修复：定义 default_state 函数
def default_state() -> dict:
    """初始化默认状态，防止 KeyError"""
    return {
        "user_input": "",
        "uploaded_file": None,
        "raw_text": "",
        "original_url": "",
        "intent_type": "",
        "knowledge_domain": None,
        "memory_match": {},
        "draft": {},
        "retry_count": 0,
        "error_message": "",
        "final_output": "",
        "human_feedback": "",
        "override_database_id": "",
        "notion_database_id": ""
    }

class DraftSchema(BaseModel):
    title: str
    summary: str # 确保必须有 summary

# --- Nodes ---

def node_perceiver(state: AgentState) -> AgentState:
    print("🔵 [Graph] Perceiver...")
    raw_text, url = researcher.perceive(state.get('user_input'), state.get('uploaded_file'))
    if not raw_text: raise ValueError("Empty input")
    return {"raw_text": raw_text, "original_url": url}

def node_classifier(state: AgentState) -> AgentState:
    print("🔵 [Graph] Classifier...")
    data = researcher.analyze_intent(state['raw_text'])
    return {"intent_type": data.get('type', 'Humanities')}

def node_domain_router(state: AgentState) -> AgentState:
    intent = state.get("intent_type", "Humanities")
    # 模糊匹配，默认社科
    domain = INTENT_TO_DOMAIN.get(intent, KnowledgeDomain.HUMANITIES)
    
    # 这里也要顺便把 notion_database_id 确定下来
    import notion_ops
    db_map = {
        KnowledgeDomain.SPANISH: notion_ops.DB_SPANISH_ID,
        KnowledgeDomain.TECH: notion_ops.DB_TECH_ID,
        KnowledgeDomain.HUMANITIES: notion_ops.DB_HUMANITIES_ID
    }
    return {
        "knowledge_domain": domain,
        "notion_database_id": db_map.get(domain)
    }

def node_memory(state: AgentState) -> AgentState:
    domain = state.get("knowledge_domain")
    print(f"🔵 [Graph] Memory (Domain: {domain.value})...")
    # ✅ 直接传 domain.value，不再报错
    match = researcher.consult_memory(state["raw_text"], domain=domain.value)
    return {"memory_match": match}

def node_researcher(state: AgentState) -> AgentState:
    print(f"🔵 [Graph] Researcher (Attempt {state.get('retry_count', 0) + 1})...")
    # ✅ 直接传 error_message，实现自我纠错
    draft = researcher.draft_content(
        state["raw_text"],
        state["intent_type"],
        error_context=state.get("error_message", "")
    )
    return {"draft": draft}

def node_validator(state: AgentState) -> AgentState:
    print("🔵 [Graph] Validator...")
    draft = state.get("draft", {})
    try:
        # 简单校验：必须有 title 和 summary
        DraftSchema(**{k: v for k, v in draft.items() if k in ['title', 'summary']})
        return {"error_message": ""}
    except ValidationError as e:
        print(f"❌ Validation Failed: {e}")
        return {
            "error_message": str(e),
            "retry_count": state.get("retry_count", 0) + 1
        }

def node_human_review(state: AgentState) -> AgentState:
    print("🟠 [Graph] Human Review...")
    # 如果用户在界面选了覆盖数据库，这里生效
    if state.get("override_database_id"):
        return {"notion_database_id": state.get("override_database_id")}
    return {}

def node_publisher(state: AgentState) -> AgentState:
    print("🔵 [Graph] Publisher...")
    # ✅ 参数完全对齐
    success = editor.publish(
        draft=state['draft'],
        intent_type=state['intent_type'],
        memory_match=state['memory_match'],
        raw_text=state['raw_text'],
        original_url=state['original_url'],
        database_id=state.get("notion_database_id"),
        domain=state.get("knowledge_domain").value
    )
    msg = "✅ Published" if success else "❌ Failed"
    return {"final_output": msg}

# --- Edges ---
def route_after_validation(state: AgentState):
    if not state.get('error_message'): return "human_review"
    if state.get('retry_count', 0) <= 2: return "researcher"
    return "human_review"

# --- Graph Construction ---
workflow = StateGraph(AgentState)
workflow.add_node("perceiver", node_perceiver)
workflow.add_node("classifier", node_classifier)
workflow.add_node("domain_router", node_domain_router)
workflow.add_node("memory", node_memory)
workflow.add_node("researcher", node_researcher)
workflow.add_node("validator", node_validator)
workflow.add_node("human_review", node_human_review)
workflow.add_node("publisher", node_publisher)

workflow.set_entry_point("perceiver")
workflow.add_edge("perceiver", "classifier")
workflow.add_edge("classifier", "domain_router")
workflow.add_edge("domain_router", "memory")
workflow.add_edge("memory", "researcher")
workflow.add_edge("researcher", "validator")
workflow.add_conditional_edges("validator", route_after_validation, {"human_review": "human_review", "researcher": "researcher"})
workflow.add_edge("human_review", "publisher")
workflow.add_edge("publisher", END)

checkpointer = MemorySaver()
app_graph = workflow.compile(checkpointer=checkpointer, interrupt_before=["human_review"])
# ==========================================
# 5. 本地测试入口 (CLI Mode)
# ==========================================
if __name__ == "__main__":
    print("🚀 Starting Graph Test (CLI Mode)...")
    
    # 模拟配置
    config = {"configurable": {"thread_id": "test_cli_thread"}}
    
    # 模拟输入 (这里用西语作为测试)
    initial_state = default_state()
    initial_state["user_input"] = "El verbo Ser se usa para características permanentes."
    
    print(f"📥 Testing with input: {initial_state['user_input']}...")
    
    try:
        # 1. 运行到断点
        print("\n--- Phase 1: Thinking ---")
        for event in app_graph.stream(initial_state, config, stream_mode="values"):
            # 只打印最后更新的键，避免刷屏
            pass 
            
        # 检查当前状态
        snapshot = app_graph.get_state(config)
        if snapshot.next and snapshot.next[0] == "human_review":
            print("\n🛑 Graph paused at 'human_review' successfully.")
            print(f"   Draft Title: {snapshot.values['draft'].get('title')}")
            
            # 2. 模拟人工批准并继续
            print("\n--- Phase 2: Human Approval ---")
            print("👤 Human says: Approve!")
            
            # 继续运行
            for event in app_graph.stream(None, config, stream_mode="values"):
                if "final_output" in event:
                    print(f"\n🏁 Final Output: {event['final_output']}")
                    
    except Exception as e:
        print(f"\n❌ Test Failed: {e}")