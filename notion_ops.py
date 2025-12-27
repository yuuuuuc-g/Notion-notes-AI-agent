import os
import requests
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

# === 配置 ===
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DB_SPANISH_ID = os.environ.get("NOTION_DATABASE_ID")          
DB_HUMANITIES_ID = os.environ.get("NOTION_DATABASE_ID_HUMANITIES")  
DB_TECH_ID = os.environ.get("NOTION_DATABASE_ID_TECH")

notion = Client(auth=NOTION_TOKEN)

# --- 核心工具：排版引擎 ---
def chunk_text(text, max_len=1900):
    """辅助函数：将长文本切分为符合 Notion 限制的片段"""
    if not text: return []
    return [text[i:i+max_len] for i in range(0, len(text), max_len)]

def clean_text(text):
    """
    清洗文本：去除 Markdown 符号
    """
    if text is None: return ""
    text = str(text)
    text = text.replace("**", "").replace("`", "")
    if text.strip().startswith("- "):
        text = text.strip()[2:]
    return text


def build_content_blocks(summary, blocks):
    print(f"🧐 [Debug] Input blocks count: {len(blocks) if blocks else 0}")
    # print(f"🧐 [Debug] Input blocks sample: {str(blocks)[:300]}...") 

    children = []

    # 1. 添加 Summary
    if summary:
        children.append({
            "object": "block", "type": "callout",
            "callout": {
                "rich_text": [{"text": {"content": clean_text(summary)}}],
                "icon": {"emoji": "💡"}, "color": "gray_background"
            }
        })

    # 2. 兜底：纯字符串
    if isinstance(blocks, str) and blocks.strip():
        print("🧐 [Debug] Blocks is a string, converting to paragraph.")
        chunks = chunk_text(clean_text(blocks))
        for chunk in chunks:
            children.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": chunk}}]}
            })
        return children

    # 3. 兜底：非列表
    if blocks and not isinstance(blocks, list):
        print("🧐 [Debug] Blocks is unknown type, forcing string conversion.")
        chunks = chunk_text(clean_text(str(blocks)))
        for chunk in chunks:
            children.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": chunk}}]}
            })
        return children

    # 4. 遍历 List
    for i, block in enumerate(blocks):
        # 情况 A: 列表里是纯字符串 ["段落1", "段落2"]
        if isinstance(block, str):
            children.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": clean_text(block)}}]}
            })
            continue

        # 情况 B: 字典结构
        b_type = block.get('type')
        content = block.get('content')
        
        # 🟢【Debug】看看当前 block 是什么类型
        print(f"   - Processing Block {i}: type='{b_type}'")

        # --- 匹配逻辑 ---

        # 1. 标题 (兼容 heading, heading_1, heading_2, heading_3)
        if b_type in ['heading', 'heading_1', 'heading_2', 'heading_3']:
            children.append({
                "object": "block", "type": "heading_2", # 统一转为二级标题
                "heading_2": {"rich_text": [{"text": {"content": clean_text(content)}}]}
            })
        
        # 2. 正文 (text, paragraph)
        elif b_type in ['text', 'paragraph']:
            chunks = chunk_text(clean_text(content))
            for chunk in chunks:
                children.append({
                    "object": "block", "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": chunk}}]}
                })

        # 3. 无序列表 (bulleted_list_item) - 新 Agent 逻辑
        elif b_type == 'bulleted_list_item':
             children.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"text": {"content": clean_text(content)}}]}
            })

        # 4. 有序列表 (numbered_list_item) - 预留
        elif b_type == 'numbered_list_item':
             children.append({
                "object": "block", "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": [{"text": {"content": clean_text(content)}}]}
            })

        # 5. 代码块 (code) - 预留
        elif b_type == 'code':
            children.append({
                "object": "block", "type": "code",
                "code": {
                    "rich_text": [{"text": {"content": str(content)}}],
                    "language": "plain text"
                }
            })
            
        # 6. 旧逻辑兼容：整个列表 (list)
        elif b_type == 'list':
            if isinstance(content, list):
                for item in content:
                    children.append({
                        "object": "block", "type": "bulleted_list_item",
                        "bulleted_list_item": {"rich_text": [{"text": {"content": clean_text(item)}}]}
                    })
        
        # 7. 表格 (table)
        elif b_type == 'table':
            # (简化的 table 处理，防止出错)
            pass 

        # 8. 兜底 (Else)
        else:
            print(f"⚠️ [Warn] Unknown block type: '{b_type}'. Fallback to text.")
            raw_content = content if content else str(block)
            chunks = chunk_text(clean_text(str(raw_content)))
            for chunk in chunks:
                children.append({
                    "object": "block", "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": f"[{b_type or 'Raw'}] {chunk}"}}]}
                })

    print(f"✅ [Debug] Final children count to Notion: {len(children)}")
    return children

