# 💠 AI Knowledge Agent (LangGraph Edition)

> **拒绝堆砌，让知识有机生长。**
> 一个面向生产环境的 AI Agent，由 LangGraph 驱动，将原始信息转化为**结构化、可审查且持续进化的 Notion 知识库**。

## 🧠 核心理念 (Core Ideas)

### 1. 知识是工作流，而不仅仅是 Prompt

大多数 AI 笔记工具依赖于"单次提示词 → 单次输出"。
本系统将知识创造建模为一个 **状态图 (StateGraph)**：

* **感知 (Perceiver)**: 预处理输入，统一数据格式
* **意图分析 (Analyzer)**: 识别用户意图（保存笔记 vs 查询知识）和知识领域
* **记忆召回 (Recall Context)**: 从向量数据库检索相关笔记
* **智能路由 (Router)**: 根据意图和检索结果决定下一步
* **内容生成/融合 (Draft)**: 新建草稿或与现有笔记深度融合
* **人工审查 (Human Review)**: 在发布前暂停，允许人工审核和编辑
* **发布与存储 (Publish & Save)**: 写入 Notion 并更新向量数据库

每一步都是显式的、可检查的、可调试的。

---

### 2. LangGraph 作为控制平面

LangGraph 在这里不只是用来"连线"，而是作为**控制平面 (Control Plane)**：

* 定义显式的状态转换
* 条件分支（查询、新建、融合）
* JSON 校验失败时的**递归重试循环**
* 可中断执行 (Human-in-the-loop)
* 状态持久化和恢复

LLM 负责生成内容 —— **图 (Graph) 负责决定下一步发生什么**。

---

### 3. "人机协同"是治理机制，而非补丁

在任何内容被写入 Notion 之前，执行流会被暂停（`interrupt_before=["publisher"]`）。

人工审查者可以：

* 编辑内容（标题、摘要）
* 预览 Markdown 内容
* 批准或拒绝发布
* 覆盖语义分类（选择目标数据库）
* 确认融合策略

这将 Agent 从一个"不可控的风险"转变为一个**受治理的系统**。

---

## ✨ 关键特性

| 特性 | 说明 |
| --- | --- |
| ⚗️ **智能融合 (Semantic Merge)** | 如果发现相关笔记，系统会读取旧内容，与新输入深度融合，生成一篇更完善的文章，而不是简单创建副本。 |
| 🔍 **统一记忆召回** | 无论是保存笔记还是查询知识，都先检索向量数据库，确保知识的一致性。 |
| 🔄 **递归自修复** | `ResearcherAgent.draft_content()` 内置 3 次重试循环。如果生成的 JSON 格式错误，错误上下文会被回传给 LLM 进行自我修正。 |
| ✋ **人机协同 (HITL)** | 使用 LangGraph 的 `interrupt_before` 在发布前暂停，确保人类拥有最终决定权。 |
| 🧠 **富向量记忆** | 优化后的 ChromaDB 策略：在 Embedding 时优先保留`标题 + 摘要`，防止因正文过长导致的语义截断。Metadata 中存储完整内容供 RAG 使用。 |
| 🎨 **原生 Markdown 支持** | `notion_ops` 内置了解析器，可将标准 Markdown 直接转换为 Notion Blocks（H1-H3、列表、代码块、表格等）。 |
| 🗂️ **多领域支持** | 支持三个知识领域：西班牙语学习、技术知识、人文社科。每个领域对应独立的 Notion 数据库。 |
| 📊 **双模式操作** | 支持查询模式和保存模式。查询模式直接返回相关笔记，保存模式根据是否找到相关笔记决定新建或融合。 |

---

## 🏗️ 系统架构

### 工作流程图

```
perceiver → analyzer → recall_context → [路由决策]
                                         ├─ query_knowledge → query_memory → END
                                         ├─ save_note + 找到相关笔记 → draft_merge → publisher → memory_saver → END
                                         └─ save_note + 无相关笔记 → draft_new → publisher → memory_saver → END
```

### 节点说明

| 节点 | 功能 |
| --- | --- |
| **perceiver** | 预处理输入，提取 raw_text 和 original_url |
| **analyzer** | 分析用户意图（query_knowledge/save_note）和知识领域（Spanish/Tech/Humanities） |
| **recall_context** | 从向量数据库检索相关笔记（全库搜索） |
| **query_memory** | 格式化查询结果并返回给用户 |
| **draft_new** | 创建新的笔记草稿 |
| **draft_merge** | 读取现有笔记，与新输入融合生成新草稿 |
| **publisher** | 将草稿发布到 Notion（在发布前会中断，等待人工审查） |
| **memory_saver** | 将已发布的页面保存到向量数据库 |

### 状态定义

系统使用 TypedDict 定义状态结构：

* **AgentState**: 主状态，包含输入、分析、草稿、记忆、输出等信息
* **AnalysisState**: 意图分析结果（intent_type, category, domain, routing, confidence）
* **DraftState**: 草稿内容（title, summary, content, tags, is_merge, merge_target_id）
* **MemoryState**: 记忆检索结果（query_results, write_payload）

---

## 🧭 设计原则

* **显式优于隐式**：所有决策（领域、数据库、重试、融合）都存在于图结构中，而不是隐藏在 Prompt 里。
* **进化优于堆砌**：系统倾向于更新和完善现有的知识（Merge），而不是无限地追加碎片化的新笔记。
* **稳定性优先**：移除了脆弱的外部依赖，优化了向量操作以解决长文本截断问题。
* **拥抱失败**：校验和重试是一等公民，被深深嵌入在 Agent 的逻辑循环中。
* **类型安全**：所有核心函数都添加了类型提示，提高了代码的可维护性。

