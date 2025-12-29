from typing import TypedDict
from enum import Enum

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agents import ResearcherAgent, EditorAgent
import notion_ops
import vector_ops

# Initialize agent instances
researcher = ResearcherAgent()
editor = EditorAgent()

# =========================================================
# State Definitions
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


class AnalysisState(TypedDict, total=False):
    intent_type: str        # query_knowledge | save_note
    category: str           # Spanish | Tech | Humanities (原始分类)
    domain: KnowledgeDomain # 映射后的领域枚举
    routing: str            # query | save
    confidence: float


class DraftState(TypedDict, total=False):
    title: str
    summary: str
    content: str
    tags: list[str]
    is_merge: bool          
    merge_target_id: str    
    

class MemoryState(TypedDict, total=False):
    query_results: dict
    write_payload: dict


class AgentState(TypedDict, total=False):
    # Input
    user_input: str
    raw_text: str
    original_url: str

    # Core States
    analysis: AnalysisState
    draft: DraftState
    memory: MemoryState

    # Meta
    retry_count: int
    error_message: str

    # Output
    final_output: str
    published_page_id: str


# =========================================================
# Nodes
# =========================================================

def node_memory_saver(state: AgentState) -> AgentState:
    """
    记忆保存节点：将已发布的页面保存到向量数据库，便于后续检索
    """
    print("💾 [Graph] Saving to Memory...")
    
    # 提取标题和摘要（优先从草稿中获取）
    title = "Untitled"
    summary = ""
    
    if state.get("draft"):
        title = state["draft"].get("title", "Untitled")
        summary = state["draft"].get("summary", "No summary provided.")

    # 只有当页面已发布时，才保存到记忆库
    if state.get("published_page_id"):
        vector_ops.add_memory(
            page_id=state["published_page_id"],
            content=state["raw_text"],
            title=title,
            category=state["analysis"]["domain"].value,
            metadata={
                "url": state.get("original_url", ""),
                "type": state["analysis"].get("intent_type", ""),
                "summary": summary  # 将摘要存入元数据，供查询时使用
            }
        )
        return {"final_output": state.get("final_output", "") + "\n(Saved to Memory)"}
    return {}


def node_recall_context(state: AgentState) -> AgentState:
    """
    通用召回节点：无论是回答问题还是写笔记，都先看看记忆库里有什么
    """
    print("🔍 [Recall] Checking Memory...")
    # 强制全库搜索，找出最相关的笔记
    results = researcher.consult_memory(state["raw_text"], domain="All")
    
    return {
        "memory": {"query_results": results}
    }

def route_after_recall(state: AgentState):
    """
    检索后的分流：
    1. 如果是提问 (query) -> 去回答
    2. 如果是保存 (save) 且找到相关笔记 -> 去融合 (Merge)
    3. 如果是保存 (save) 且无相关笔记 -> 去新建 (Draft)
    """
    intent = state["analysis"]["intent_type"]
    memory_match = state["memory"].get("query_results", {}).get("match", False)

    print(f"🔀 [Router] Intent: {intent}, Memory Match: {memory_match}")

    if intent == "query_knowledge":
        return "generate_answer"
    elif intent == "save_note" and memory_match:
        return "merge_draft"
    else:
        return "new_draft"
    
    
def node_perceiver(state: AgentState) -> AgentState:
    """
    感知节点：预处理输入，统一提取 raw_text 和 original_url
    这是工作流的入口节点，负责数据清洗和标准化
    """
    print("🔵 [Graph] Perceiver...")
    raw_text = (state.get("raw_text") or state.get("user_input") or "").strip()

    if not raw_text:
        raise ValueError("Perceiver requires pre-processed raw_text")

    return {
        "raw_text": raw_text,
        "original_url": state.get("original_url", ""),
    }


