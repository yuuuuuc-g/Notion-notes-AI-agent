import os
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from typing import Optional, Dict, Any # ✅ 新增导入

load_dotenv()

# --- 配置 ---
# 这里使用 Chroma 默认的 SentenceTransformer (完全免费，本地运行，不用 API Key)
# 第一次运行会自动下载模型 (约 80MB)
EMBEDDING_FUNC = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

# 初始化本地数据库 (会在项目目录下生成一个 chromadb 文件夹)
client = chromadb.PersistentClient(path="./chroma_db")

# 创建或获取集合 (Collection)
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
    metadata: Optional[Dict[str, Any]] = None, # ✅ 修复：使用 Optional 兼容 Python 3.9
):
    """
    存入记忆（工业级 V2）

    兼容两种调用方式：

    1️⃣ 旧版（positional）:
        add_memory(page_id, text, title, category)

    2️⃣ 新版（keyword）:
        add_memory(
            page_id=...,
            content=...,
            title=...,
            intent_type=...,
            metadata={...}
        )
    """

    # ---------- 参数归一化 ----------
    final_content = content if content is not None else text_content
    final_title = title or (metadata.get("title") if metadata else "Untitled")
    final_category = (
        intent_type
        or category
        or (metadata.get("category") if metadata else "General")
    )

    if not final_content:
        print("❌ VectorOps: content is empty, skip memory.")
        return False

    final_metadata = metadata or {}
    final_metadata.setdefault("title", final_title)
    final_metadata.setdefault("category", final_category)

    print(f"💾 Vectorizing memory: {final_title}...")

    try:
        collection.add(
            documents=[final_content],
            metadatas=[final_metadata],
            ids=[page_id],
        )
        print("✅ Memory stored in Vector DB.")
        return True
    except Exception as e:
        print(f"❌ Failed to store vector: {e}")
        return False

def search_memory(query_text, n_results=1, category_filter=None):
    """
    检索记忆：寻找最相似的笔记
    :param category_filter: (可选) 过滤特定分类
    """
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
            # Distance 越小越相似。一般 < 0.3 或 0.4 算非常相似
            distance = results['distances'][0][0]
            page_id = results['ids'][0][0]
            metadata = results['metadatas'][0][0]
            
            print(f"   Found candidate: {metadata.get('title')} (Dist: {distance:.4f})")
            
            # 设定一个阈值，如果距离太远(比如 > 0.5)，认为是不相关的
            if distance < 0.5: 
                return {
                    "match": True,
                    "page_id": page_id,
                    "title": metadata.get("title"),
                    "distance": distance,
                    "metadata": metadata,
                }
            else:
                print("   No close match found (Distance too high).")
                return {"match": False}
        
        return {"match": False}
    except Exception as e:
        print(f"❌ Vector Search Error: {e}")
        return {"match": False}