💠 AI Knowledge Agent (LangGraph Edition)

📖 项目简介 (Introduction)
AI Knowledge Agent 是一个基于 LangGraph 架构构建的智能知识流水线，它是一个有状态的图系统 (Stateful Graph System)。
它具备反思与纠错能力：如果 AI 生成的笔记格式不达标，系统会自动打回重写，直到满足要求。
同时引入了 Human-in-the-loop (人机回环) 机制，让用户在最终写入 Notion 前拥有“上帝视角”的审核权。
✨ 核心亮点 (Key Features)
| 特性模块 | 技术深度描述 
|| 🔄 自我纠错循环 | 引入 Validator 节点。如果 LLM 生成的 JSON 格式错误或缺失关键字段，系统会自动回滚到 Researcher 节点并附带错误日志，强制 AI 重试 (Retry)，直到通过验证。 
|| ✋ 人机回环 (HITL) | 利用 LangGraph 的 interrupt_before 机制，在写入数据库前暂停运行。用户可以在 UI 上预览、修改 AI 生成的草稿，点击批准后系统才会继续执行。 
|| 🧠 动态向量记忆 | 内置 ChromaDB。每次处理新内容前，先进行语义检索。如果发现相似主题，自动触发“融合策略 (Merge)”而非新建，实现知识的有机生长。 
|| 🇪🇸 智能重构引擎 | 针对西语学习场景，通过 DeepSeek-R1 进行深度推理，将非结构化文本重构为 Notion 的 Table (对比表)、Heading (层级) 和 List (知识点)。 
|| 🌍 多模态感知 | 集成 yt-dlp 和 PyMuPDF，支持 YouTube 视频字幕提取、PDF 论文解析、网页抓取 以及 纯文本 输入。 
|| 🧭 语义驱动的数据流 | 先进行语义归类（KnowledgeDomain），再由 Graph 决定写入目标数据库，实现“语义 → 数据去向”的集中式决策，避免规则分散与隐式耦合。 
|🏗️ 系统架构 (System Architecture)

```mermaid
graph TD
    Start([Start])

    %% ===== Input Layer =====
    Start --> Perceiver

    subgraph "🕵️‍♂️ Researcher Agent（感知 & 生成）"
        Perceiver[Perceiver<br/>多模态感知<br/>(Text / PDF / URL / Video)]
        Classifier[Classifier<br/>意图识别]
        DomainRouter[Domain Router<br/>语义归类<br/>(KnowledgeDomain)]
        Memory[Memory Node<br/>向量检索<br/>(Single Vector DB + Domain Metadata)]
        Researcher[Researcher<br/>内容生成 / 重写<br/>(LLM)]
    end

    Perceiver --> Classifier
    Classifier --> DomainRouter
    DomainRouter --> Memory
    Memory --> Researcher

    %% ===== Validation & Retry =====
    Researcher --> Validator{Validator<br/>Schema 校验}

    subgraph "🔁 Self-Correction Loop"
        Validator -- "❌ 校验失败" --> Researcher
    end

    %% ===== Human-in-the-loop =====
    Validator -- "✅ 校验通过" --> HumanReview

    subgraph "✋ Human-in-the-loop"
        HumanReview[Human Review<br/>人工审核 / 编辑<br/>可覆盖 KnowledgeDomain]
    end

    %% ===== Publish Layer =====
    subgraph "✍️ Editor Agent（执行层）"
        Publisher[Publisher<br/>Notion 写入<br/>(Database by Domain)]
    end

    HumanReview --> Publisher
    Publisher --> End([End])

    %% ===== Styles =====
    style Validator fill:#f96,stroke:#333,stroke-width:2px
    style HumanReview fill:#69f,stroke:#333,stroke-width:3px
    style DomainRouter fill:#bbf,stroke:#333,stroke-width:2px
    style Memory fill:#9f9,stroke:#333,stroke-width:2px
```

### 🧭 架构设计说明（Architecture Notes）

- **StateGraph = 控制平面（Control Plane）**  
  Graph 负责“状态流转、语义决策与流程控制”，而非具体业务实现。

- **KnowledgeDomain = 语义层（Semantic Layer）**  
  系统首先判断“这是什么类型的知识”，再由 Graph 映射到具体的 Notion Database。
  Database ID 不散落在 Agent 内部，而由 Graph 统一决策。

- **单一向量库 + Domain Metadata**  
  当前 Memory 仅使用一个向量数据库（ChromaDB），但每条向量均携带 domain 作为 metadata：
  - 保证跨领域语义连续性
  - 为未来 domain-aware recall / rerank 预留接口
  - 避免过早拆分向量库带来的召回质量下降

- **Human-in-the-loop 是治理接口，而非补丁**  
  人工审核节点不仅用于“Approve / Reject”，
  还可以在发布前覆盖 KnowledgeDomain，实现对自动决策的最终裁决。

- **Editor Agent 是纯执行单元**  
  Editor 不再判断写入哪个数据库，只负责：
  - 接收 Graph 决定的 database_id
  - 将结构化内容写入 Notion

📂 项目结构 (Directory)📦 notion-ai-agent
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

2. 填写密钥 (.env)OPENAI_API_KEY="sk-..."
OPENAI_BASE_URL="[https://api.deepseek.com](https://api.deepseek.com)"
NOTION_TOKEN="secret_..."
NOTION_DATABASE_ID="..."          # 西语库
NOTION_DATABASE_ID_TECH="..."     # 科技库
NOTION_DATABASE_ID_HUMANITIES="..." # 社科库

3. 启动应用streamlit run app.py