def node_analyzer(state: AgentState) -> AgentState:
    """
    分析节点：分析用户意图和知识领域
    输出 intent_type (query_knowledge/save_note)、category (Spanish/Tech/Humanities) 和对应的 domain
    """
    print("🧠 [Analysis] Intent & Domain Detection")

    result = researcher.analyze_intent(state["raw_text"])

    # 兼容处理：确保字段存在
    intent = result.get("intent", "save_note")
    # 如果 analyze_intent 返回的是 "save_note" 或 "query_knowledge"，需要做一下映射
    if "query" in intent:
        routing = "query"
    else:
        routing = "save"
        
    category = result.get("category", "Humanities")
    domain = INTENT_TO_DOMAIN.get(category, KnowledgeDomain.HUMANITIES)

    print(f"   -> Intent: {intent}, Category: {category}, Domain: {domain.value}")

    return {
        "analysis": {
            "intent_type": intent,
            "category": category,  # 保存原始分类，供 draft_content 使用
            "domain": domain,
            "routing": routing,
            "confidence": result.get("confidence", 0.7),
        }
    }


def node_query_memory(state: AgentState) -> AgentState:
    """
    查询记忆节点：格式化并输出记忆库查询结果
    注意：复用 recall_context 节点的查询结果，避免重复查询
    """
    print("🔍 [Query] Formatting Memory Search Results")

    # 复用 recall_context 节点的查询结果，避免重复查询
    results = state.get("memory", {}).get("query_results", {})
    
    # 如果没有结果（理论上不应该发生），则进行一次查询作为兜底
    if not results:
        print("⚠️ [Query] No cached results, performing search...")
        results = researcher.consult_memory(state["raw_text"], domain="All")

    # 格式化输出查询结果
    if results.get("match"):
        # 构造 Notion 链接
        page_id = results["page_id"].replace("-", "")
        notion_url = f"https://www.notion.so/{page_id}"
        
        title = results.get("title", "Untitled")
        # 从 metadata 中提取摘要 (如果旧数据没有摘要，提供默认文案)
        summary = results.get("metadata", {}).get("summary", "（该笔记暂无摘要元数据）")
        
        # 🎯 简洁的卡片式输出
        final_output = (
            f"✅ **已找到相关笔记**\n\n"
            f"📄 **[{title}]({notion_url})**\n\n"
            f"💡 **摘要**：\n{summary}"
        )
    else:
        final_output = "❌ 未在知识库中找到相关文章。"

    return {
        "memory": {"query_results": results},
        "final_output": final_output
    }


def node_draft_new(state: AgentState) -> AgentState:
    """
    新建草稿节点：根据原始文本创建新的笔记草稿
    使用 ResearcherAgent 的 draft_content 方法生成结构化内容
    """
    print("✍️ [Draft] Creating New Note")
    # draft_content 需要 category (Spanish/Tech/Humanities) 作为第二个参数
    category = state["analysis"].get("category", "Humanities")
    draft = researcher.draft_content(
        state["raw_text"],
        category
    )
    return {"draft": draft}


def node_draft_merge(state: AgentState) -> AgentState:
    """
    合并草稿节点：将新内容与现有笔记合并
    """
    print("⚗️ [Merge] Merging with Existing Note")
    existing_note = state["memory"]["query_results"]
    
    # 获取旧笔记全文 (需要调用 notion_ops 获取详情，因为向量库里只有片段)
    old_content = notion_ops.get_page_text(existing_note["page_id"])
    
    # 调用 Researcher 的 merge_content 方法进行内容融合
    merged_draft = researcher.merge_content(old_content, state["raw_text"])
    
    merged_draft["is_merge"] = True
    merged_draft["merge_target_id"] = existing_note["page_id"]
    
    return {"draft": merged_draft}

def node_publisher(state: AgentState) -> AgentState:
    """
    发布节点：将草稿发布到 Notion 对应的数据库
    """
    print("📰 [Publish] Publishing to Notion")
    
    current_domain = state["analysis"]["domain"]

    # 根据领域动态选择目标数据库
    db_map = {
        KnowledgeDomain.SPANISH: notion_ops.DB_SPANISH_ID,
        KnowledgeDomain.TECH: notion_ops.DB_TECH_ID,
        KnowledgeDomain.HUMANITIES: notion_ops.DB_HUMANITIES_ID,
    }
    target_db_id = db_map.get(current_domain, notion_ops.DB_HUMANITIES_ID)

    result = editor.publish(
        draft=state["draft"],
        intent_type=state["analysis"]["intent_type"],
        memory_match=None,  # 新流程中记忆匹配在 recall_context 节点处理，publisher 不再需要
        raw_text=state["raw_text"],
        original_url=state.get("original_url"),
        database_id=target_db_id,  # 使用映射后的 ID
        domain=current_domain.value,
    )

    if not result.get("success"):
        return {"final_output": "❌ 发布失败"}

    return {
        "published_page_id": result["page_id"],
        "final_output": f"✅ 已发布到 Notion ({current_domain.value})"
    }