---

## 📂 项目结构

```text
notion-ai-agent/
├── app.py            # Streamlit UI + 人工审查界面
├── workflow.py       # ⚙️ LangGraph 控制平面 (定义状态、节点、边、路由)
├── agents.py         # 🤖 核心逻辑: ResearcherAgent (意图分析/记忆检索/草稿生成/内容融合) & EditorAgent (发布决策)
├── notion_ops.py     # 🛠️ 执行层: Markdown 解析器, 覆盖重写, 新建页面, 页面读取
├── vector_ops.py     # 🧠 记忆层: ChromaDB 封装 (含 Embeddings 优化策略)
├── llm_client.py     # 🔌 接口层: LLM 模型抽象 (支持 get_completion 和 get_reasoning_completion)
├── file_ops.py       # 📂 输入层: PDF 处理 (可选)
├── requirements.txt  # 依赖列表
└── README.md
```

### 核心模块职责

**workflow.py**
* 定义状态结构（AgentState, AnalysisState, DraftState, MemoryState）
* 定义工作流节点和边
* 实现路由逻辑（route_after_recall）
* 编译带检查点的图（用于 Streamlit）和无状态图（用于 CLI）

**agents.py**
* `ResearcherAgent`: 负责意图分析、记忆检索、草稿生成、内容融合
* `EditorAgent`: 负责发布决策和 Notion 写入
* 内置错误处理和重试机制

**notion_ops.py**
* Markdown 到 Notion Blocks 的转换器
* 页面创建、更新、读取功能
* 支持恢复模式（覆盖重写）和追加模式

**vector_ops.py**
* 向量数据库的封装（ChromaDB）
* 优化的 Embedding 策略（高密度文本构建）
* 记忆检索（支持分类过滤）

---

## 🚀 快速开始

### 环境配置

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 配置环境变量（`.env` 文件）：
```env
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=your_base_url  # 如果使用自定义 API
NOTION_TOKEN=your_notion_token
NOTION_DATABASE_ID=your_spanish_db_id
NOTION_DATABASE_ID_HUMANITIES=your_humanities_db_id
NOTION_DATABASE_ID_TECH=your_tech_db_id
```

3. 运行 Streamlit 应用：
```bash
streamlit run app.py
```

4. 或使用 CLI 测试：
```bash
python workflow.py
```

### 使用流程

1. **输入内容**：在 Streamlit 界面输入文本或上传 PDF
2. **自动分析**：系统自动识别意图和知识领域
3. **记忆检索**：从向量数据库查找相关笔记
4. **智能决策**：
   - 如果是查询：返回相关笔记链接和摘要
   - 如果是保存且找到相关笔记：融合内容生成新草稿
   - 如果是保存且无相关笔记：生成新草稿
5. **人工审查**：在发布前检查并编辑草稿
6. **发布存储**：写入 Notion 并更新向量数据库

---

## 🧪 状态

本项目已达到 **个人知识管理生产可用 (Production-Ready)** 状态。

### 最新更新

* ✅ **统一记忆召回**：所有操作（查询和保存）都先检索向量数据库
* ✅ **智能路由**：根据意图和检索结果自动选择处理路径
* ✅ **接口对齐**：修复了所有模块间的接口不一致问题
* ✅ **类型安全**：为核心函数添加了完整的类型提示
* ✅ **代码清理**：移除了冗余代码和未使用的导入
* ✅ **文档完善**：所有核心函数都有详细的文档字符串
* ✅ **融合策略**：成功实现了 "查重 -> 读取 -> 融合 -> 重写" 的闭环
* ✅ **错误恢复**：健壮的 LLM 格式错误自动处理（3次重试）
* ✅ **内容保真度**：高质量的 Markdown 到 Notion 转换

---

## 📝 技术细节

### 向量数据库优化

系统使用优化的 Embedding 策略：

1. **高密度文本构建**：在计算向量时，优先使用标题（重复两次以增加权重）、摘要和正文前400字符
2. **完整内容存储**：在 Metadata 中存储完整内容（前3000字符）供 RAG 查询使用
3. **摘要元数据**：将摘要存入 Metadata，查询时可直接展示

### 错误处理

* `draft_content` 方法内置 3 次重试机制
* 每次重试会将上一次的错误信息注入 Prompt
* 如果所有重试都失败，返回包含原始内容的兜底草稿

### 领域分类

系统支持三个知识领域：

* **Spanish** (`spanish_learning`): 西班牙语学习
* **Tech** (`tech_knowledge`): 技术知识（编程、AI、工程）
* **Humanities** (`humanities`): 人文社科（历史、经济、哲学、通用）

每个领域对应独立的 Notion 数据库，系统会根据分类自动选择目标数据库。

---

## 🔧 开发说明

### 添加新节点

1. 在 `workflow.py` 中定义节点函数
2. 使用 `workflow.add_node()` 注册节点
3. 使用 `workflow.add_edge()` 或 `workflow.add_conditional_edges()` 连接节点

### 修改路由逻辑

编辑 `route_after_recall` 函数，修改条件分支逻辑。

### 扩展知识领域

1. 在 `KnowledgeDomain` 枚举中添加新领域
2. 更新 `INTENT_TO_DOMAIN` 映射
3. 在 `notion_ops.py` 中添加对应的数据库 ID
4. 在 `node_publisher` 中更新 `db_map`

---

## 📄 许可证

本项目仅供个人学习和研究使用。

---

**Happy Knowledge Building! 🚀**
