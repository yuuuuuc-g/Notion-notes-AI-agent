from agents import ResearcherAgent, EditorAgent
import os

# --- 🎩 Main Workflow: The Orchestrator ---
def main_workflow(user_input=None, uploaded_file=None):
    # 1. 初始化智能体团队
    researcher = ResearcherAgent()
    editor = EditorAgent()

    # 2. 研究员：处理输入与感知
    raw_text, original_url = researcher.perceive(user_input, uploaded_file)
    if not raw_text:
        raise Exception("Input processing failed (Empty content).")

    # 3. 研究员：分析意图
    print("🚦 Orchestrator: Analyzing intent...")
    intent_data = researcher.analyze_intent(raw_text)
    intent_type = intent_data.get('type', 'General')
    print(f"👉 Intent Detected: {intent_type}")

    # 4. 研究员：检索记忆
    memory_match = researcher.consult_memory(raw_text)

    # 5. 研究员：起草内容 (R1 深度思考)
    draft = researcher.draft_content(raw_text, intent_type)
    if not draft:
        raise Exception("Research draft failed.")

    # 6. 主编：审核与发布 (Notion + Vector)
    print("✍️ Orchestrator: Handing over to Editor...")
    success = editor.publish(
        draft=draft, 
        intent_type=intent_type, 
        memory_match=memory_match, 
        raw_text=raw_text, 
        original_url=original_url
    )

    if success:
        print("✅ Workflow Completed Successfully.")
    else:
        raise Exception("Publication failed.")

if __name__ == "__main__":
    # Local Testing
    pass