# =========================================================
# Graph Build
# =========================================================
workflow = StateGraph(AgentState)

# 注册所有节点
workflow.add_node("perceiver", node_perceiver)
workflow.add_node("analyzer", node_analyzer)
workflow.add_node("query_memory", node_query_memory)
workflow.add_node("recall_context", node_recall_context)
workflow.add_node("draft_new", node_draft_new)
workflow.add_node("draft_merge", node_draft_merge)  # 合并草稿节点
workflow.add_node("publisher", node_publisher)
workflow.add_node("memory_saver", node_memory_saver)

# 设置入口点
workflow.set_entry_point("perceiver")

# 定义边：必须在编译之前完成所有边的添加
workflow.add_edge("perceiver", "analyzer")
workflow.add_edge("analyzer", "recall_context")  # 分析后先去检索记忆库

# 条件路由：根据意图和记忆匹配结果决定下一步
workflow.add_conditional_edges(
    "recall_context",
    route_after_recall,
    {
        "generate_answer": "query_memory",  # 查询意图 -> 查询记忆节点
        "merge_draft": "draft_merge",       # 保存意图 + 找到相关笔记 -> 合并草稿
        "new_draft": "draft_new"            # 保存意图 + 无相关笔记 -> 新建草稿
    }
)

# 草稿创建路径：都指向发布节点
workflow.add_edge("draft_new", "publisher")
workflow.add_edge("draft_merge", "publisher")

# 发布后保存到记忆库
workflow.add_edge("publisher", "memory_saver")

# 查询路径和保存路径的终点
workflow.add_edge("query_memory", END)      # 查询完成直接结束
workflow.add_edge("memory_saver", END)      # 保存完成后结束

# 编译带检查点的图（用于 Streamlit，支持中断和恢复）
checkpointer = MemorySaver()
app_graph = workflow.compile(
    checkpointer=checkpointer,
    interrupt_before=["publisher"]  # 在发布前暂停，等待人工审查
)

# 用于 CLI 的无状态版本（无检查点，连续执行）
app = workflow.compile()

# ==========================================
# 本地运行入口 (CLI Entry Point)
# ==========================================
if __name__ == "__main__":
    import os
    
    TEST_FILE_NAME = "test_input.txt"
    print(f"🚀 Starting Local Graph Test...")

    if os.path.exists(TEST_FILE_NAME):
        try:
            with open(TEST_FILE_NAME, "r", encoding="utf-8") as f:
                test_input = f.read().strip()
            if not test_input:
                test_input = "什么是批判性思维？" 
            else:
                print(f"📂 成功读取文件: {TEST_FILE_NAME}")
        except Exception as e:
            print(f"❌ 读取文件出错: {e}")
            test_input = "Error."
    else:
        with open(TEST_FILE_NAME, "w", encoding="utf-8") as f:
            f.write("在这里粘贴你想测试的内容...")
        test_input = "什么是经济租？"

    print("-" * 50)

    # 构造初始状态
    initial_state = {
        "user_input": test_input,
        "raw_text": test_input,
        "analysis": {},
        "draft": {},
        "memory": {},
        "final_output": "",
    }

    try:
        final_state = app.invoke(initial_state)
        
        print("\n" + "="*50)
        print("✅ Workflow Completed!")
        print("="*50)
        
        print(f"📝 Final Output:\n{final_state.get('final_output')}")
        
        if final_state.get("published_page_id"):
             print(f"🎉 Page ID: {final_state.get('published_page_id')}")

    except Exception as e:
        print(f"\n❌ Graph Execution Error: {e}")
        import traceback
        traceback.print_exc()