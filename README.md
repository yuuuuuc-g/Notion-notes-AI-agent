💠 AI Knowledge Agent (Personal Knowledge Pipeline)<div align="center"><h3> 🚀 你的第二大脑自动化构建流水线 </h3><p><b>多智能体协作</b> • <b>向量语义检索</b> • <b>多模态输入</b> • <b>结构化归档</b></p>点击体验在线 Demo | 查看详细文档 | 报告 Bug</div>📖 项目简介 (Introduction)Knowledge AI Agent 是一个全栈 AI 知识管理系统。它不再是一个简单的聊天机器人，而是一个不知疲倦的智能编辑团队。它能处理 PDF 文档、YouTube 视频、网页链接 或 纯文本，利用 DeepSeek-R1 进行深度思考与重构，最终将结构化的知识自动存入你的 Notion 知识库。它解决了“收藏从未阅读”的痛点，实现了从信息获取到知识沉淀的全自动化。✨ 核心亮点 (Key Features)功能模块亮点描述🤖 双智能体架构Researcher 负责感知与深度思考，Editor 负责决策与排版，分工明确，逻辑解耦。🧠 向量长期记忆内置 ChromaDB，对每一条笔记进行向量化存储。新笔记录入时自动进行语义查重，避免重复，支持增量合并。🇪🇸 深度西语模式专为语言学习者设计。自动提取核心词汇表、例句，并将枯燥的语法点重构为清晰的对比表格。🌍 通用知识图谱支持 Tech (科技) 与 Humanities (社科) 自动分类。对于长文，自动生成 Key Points 和 深度摘要。🛡️ 工程级鲁棒性实现了底层 httpx 通道绕过 SDK 限制；内置数据清洗器；解决了 Streamlit 状态管理痛点。🏗️ 系统架构 (Architecture)本项目采用了 Orchestrator-Workers (指挥官-工人) 模式，数据流向清晰可控：graph TD
    User((用户输入)) -->|PDF / URL / Text| UI[Streamlit 前端]
    UI -->|触发| Main{Main Orchestrator}
    
    subgraph "🕵️‍♂️ Researcher Agent (感知与思考)"
        Main -->|1. 感知| WebOps[Web/PDF 解析器]
        Main -->|2. 分类| Router[意图识别器]
        Main -->|3. 回忆| VectorDB[(ChromaDB 向量库)]
        Main -->|4. 起草| Reasoning[DeepSeek-R1 推理]
    end
    
    subgraph "✍️ Editor Agent (决策与执行)"
        Main -->|5. 移交| Editor
        Editor -->|检查结构| NotionRead[读取页面结构]
        Editor -->|决策: 合并or新建| Strategy{合并策略}
        Strategy -->|插入表格行| NotionWrite[Notion API]
        Strategy -->|追加文本块| NotionWrite
    end
    
    Editor -->|6. 归档记忆| VectorDB
    NotionWrite -->|7. 最终产出| Notion[(Notion Database)]
📂 项目结构 (Directory)📦 notion-ai-agent
 ┣ 📂 .streamlit       # Streamlit 配置
 ┣ 📜 app.py           # 前端入口：处理 UI 交互与状态流
 ┣ 📜 main.py          # 总指挥：协调 Agent 协作
 ┣ 📜 agents.py        # 智能体核心：封装 Researcher 与 Editor 类
 ┣ 📜 notion_ops.py    # 执行层：处理复杂的 Notion Block 组装与 API 交互
 ┣ 📜 vector_ops.py    # 记忆层：ChromaDB 向量检索与存储
 ┣ 📜 web_ops.py       # 网络层：yt-dlp 视频解析与网页抓取
 ┣ 📜 file_ops.py      # 文件层：PDF 文本提取
 ┣ 📜 llm_client.py    # 模型层：DeepSeek API 封装
 ┣ 📜 requirements.txt # 依赖清单
 ┗ 📜 README.md        # 项目文档
🚀 快速开始 (Quick Start)1. 环境准备确保本地已安装 Python 3.9+。git clone [https://github.com/your-username/notion-ai-agent.git](https://github.com/your-username/notion-ai-agent.git)
cd notion-ai-agent
pip install -r requirements.txt
2. 配置密钥 (.env)在项目根目录新建 .env 文件，填入你的 API Key：OPENAI_API_KEY="sk-..."
OPENAI_BASE_URL="[https://api.deepseek.com](https://api.deepseek.com)"
NOTION_TOKEN="secret_..."
NOTION_DATABASE_ID="..."          # 西语库 ID
NOTION_DATABASE_ID_TECH="..."     # 科技库 ID
NOTION_DATABASE_ID_HUMANITIES="..." # 社科库 ID
3. 启动应用
streamlit run app.py
