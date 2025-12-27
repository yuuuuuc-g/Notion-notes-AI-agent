import os
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from typing import Optional, Dict, Any 

load_dotenv()

# --- 配置 ---
# 这里使用 Chroma 默认的 SentenceTransformer
EMBEDDING_FUNC = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

# 初始化本地数据库
client = chromadb.PersistentClient(path="./chroma_db")

# 创建或获取集合
collection = client.get_or_create_collection(
    name="knowledge_base",
    embedding_function=EMBEDDING_FUNC
)

def add_memory(
    page_id,
    text_content=None,
    title=None,
    category=None,
    *,
    content=None,
    intent_type=None,
    metadata: Optional[Dict[str, Any]] = None, 
):
    """
    存入记忆（已修复 Metadata 空值崩溃问题 + 优化向量匹配精度）
    """
    
    # 1️⃣ 【第一步】参数归一化
    final_title = title or (metadata.get("title") if metadata else "Untitled")
    final_category = (
        intent_type
        or category
        or (metadata.get("category") if metadata else "General")
    )

    # content 优先
    final_content = content
    if final_content is None and text_content:
        final_content = text_content

    # 2️⃣ 【第二步】安全检查
    if not isinstance(final_content, str) or len(final_content.strip()) < 30:
        print("❌ VectorOps: content too short or invalid, skip memory.")
        return False

    # 3️⃣ 【第三步】准备原始 Metadata
    final_metadata = metadata or {}
    final_metadata.setdefault("title", final_title)
    final_metadata.setdefault("category", final_category)

    # 4️⃣ 【第四步】清洗 Metadata (去除 None)
    cleaned_metadata = {}
    for k, v in final_metadata.items():
        if v is None:
            cleaned_metadata[k] = "" 
        else:
            cleaned_metadata[k] = str(v)

    print(f"💾 Vectorizing memory: {final_title}...")

    # 5️⃣ 【第五步】构建增强版 Embedding 文本 (关键修改)
    # 获取摘要
    summary_text = metadata.get("summary", "") if metadata else ""
    
    # 拼接：Title + Summary + Content
    # 目的：确保核心关键词出现在文本最开头，防止被 Embedding 模型截断
    embedding_text = f"Title: {final_title}\nSummary: {summary_text}\nContent: {final_content}"

    # 6️⃣ 【第六步】写入数据库
    try:
        collection.add(
            documents=[embedding_text], # 👈 Chroma 会自动为此文本计算向量
            metadatas=[cleaned_metadata], 
            ids=[page_id],
        )
        print("✅ Memory stored in Vector DB (Optimized with Title prioritization).")
        return True
    except Exception as e:
        print(f"❌ Failed to store vector: {e}")
        return False

def search_memory(query_text, n_results=1, category_filter=None):
    """
    检索记忆：寻找最相似的笔记
    :param category_filter: (可选) 过滤特定分类
    """

    # ---------- Query Sanity Check ----------
    if not isinstance(query_text, str) or len(query_text.strip()) < 10:
        print("⚠️ VectorOps: query too short, skip search.")
        return {"match": False}

    print(f"🔍 Vector Searching for: {query_text[:20]}... (Filter: {category_filter})")
    
    # 构造查询参数
    query_args = {
        "query_texts": [query_text],
        "n_results": n_results
    }
    
    # 如果有分类限制，添加 where 条件
    if category_filter:
        query_args["where"] = {"category": category_filter}

    try:
        results = collection.query(**query_args)
        
        # Chroma 返回的结构比较复杂，我们需要解包
        if results['ids'] and results['ids'][0]:
            # 获取相似度距离 (Distance)
            distance = results['distances'][0][0]
            page_id = results['ids'][0][0]
            metadata = results['metadatas'][0][0]
            
            print(f"   Found candidate: {metadata.get('title')} (Dist: {distance:.4f})")
            
            # ⚠️ 严格阈值
            THRESHOLD = 0.3 if category_filter == "spanish_learning" else 0.5

            if distance < THRESHOLD:
                return {
                    "match": True,
                    "page_id": page_id,
                    "title": metadata.get("title"),
                    "distance": distance,
                    "category": metadata.get("category"),
                    "metadata": metadata,
                }
            else:
                print("   No close match found (Distance too high).")
                return {"match": False}
        
        return {"match": False}
    except Exception as e:
        print(f"❌ Vector Search Error: {e}")
        return {"match": False}