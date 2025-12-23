💠 AI Knowledge Agent (Personal Knowledge Pipeline)<div align="center">
<h3> <h3> 🚀 具备“自我纠错”能力的知识管理智能体 </h3>

<p>
<b>循环图架构</b> • <b>人机回环 (HITL)</b> • <b>向量记忆</b> • <b>多模态感知</b>
</p>


</div>

📖 项目简介 (Introduction)

AI Knowledge Agent 是一个基于 LangGraph 架构构建的智能知识流水线。与传统的线性脚本不同，它是一个有状态的图系统 (Stateful Graph System)。

它具备反思与纠错能力：如果 AI 生成的笔记格式不达标，系统会自动打回重写，直到满足要求。同时引入了 Human-in-the-loop (人机回环) 机制，让用户在最终写入 Notion 前拥有审核权。

✨ 核心亮点 (Key Features)

特性模块

技术深度描述

🔄 自我纠错循环

引入 Validator 节点。如果 LLM 生成的 JSON 格式错误或缺失关键字段，系统会自动回滚到 Researcher 节点并附带错误日志，强制 AI 重试 (Retry)，直到通过验证。

✋ 人机回环 (HITL)

利用 LangGraph 的 interrupt_before 机制，在写入数据库前暂停运行。用户可以在 UI 上预览、修改 AI 生成的草稿，点击批准后系统才会继续执行。

🧠 动态向量记忆

内置 ChromaDB。每次处理新内容前，先进行语义检索。如果发现相似主题，自动触发“融合策略 (Merge)”而非新建，实现知识的有机生长。

🇪🇸 智能重构引擎

针对西语学习场景，通过 DeepSeek-R1 进行深度推理，将非结构化文本重构为 Notion 的 Table (对比表)、Heading (层级) 和 List (知识点)。

🌍 多模态感知

集成 yt-dlp 和 PyMuPDF，支持 YouTube 视频字幕提取、PDF 论文解析、网页抓取 以及 纯文本 输入。

🏗️ 系统架构 (System Architecture)

采用 StateGraph (状态图) 架构：

graph TD
    Start([Start]) --> Perceiver
    
    subgraph "🕵️‍♂️ Researcher Agent"
        Perceiver[感知节点: PDF/URL] --> Classifier[分类节点]
        Classifier --> Memory[记忆检索节点]
        Memory --> Researcher[撰写节点: DeepSeek-R1]
    end
    
    Researcher --> Validator{格式验证?}
    
    subgraph "Self-Correction Loop (自我纠错)"
        Validator -- "❌ 格式错误 (Retry)" --> Researcher
    end
    
    Validator -- "✅ 通过" --> HumanReview
    
    subgraph "✍️ Editor Agent"
        HumanReview[🛑 人工审批 (HITL)] --> Publisher[发布节点: Notion API]
    end
    
    Publisher --> End([End])

    style Validator fill:#f96,stroke:#333,stroke-width:2px
    style HumanReview fill:#69f,stroke:#333,stroke-width:4px


📂 项目结构 (Directory)

📦 notion-ai-agent
 ┣ 📜 app.py             # 🎨 前端入口：处理 Streamlit 状态与 HITL 交互
 
 ┣ 📜 graph_agent.py     # 🕸️ 核心架构：定义 State, Nodes, Edges 和 Workflow 图
 
 ┣ 📜 agents.py          # 🧠 业务逻辑：封装 Researcher 和 Editor 的具体能力
 
 ┣ 📜 notion_ops.py      # ✍️ 执行工具：处理 Notion Block 组装与 API 交互
 
 ┣ 📜 vector_ops.py      # 💾 记忆工具：ChromaDB 向量检索
 
 ┣ 📜 web_ops.py         # 🌐 网络工具：视频/网页抓取
 
 ┣ 📜 file_ops.py        # 📄 文件工具：PDF 解析
 
 ┣ 📜 llm_client.py      # 🤖 模型接口：封装 DeepSeek API
 
 ┣ 📜 requirements.txt   # 📦 依赖清单
 
 ┗ 📜 README.md          # 📄 项目文档


🚀 快速开始 (Quick Start)

1. 环境配置

git clone [https://github.com/your-username/notion-ai-agent.git](https://github.com/your-username/notion-ai-agent.git)

cd notion-ai-agent

pip install -r requirements.txt


2. 填写密钥 (.env)

OPENAI_API_KEY="sk-..."

OPENAI_BASE_URL="[https://api.deepseek.com](https://api.deepseek.com)"

NOTION_TOKEN="secret_..."

NOTION_DATABASE_ID="..."          # 西语库

NOTION_DATABASE_ID_TECH="..."     # 科技库

NOTION_DATABASE_ID_HUMANITIES="..." # 社科库


3. 启动应用

streamlit run app.py


📸 运行流程 (Workflow)

Input: 用户上传 PDF 或粘贴 URL。

Think: Agent 分析意图，并检索是否有重复笔记。

Draft: DeepSeek-R1 生成结构化笔记草稿。

Review (HITL): 网页弹出草稿预览，等待用户确认。

Publish: 用户点击 Approve，数据写入 Notion。

<div align="center">
