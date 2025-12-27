# 💠 AI Knowledge Agent (LangGraph Edition)

> **拒绝堆砌，让知识有机生长。**
> 一个面向生产环境的 AI Agent，由 LangGraph 驱动，将原始信息转化为**结构化、可审查且持续进化的 Notion 知识库**。

## 🧠 核心理念 (Core Ideas)

### 1. 知识是工作流，而不仅仅是 Prompt

大多数 AI 笔记工具依赖于“单次提示词 → 单次输出”。
本系统将知识创造建模为一个 **状态图 (StateGraph)**：

* 感知 (PDF/文本)
* 意图分类与语义路由
* **记忆召回与融合** (新增的核心逻辑)
* 生成 (严格 JSON Schema)
* **自修复** (错误反馈循环)
* 人工审查
* 发布 (新建或覆盖重写)

每一步都是显式的、可检查的、可调试的。

---

### 2. LangGraph 作为控制平面

LangGraph 在这里不只是用来“连线”，而是作为**控制平面 (Control Plane)**：

* 定义显式的状态转换
* JSON 校验失败时的**递归重试循环**
* 条件分支 (是新建页面，还是融合旧文？)
* 可中断执行 (Human-in-the-loop)

LLM 负责生成内容 —— **图 (Graph) 负责决定下一步发生什么**。

---

### 3. “人机协同”是治理机制，而非补丁

在任何内容被写入 Notion 之前，执行流会被暂停。

人工审查者可以：

* 编辑内容 (标题, 摘要)
* 批准或拒绝
* 覆盖语义分类 (KnowledgeDomain)
* **确认融合策略** (是覆盖旧笔记还是新建)

这将 Agent 从一个“不可控的风险”转变为一个**受治理的系统**。

---

## ✨ 关键特性

| 特性 | 说明 |
| --- | --- |
| ⚗️ **语义融合 (Semantic Merge)** | Agent 不再只是创建副本。如果发现相关笔记，它会**读取**旧内容，与新输入**综合**，并生成一篇更完善的文章。 |
| 🔁 **递归自修复** | `ResearcherAgent` 内置 3 次 `try...catch` 循环。如果生成的 JSON 格式错误，错误上下文会被回传给 LLM 进行自我修正。 |
| ✋ **人机协同 (HITL)** | 使用 LangGraph 的 `interrupt_before` 在发布前暂停，确保人类拥有最终决定权。 |
| 🧠 **富向量记忆** | 优化后的 ChromaDB 策略：在 Embedding 时优先保留 `标题 + 摘要`，防止因正文过长导致的语义截断。 |
| 🎨 **原生 Markdown 支持** | `notion_ops` 内置了解析器，可将标准 Markdown 直接转换为 Notion Blocks (H1-H3, 列表, 代码块)。 |
| ✍️ **确定性发布** | `EditorAgent` 处理复杂的写入逻辑——根据向量检索的结果，决定是“覆盖重写”还是“新建页面”。 |

---

## 🏗️ 系统架构

工作流已进化为包含“读取-融合”闭环的结构：

graph TD
    Start([输入: PDF / 文本]) --> Perceiver

    subgraph Researcher Agent (研究员)
        Perceiver --> Classifier
        Classifier --> Memory{向量检索}
        
        Memory -- 发现匹配 --> Read[读取 Notion 旧文]
        Read --> Merge[LLM 深度融合: 旧文+新知]
        
        Memory -- 无匹配 --> Draft[起草新文]
        
        Merge & Draft --> Validator{JSON 合法?}
        Validator -- 否 --> Retry[注入错误上下文]
        Retry --> Merge & Draft
    end

    Validator -- 是 --> HumanReview

    HumanReview --> Publisher
    
    subgraph Editor Agent (编辑)
        Publisher --> Decide{决策模式?}
        Decide -- 融合 --> Overwrite[Notion: 清空并重写]
        Decide -- 新建 --> NewPage[Notion: 新建页面]
    end
    
    Overwrite & NewPage --> End([Notion & ChromaDB])

```

---

## 🧭 设计原则

* **显式优于隐式**：所有决策（领域、数据库、重试、融合）都存在于图结构中，而不是隐藏在 Prompt 里。
* **进化优于堆砌**：系统倾向于更新和完善现有的知识（Merge），而不是无限地追加碎片化的新笔记。
* **稳定性优先**：移除了脆弱的外部依赖，优化了向量操作以解决长文本截断问题。
* **拥抱失败**：校验和重试是一等公民，被深深嵌入在 Agent 的逻辑循环中。

---

## 📂 项目结构

```text
notion-ai-agent/
├── app.py            # Streamlit UI + 人工审查界面
├── graph_agent.py    # ⚙️ LangGraph 控制平面 (定义状态、节点、边)
├── agents.py         # 🤖 核心逻辑: Researcher (起草/融合/重试) & Editor (发布决策)
├── notion_ops.py     # 🛠️ 执行层: Markdown 解析器, 覆盖重写, 新建页面
├── vector_ops.py     # 🧠 记忆层: ChromaDB 封装 (含 Embeddings 优化)
├── file_ops.py       # 📂 输入层: PDF 处理
├── llm_client.py     # 🔌 接口层: 模型抽象
└── README.md

```

---

## 🧪 状态

本项目已达到 **个人知识管理生产可用 (Production-Ready)** 状态。
近期的更新主要解决了：

* **融合策略**：成功实现了 "查重 -> 读取 -> 融合 -> 重写" 的闭环。
* **错误恢复**：健壮的 LLM 格式错误自动处理。
* **内容保真度**：高质量的 Markdown 到 Notion 转换。