# --- 功能函数 (保持不变) ---
def get_all_page_titles(db_id):
    if not db_id: return []
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json={"page_size": 100}, timeout=10)
        data = response.json()
        results = []
        for page in data.get("results", []):
            try:
                props = page.get("properties", {})
                title_prop = next((v for k, v in props.items() if v["type"] == "title"), None)
                if title_prop and title_prop.get("title"):
                    title_text = "".join([t["plain_text"] for t in title_prop["title"]])
                    if title_text: results.append({"id": page["id"], "title": title_text})
            except: continue
        return results
    except Exception as e:
        print(f"❌ Error fetching titles: {e}")
        return []

def get_page_structure(page_id):
    try:
        blocks = notion.blocks.children.list(block_id=page_id).get("results", [])
        structure_desc = []
        tables = []
        for b in blocks:
            if b["type"] == "heading_2":
                text = b["heading_2"]["rich_text"][0]["plain_text"] if b["heading_2"]["rich_text"] else ""
                structure_desc.append(f"[Heading] {text}")
            elif b["type"] == "table":
                tables.append({"id": b["id"], "desc": "Existing Table"})
                structure_desc.append(f"[Table] ID:{b['id']}")
        return "\n".join(structure_desc), tables
    except: return "", []

# --- 核心操作 (保持不变) ---
def create_study_note(title, category, summary, blocks, original_url=None):
    print(f"✍️ Creating Spanish Note: {title}...")
    clean_title = clean_text(title)
    children = build_content_blocks(summary, blocks)
    
    if original_url:
        children.append({
             "object": "block", "type": "paragraph",
             "paragraph": {"rich_text": [{"text": {"content": f"🔗 Source: {original_url}", "link": {"url": original_url}}}]}
        })

    try:
        response = notion.pages.create(
            parent={"database_id": DB_SPANISH_ID},
            properties={
                "Name": {"title": [{"text": {"content": clean_title}}]},
                "Tags": {"multi_select": [{"name": "Spanish"}]}, 
                "Category": {"select": {"name": category}},
                "URL": {"url": original_url if original_url else None}
            },
            children=children
        )
        print("✅ Study Note Created!")
        return response["id"]
    except Exception as e:
        print(f"❌ Failed: {e}")
        return None

def create_general_note(data, target_db_id, original_url=None):
    title = data.get('title', 'Unnamed')
    clean_title = clean_text(title)
    print(f"✍️ Creating General Note: {clean_title}...")
    
    blocks = data.get('blocks') or data.get('key_points', []) 
    children = build_content_blocks(data.get('summary'), blocks)

    if not data.get('blocks') and blocks:
        children.insert(1, {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "📝 Key Takeaways"}}], "color": "blue"}})

    if original_url:
        children.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": f"🔗 Source: {original_url}", "link": {"url": original_url}}}]}})

    try:
        if not target_db_id:
            print("❌ Error: Target DB ID is missing.")
            return None

        response = notion.pages.create(
            parent={"database_id": target_db_id},
            properties={
                "Name": {"title": [{"text": {"content": clean_title}}]},
                "Tags": {"multi_select": [{"name": tag} for tag in data.get('tags', [])]},
                "Type": {"select": {"name": "Article"}},
                "URL": {"url": original_url if original_url else None}
            },
            children=children
        )
        print("✅ General Note Created!")
        return response["id"]
    except Exception as e:
        print(f"❌ Failed: {e}")
        return None

def append_to_page(page_id, summary, blocks):
    print(f"➕ Appending content to page {page_id}...")
    children = []
    children.append({"object": "block", "type": "divider", "divider": {}})
    children.extend(build_content_blocks(f"New Update: {summary}", blocks))
    try:
        notion.blocks.children.append(block_id=page_id, children=children)
        print("✅ Appended successfully!")
        return True
    except Exception as e:
        print(f"❌ Append failed: {e}")
        return False

def add_row_to_table(table_id, row_data):
    print(f"➕ Inserting row into table {table_id}...")
    try:
        row_cells = [[{"text": {"content": clean_text(str(cell))}}] for cell in row_data]
        notion.blocks.children.append(
            block_id=table_id,
            children=[{"object": "block", "type": "table_row", "table_row": {"cells": row_cells}}]
        )
        print("✅ Row inserted!")
        return True
    except Exception as e:
        print(f"❌ Table insert failed: {e}")
        return False