import operator
from typing import Annotated, TypedDict, Union, List, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver # 🌟 关键：内存检查点

# 导入业务逻辑
from agents import ResearcherAgent, EditorAgent

# 初始化智能体
researcher = ResearcherAgent()
editor = EditorAgent()

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
    memory_match: Dict
    
    # 核心产物
    draft: Dict
    
    # 控制流
    retry_count: int
    error_message: str
    final_output: str

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
        "retry_count": 0,
        "error_message": ""
    }

def node_classifier(state: AgentState) -> AgentState:
    """分类：判断意图"""
    print("🔵 [Graph] Classifier: Analyzing intent...")
    intent_data = researcher.analyze_intent(state['raw_text'])
    return {"intent_type": intent_data.get('type', 'General')}

def node_memory(state: AgentState) -> AgentState:
    """记忆：查重"""
    print("🔵 [Graph] Memory: Searching vector DB...")
    match = researcher.consult_memory(state['raw_text'])
    return {"memory_match": match}

def node_researcher(state: AgentState) -> AgentState:
    """研究员：生成草稿"""
    print(f"🔵 [Graph] Researcher: Drafting content (Attempt {state.get('retry_count', 0) + 1})...")
    
    # 这里的草稿生成逻辑已经包含了对西语/通用的不同处理
    draft = researcher.draft_content(state['raw_text'], state['intent_type'])
    return {"draft": draft}

def node_validator(state: AgentState) -> AgentState:
    """验证：检查 JSON"""
    print("🔵 [Graph] Validator: Checking format...")
    draft = state.get('draft')
    
    # 简单的验证逻辑：确保有标题
    if draft and isinstance(draft, dict) and 'title' in draft:
        return {"error_message": ""}
    else:
        print("❌ [Graph] Validation Failed: Missing title or invalid JSON.")
        return {
            "error_message": "Invalid JSON or missing title.", 
            "retry_count": state.get('retry_count', 0) + 1
        }

def node_human_review(state: AgentState) -> AgentState:
    """
    🛑 人工审批节点
    LangGraph 会在这里暂停（通过 interrupt_before），
    等待 Streamlit 界面更新 state 后再恢复。
    """
    print("🟠 [Graph] Human Review: Paused for user feedback...")
    return {} 

def node_publisher(state: AgentState) -> AgentState:
    """发布：写入 Notion"""
    print("🔵 [Graph] Publisher: Writing to Notion...")
    
    success = editor.publish(
        draft=state['draft'], # 此时的 draft 可能是用户修改过的
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
workflow.add_node("memory", node_memory)
workflow.add_node("researcher", node_researcher)
workflow.add_node("validator", node_validator)
workflow.add_node("human_review", node_human_review)
workflow.add_node("publisher", node_publisher)

# 设置流程线
workflow.set_entry_point("perceiver")
workflow.add_edge("perceiver", "classifier")
workflow.add_edge("classifier", "memory")
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
        "user_input": "DeepSeek-V3 是一篇关于 AI 的论文...", # 测试文本
        "uploaded_file": None,
        "retry_count": 0
    }
    
    print(f"📥 Testing with input: {initial_state['user_input'][:20]}...")
    
    # 运行图
    for event in app_graph.stream(initial_state, config, stream_mode="values"):
        # 打印当前步骤更新了哪些字段
        updated_keys = list(event.keys())
        print(f"🔄 Graph Update: {updated_keys}")
        
    print("\n🛑 Graph paused at 'human_review' (Expected behavior).")