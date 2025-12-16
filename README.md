# 🇪🇸 AI Spanish Knowledge Agent (西语学习智能助手)

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B)
![Notion](https://img.shields.io/badge/Integration-Notion_API-000000)
![DeepSeek](https://img.shields.io/badge/AI-DeepSeek_V3-blueviolet)
![Status](https://img.shields.io/badge/Status-Deployed-success)

> **"不是简单的笔记搬运工，而是拥有长期记忆、懂得排版美学的智能编辑。"**

这是一个具备 **RAG (检索增强生成)**、**长期记忆** 以及 **Web 可视化界面** 的全栈 AI Agent。它能将零散的非结构化西语笔记，智能转化为 Notion 数据库中的结构化知识，并具备**语义查重**与**增量更新**能力。

🔗 **[点击体验在线 Demo](https://notion-notes-ai-agent-5xjdcivttpj4qtuygwxkey.streamlit.app/)

---

## ✨ 核心功能 (Key Features)

### 1. 🖥️ 可视化交互界面 (Streamlit UI)
* **实时状态流**：通过折叠式状态栏，实时展示 Agent 的思考路径（检索 -> 分析 -> 决策 -> 执行）。
* **透明化交互**：提供 JSON 数据透视面板，可审查 AI 的决策逻辑 (Human-in-the-loop)。

### 2. 🧠 语义查重与记忆 (Semantic Retrieval)
* **痛点解决**：解决传统关键词匹配的弊端。
* **拒绝重复**：自动调取旧页面 ID，进行增量更新，而非新建重复页面。

### 3. 🧩 上下文感知融合 (Context-Aware Merge)
Agent 在追加内容前，会先**读取 (Read)** 现有页面的 Block 结构，并做出智能决策：
* **表格插入 (Insert Row)**：如果新笔记属于现有表格的范畴（如新增一行变位），它会精准插入，保持表格完整。
* **文末追加 (Append)**：如果是新的补充知识，则自动追加到文末。

### 4. 📝 智能重构与排版 (Smart Restructuring)
* **无损重构**：将长篇大论的笔记自动拆解为 **Heading**、**Table**、**List** 和 **Text**。
* **细节保留**：通过 Prompt Engineering 强约束，确保笔记不被 AI 过度摘要。

### 5. 🛡️ 工程鲁棒性 (Technical Robustness)
* **Raw HTTP Fallback**: 针对 Notion 官方 Python 库存在的版本兼容性 Bug (`query` 方法缺失)，底层实现了基于 `httpx` 的原生请求通道，确保 API 调用 100% 稳定。
* **Markdown Sanitation**: 内置数据清洗器，确保 Notion 页面展示整洁无乱码。

---

## 🏗️ 系统架构 (Architecture)

```mermaid
graph TD
    User((用户)) -->|输入笔记| UI[Streamlit Web 界面]
    UI -->|1.调用| Main[Main Controller]
    
    subgraph "大脑 (Reasoning)"
    Main -->|2.分析主题| LLM[DeepSeek API]
    LLM -->|3.返回 JSON| Main
    end
    
    subgraph "记忆 (Memory)"
    Main -->|4.检索现有标题| NotionSearch["Notion API (httpx)"]
    NotionSearch -->|5.语义比对| LLM
    end
    
    subgraph "行动 (Action)"
    Main -->|6.决策: 新建 vs 融合| Ops[Notion Ops]
    Ops -->|7.读取页面结构| NotionRead[Get Page Blocks]
    Ops -->|8.写入/更新| NotionWrite[Create/Update Page]
    end
    
    NotionWrite -->|9.反馈结果| UI

📂 项目结构
.
├── app.py              # Streamlit Web 界面入口
├── main.py             # 核心编排逻辑 (大脑)
├── notion_ops.py       # Notion API 工具集 (双手 - 含 httpx 实现)
├── llm_client.py       # LLM 调用封装
├── note.txt            # CLI 模式输入缓冲
├── requirements.txt    # 依赖列表
└── README.md           # 项目文档