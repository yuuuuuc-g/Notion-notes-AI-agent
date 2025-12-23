import sys
from typing import Optional, Any, Dict
from loguru import logger
from agents import ResearcherAgent, EditorAgent
import os

# --- ⚙️ Logger 配置 ---
# 移除默认 handler，添加一个自定义格式的 handler 到 stderr
logger.remove()
logger.add(
    sys.stderr, 
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>", 
    level="INFO"
)

# --- 🎩 Main Workflow: The Orchestrator ---
def main_workflow(user_input: Optional[str] = None, uploaded_file: Optional[Any] = None) -> None:
    """
    主流程编排器
    :param user_input: 用户输入的文本或 URL
    :param uploaded_file: Streamlit 上传的文件对象
    """
    # 1. 组建团队 (Initialize Agents)
    researcher = ResearcherAgent()
    editor = EditorAgent()

    # 2. 研究员：感知 (Perceive)
    # 这一步会处理 URL 抓取或 PDF 读取
    raw_text: Optional[str] = None
    original_url: Optional[str] = None
    
    try:
        raw_text, original_url = researcher.perceive(user_input, uploaded_file)
    except Exception as e:
        logger.error(f"Perception layer failed: {e}")
        raise e

    if not raw_text:
        logger.error("Input processing failed (Empty content).")
        raise Exception("Input processing failed (Empty content).")

    # 3. 研究员：分析意图 (Classify)
    logger.info("🚦 Orchestrator: Analyzing intent...")
    intent_data: Dict[str, str] = researcher.analyze_intent(raw_text)
    intent_type: str = intent_data.get('type', 'General')
    logger.info(f"👉 Intent Detected: {intent_type}")

    # 4. 研究员：查重 (Memory Search)
    memory_match: Dict[str, Any] = researcher.consult_memory(raw_text)

    # 5. 研究员：起草 (Drafting with R1)
    # 这一步会调用 agents.py 里那个高级的 Prompt
    draft: Optional[Dict[str, Any]] = researcher.draft_content(raw_text, intent_type)
    
    if not draft:
        logger.error("Research draft failed (AI returned nothing).")
        raise Exception("Research draft failed (AI returned nothing).")

    # 6. 主编：审核与发布 (Publishing)
    logger.info("✍️ Orchestrator: Handing over to Editor...")
    
    try:
        # Editor 会决定是合并还是新建，并负责写入 Notion 和 向量库
        success: bool = editor.publish(
            draft=draft, 
            intent_type=intent_type, 
            memory_match=memory_match, 
            raw_text=raw_text, 
            original_url=original_url
        )

        if success:
            logger.success("✅ Workflow Completed Successfully.")
        else:
            logger.error("Publication failed inside Editor.")
            raise Exception("Publication failed.")
            
    except Exception as e:
        logger.error(f"Editor execution error: {e}")
        raise e

if __name__ == "__main__":
    # 本地测试入口
    # 你可以在这里写死一个文本直接 python main.py 跑，不用每次都开网页
    # main_workflow(user_input="Test content")
    pass