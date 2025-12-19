import os
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

load_dotenv()

# --- 配置 ---
# 我们使用 OpenAI 的 text-embedding-3-small (便宜且强大)
# 如果你只用 DeepSeek，DeepSeek 并没有官方兼容 OpenAI 格式的 Embedding API (截至目前)
# 所以这里建议单独配一个 OpenAI Key，或者使用本地模型 (SentenceTransformer)
# 为了演示最简便的方法，我们假设你有一个能调用的 Embedding 服务
# 如果没有 OpenAI Key，可以使用 chromadb 自带的 default_embedding_function (下载本地模型，免费)

# 这里我们使用 Chroma 默认的 SentenceTransformer (完全免费，本地运行，不用 API Key)
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

def add_memory(page_id, text_content, title, category):
    """
    存入记忆：将笔记内容向量化并存入 Chroma
    """
    print(f"💾 Vectorizing memory: {title}...")
    try:
        collection.add(
            documents=[text_content],       # 原始内容 (用于计算向量)
            metadatas=[{"title": title, "category": category}], # 元数据
            ids=[page_id]                   # 使用 Notion Page ID 作为唯一标识
        )
        print("✅ Memory stored in Vector DB.")
        return True
    except Exception as e:
        print(f"❌ Failed to store vector: {e}")
        return False

def search_memory(query_text, n_results=1):
    """
    检索记忆：寻找最相似的笔记
    """
    print(f"🔍 Vector Searching for: {query_text[:20]}...")
    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        
        # Chroma 返回的结构比较复杂，我们需要解包
        if results['ids'] and results['ids'][0]:
            # 获取相似度距离 (Distance)
            # Distance 越小越相似。一般 < 0.3 或 0.4 算非常相似
            distance = results['distances'][0][0]
            page_id = results['ids'][0][0]
            metadata = results['metadatas'][0][0]
            
            print(f"   Found candidate: {metadata['title']} (Distance: {distance:.4f})")
            
            # 设定一个阈值，如果距离太远(比如 > 0.5)，认为是不相关的
            if distance < 0.5: 
                return {
                    "match": True,
                    "page_id": page_id,
                    "title": metadata['title'],
                    "distance": distance
                }
            else:
                print("   No close match found (Distance too high).")
                return {"match": False}
        
        return {"match": False}
    except Exception as e:
        print(f"❌ Vector Search Error: {e}")
        return {"match": False}

# --- 初始化脚本 (可选) ---
# 如果你想把 Notion 里现有的笔记同步过来，需要写一个一次性脚本
# 这里暂略，先保证新笔记能存进去