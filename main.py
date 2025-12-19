from agents import ResearcherAgent, EditorAgent
import os

# --- 🎩 Main Workflow: The Orchestrator ---
def main_workflow(user_input=None, uploaded_file=None):
    # 1. 组建团队 (Initialize Agents)
    researcher = ResearcherAgent()
    editor = EditorAgent()

    # 2. 研究员：感知 (Perceive)
    # 这一步会处理 URL 抓取或 PDF 读取
    raw_text, original_url = researcher.perceive(user_input, uploaded_file)
    if not raw_text:
        raise Exception("Input processing failed (Empty content).")

    # 3. 研究员：分析意图 (Classify)
    print("🚦 Orchestrator: Analyzing intent...")
    intent_data = researcher.analyze_intent(raw_text)
    intent_type = intent_data.get('type', 'General')
    print(f"👉 Intent Detected: {intent_type}")

    # 4. 研究员：查重 (Memory Search)
    memory_match = researcher.consult_memory(raw_text)

    # 5. 研究员：起草 (Drafting with R1)
    # 这一步会调用 agents.py 里那个高级的 Prompt
    draft = researcher.draft_content(raw_text, intent_type)
    if not draft:
        raise Exception("Research draft failed (AI returned nothing).")

    # 6. 主编：审核与发布 (Publishing)
    print("✍️ Orchestrator: Handing over to Editor...")
    # Editor 会决定是合并还是新建，并负责写入 Notion 和 向量库
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
    # 本地测试入口
    # 你可以在这里写死一个文本直接 python main.py 跑，不用每次都开网页
    pass