from typing import TypedDict, Dict, Any, Optional
from enum import Enum

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, ValidationError

from agents import ResearcherAgent, EditorAgent
import notion_ops
import vector_ops

# =========================================================
# Init Agents
# =========================================================
researcher = ResearcherAgent()
editor = EditorAgent()


# =========================================================
# Knowledge Domain
# =========================================================
class KnowledgeDomain(str, Enum):
    SPANISH = "spanish_learning"
    TECH = "tech_knowledge"
    HUMANITIES = "humanities"


INTENT_TO_DOMAIN = {
    "Spanish": KnowledgeDomain.SPANISH,
    "Tech": KnowledgeDomain.TECH,
    "Humanities": KnowledgeDomain.HUMANITIES,
}


# =========================================================
# State Definition
# =========================================================
class AgentState(TypedDict, total=False):
    # Input
    user_input: str
    uploaded_file: Optional[Any]

    # Parsed content
    raw_text: str
    original_url: str

    # Analysis
    intent_type: str
    knowledge_domain: KnowledgeDomain

    # Memory
    memory_match: Dict

    # Draft
    draft: Dict
    retry_count: int
    error_message: str

    # Human review
    human_feedback: str
    override_database_id: str
    notion_database_id: str

    # Publish result
    published_page_id: str
    published_title: str
    final_output: str


def default_state() -> dict:
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
        "human_feedback": "",
        "override_database_id": "",
        "notion_database_id": "",
        "final_output": "",
    }


# =========================================================
# Draft Validation
# =========================================================
class DraftSchema(BaseModel):
    title: str
    summary: str


# =========================================================
# Nodes
# =========================================================
def node_memory_saver(state: AgentState) -> AgentState:
    print("💾 [Graph] Saving to Memory...")
    
    # 只有发布成功才保存
    if state.get("published_page_id"):
        # 将最终确定的标题和内容存入向量库
        vector_ops.add_memory(
            page_id=state["published_page_id"],
            content=state["raw_text"], # 或者存 summary，取决于你想查重的粒度
            title=state["draft"].get("title", "Untitled"),
            category=state["knowledge_domain"].value,
            metadata={
                "url": state.get("original_url", ""),
                "type": state.get("intent_type", "")
            }
        )
        return {"final_output": state["final_output"] + " (Saved to Memory)"}
    return {}

def node_perceiver(state: AgentState) -> AgentState:
    print("🔵 [Graph] Perceiver...")
    raw_text = (state.get("raw_text") or "").strip()

    if not raw_text:
        raise ValueError("Perceiver requires pre-processed raw_text")

    return {
        "raw_text": raw_text,
        "original_url": state.get("original_url", ""),
    }


def node_classifier(state: AgentState) -> AgentState:
    print("🔵 [Graph] Classifier...")
    result = researcher.analyze_intent(state["raw_text"])
    return {"intent_type": result.get("type", "Humanities")}


def node_domain_router(state: AgentState) -> AgentState:
    intent = state.get("intent_type", "Humanities")
    domain = INTENT_TO_DOMAIN.get(intent, KnowledgeDomain.HUMANITIES)

    db_map = {
        KnowledgeDomain.SPANISH: notion_ops.DB_SPANISH_ID,
        KnowledgeDomain.TECH: notion_ops.DB_TECH_ID,
        KnowledgeDomain.HUMANITIES: notion_ops.DB_HUMANITIES_ID,
    }

    return {
        "knowledge_domain": domain,
        "notion_database_id": db_map.get(domain),
    }


def node_memory(state: AgentState) -> AgentState:
    domain = state["knowledge_domain"]
    print(f"🔵 [Graph] Memory (Domain={domain.value})...")
    match = researcher.consult_memory(
        state["raw_text"],
        domain=domain.value,
    )
    return {"memory_match": match}


def node_researcher(state: AgentState) -> AgentState:
    print(f"🔵 [Graph] Researcher (Attempt {state.get('retry_count', 0) + 1})...")
    draft = researcher.draft_content(
        state["raw_text"],
        state["intent_type"],
        error_context=state.get("error_message", ""),
    )
    return {"draft": draft}


def node_validator(state: AgentState) -> AgentState:
    print("🔵 [Graph] Validator...")
    try:
        DraftSchema(
            title=state["draft"].get("title"),
            summary=state["draft"].get("summary"),
        )
        return {"error_message": ""}
    except ValidationError as e:
        print("❌ Validation failed:", e)
        return {
            "error_message": str(e),
            "retry_count": state.get("retry_count", 0) + 1,
        }


def node_human_review(state: AgentState) -> AgentState:
    print("🟠 [Graph] Human Review...")
    if state.get("override_database_id"):
        return {"notion_database_id": state["override_database_id"]}
    return {}


def node_publisher(state: AgentState) -> AgentState:
    """
    Returns:
    {
    "success": bool,
    "page_id": str | None,
    "target_db_id": str | None,
    }
    """
    print("🔵 [Graph] Publisher...")

    result = editor.publish(
        draft=state["draft"],
        intent_type=state["intent_type"],
        memory_match=state["memory_match"],
        raw_text=state["raw_text"],
        original_url=state.get("original_url"),
        database_id=state.get("notion_database_id"),
        domain=state["knowledge_domain"].value,
    )

    if not result["success"]:
        return {"final_output": "❌ Publish failed"}

    return {
        "published_page_id": result["page_id"],
        "published_title": result["title"],
        "final_output": "✅ Published",
    }


# =========================================================
# Routing
# =========================================================
def route_after_validation(state: AgentState):
    if not state.get("error_message"):
        return "human_review"
    if state.get("retry_count", 0) <= 2:
        return "researcher"
    return "human_review"


# =========================================================
# Graph Build
# =========================================================
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
workflow.add_conditional_edges(
    "validator",
    route_after_validation,
    {"human_review": "human_review", "researcher": "researcher"},
)
workflow.add_edge("human_review", "publisher")
workflow.add_node("saver", node_memory_saver)
workflow.add_edge("publisher", "saver")
workflow.add_edge("saver", END)

checkpointer = MemorySaver()
app_graph = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["human_review"],
)