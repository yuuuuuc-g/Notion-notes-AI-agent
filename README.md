🧠 AI Knowledge Agent (Personal Knowledge Pipeline)"Your personal AI editorial team. One Agent to research, one Agent to edit."这是一个基于 多智能体架构 (Multi-Agent Architecture) 的全能知识管理系统。它集成了 RAG (检索增强生成)、向量记忆 (Vector Memory) 和 自动化归档 能力，能够将 PDF、YouTube 视频、网页或文本转化为结构化的 Notion 知识库。🏗️ 系统架构 (System Architecture)本项目采用 Orchestrator-Workers 模式，由 main.py 指挥两个核心智能体协作：graph TD
    User((User)) -->|Input: PDF/URL/Text| UI[Streamlit UI]
    UI -->|Trigger| Orch{Main Orchestrator}
    
    subgraph "🕵️‍♂️ Researcher Agent (Perception & Cognitive)"
        Orch -->|1. Perceive| WebOps[Web/PDF Tools]
        Orch -->|2. Classify| Router[Intent Classifier]
        Orch -->|3. Recall| VectorDB[(ChromaDB Memory)]
        Orch -->|4. Draft| Reasoning[DeepSeek-R1 (Thinking)]
    end
    
    subgraph "✍️ Editor Agent (Decision & Execution)"
        Orch -->|5. Handover| Editor
        Editor -->|Check Structure| NotionRead[Read Page]
        Editor -->|Decision| MergeStrategy{Merge or Create?}
        MergeStrategy -->|Insert Row| NotionWrite[Notion API]
        MergeStrategy -->|Append Text| NotionWrite
    end
    
    Editor -->|6. Memorize| VectorDB
    NotionWrite -->|7. Final Doc| Notion[(Notion Database)]
📂 项目结构 (Directory Structure).
├── app.py                # 🎨 前端交互层 (Streamlit)
│                          - 用户输入界面
│                          - 实时日志显示与状态反馈
│
├── main.py               # 🎩 总指挥 (Orchestrator)
│                          - 初始化智能体团队
│                          - 协调 Researcher 和 Editor 的工作流
│
├── agents.py             # 🤖 智能体核心 (Brain)
│                          - ResearcherAgent: 感知、分类、查重、起草(R1)
│                          - EditorAgent: 决策合并策略、发布内容
│
├── llm_client.py         # 🧠 模型接口层
│                          - 封装 DeepSeek V3 (快速) & R1 (深度思考)
│
├── notion_ops.py         # ✍️ 执行层 (Hands)
│                          - 复杂的 Block 组装 (Heading, Table, List)
│                          - 底层 API 交互与清洗
│
├── vector_ops.py         # 💾 记忆层 (Hippocampus)
│                          - ChromaDB 向量数据库管理
│                          - 语义检索与去重
│
├── web_ops.py            # 🌐 网络感知工具
│                          - yt-dlp 视频字幕提取
│                          - Jina 网页抓取
│
├── file_ops.py           # 📄 文件感知工具 (PDF 解析)
├── requirements.txt      # 📦 Python 依赖
├── packages.txt          # 📦 系统依赖 (ffmpeg)
└── .env                  # 🔑 密钥配置
✨ 核心特性 (Key Features)1. 🤖 双智能体协作 (Researcher & Editor)Researcher：负责“读”和“想”。利用 DeepSeek-R1 的深度推理能力，对长文进行解构，生成高质量草稿。Editor：负责“审”和“写”。判断新知识是否属于已有主题，并决定是新建页面还是插入现有表格。2. 🧠 向量化长期记忆 (Vector Memory)内置 ChromaDB 本地向量数据库。每次处理新知识时，自动在库中进行语义查重。效果：即使用户输入的标题不同（如 "Ser用法" vs "动词 Ser"），Agent 也能识别出是同一主题并自动合并。3. 🇪🇸 深度西语学习模式自动识别西语内容。智能重构：将枯燥的语法点自动转化为 Notion 表格 和 列表。无损保留：通过 Prompt 强约束，确保所有例句和场景描述不被删减。4. 🌍 通用知识图谱支持 Tech (技术) 和 Humanities (社科) 分类。自动生成 Key Points (核心知识点) 和 Summary (摘要)。支持 YouTube 视频转笔记（自动提取字幕）。🚀 快速开始 (Quick Start)1. 安装依赖pip install -r requirements.txt
2. 配置环境 (.env)OPENAI_API_KEY="sk-..."
OPENAI_BASE_URL="[https://api.deepseek.com](https://api.deepseek.com)"
NOTION_TOKEN="secret_..."
NOTION_DATABASE_ID="..."          # 西语库
NOTION_DATABASE_ID_TECH="..."     # 科技库
NOTION_DATABASE_ID_HUMANITIES="..." # 社科库
3. 启动应用streamlit run app.py
Powered by DeepSeek, Notion & Streamlit
---