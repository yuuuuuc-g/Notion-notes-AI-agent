import os
import requests # ✅ 引入 requests 库，直接由底层发请求
from notion_client import Client

# === 配置 ===
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
# 同时支持两个数据库 ID
DB_SPANISH_ID = os.environ.get("NOTION_DATABASE_ID")          
DB_GENERAL_ID = os.environ.get("NOTION_DATABASE_ID_GENERAL")  

# 初始化客户端 (用于创建页面，这部分目前看来是正常的)
notion = Client(auth=NOTION_TOKEN)

# --- 核心工具：排版引擎 (保持不变) ---
def clean_text(text):
    if text is None: return ""
    return str(text)[:2000]

def build_content_blocks(summary, blocks):
    """
    负责构建复杂的 Notion 区块结构 (Heading, Table, List, Callout)
    """
    children = []
    
    # 1. 摘要 (Callout)
    if summary:
        children.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"text": {"content": clean_text(summary)}}],
                "icon": {"emoji": "💡"},
                "color": "gray_background"
            }
        })

    # 2. 遍历 blocks 构建正文
    if not blocks:
        return children

    for block in blocks:
        # A. 容错处理：如果是字符串 (通用模式 key_points 的情况)
        if isinstance(block, str):
            children.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"text": {"content": clean_text(block)}}]}
            })
            continue

        # B. 正常处理字典结构的 block (西语模式)
        b_type = block.get('type')
        content = block.get('content')
        
        if b_type == 'heading':
            children.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": clean_text(content)}}]}
            })
        
        elif b_type == 'text' or b_type == 'paragraph':
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": clean_text(content)}}]}
            })
            
        elif b_type == 'list':
            if isinstance(content, list):
                for item in content:
                    children.append({
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {"rich_text": [{"text": {"content": clean_text(item)}}]}
                    })
        
        elif b_type == 'table':
            table_rows = []
            if 'headers' in content:
                header_cells = [[{"text": {"content": str(h)}}] for h in content['headers']]
                table_rows.append({"type": "table_row", "table_row": {"cells": header_cells}})
            if 'rows' in content:
                for row in content['rows']:
                    row_cells = [[{"text": {"content": str(c)}}] for c in row]
                    table_rows.append({"type": "table_row", "table_row": {"cells": row_cells}})
            
            if table_rows:
                children.append({
                    "object": "block",
                    "type": "table",
                    "table": {
                        "table_width": len(content.get('headers', ['A', 'B'])),
                        "has_column_header": True,
                        "children": table_rows
                    }
                })

    return children

# --- ✨ 核心修复：查重函数 (改用 requests 原生请求) ---
def get_all_page_titles(db_id=DB_SPANISH_ID):
    """
    获取现有笔记标题用于查重
    ⚠️ 修复：不使用 SDK，改用 requests 直接调用 API，避免 Attribute Error
    """
    if not db_id:
        return []

    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28", # 使用稳定的 API 版本
        "Content-Type": "application/json"
    }
    
    try:
        # 只请求标题，减少数据量
        payload = {
            "page_size": 100,
            # filter_properties 在 query 接口中可能不被所有版本支持，这里为了稳健先去掉
            # 我们直接拉取前100条（通常够用了）
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code != 200:
            print(f"⚠️ Notion API Error: {response.status_code} - {response.text}")
            return []

        data = response.json()
        results = []
        
        for page in data.get("results", []):
            try:
                props = page.get("properties", {})
                # 寻找类型为 title 的属性 (兼容不同列名)
                title_prop = next((v for k, v in props.items() if v["type"] == "title"), None)
                
                if title_prop and title_prop.get("title"):
                    # 提取纯文本标题
                    title_text = "".join([t["plain_text"] for t in title_prop["title"]])
                    if title_text:
                        results.append({"id": page["id"], "title": title_text})
            except:
                continue
                
        return results
    except Exception as e:
        print(f"❌ Error fetching titles (Requests): {e}")
        return []

def get_page_structure(page_id):
    """获取页面现有的结构"""
    try:
        blocks = notion.blocks.children.list(block_id=page_id).get("results", [])
        structure_desc = []
        tables = []
        for b in blocks:
            if b["type"] == "heading_2":
                text = b["heading_2"]["rich_text"][0]["plain_text"]
                structure_desc.append(f"[Heading] {text}")
            elif b["type"] == "table":
                tables.append({"id": b["id"], "desc": "Existing Table"})
                structure_desc.append(f"[Table] ID:{b['id']}")
        return "\n".join(structure_desc), tables
    except:
        return "", []

# --- 核心操作：创建与更新 ---

def create_study_note(title, category, summary, blocks, original_url=None):
    print(f"✍️ Creating Study Note: {title}...")
    children = build_content_blocks(summary, blocks)
    
    if original_url:
        children.append({
             "object": "block", "type": "paragraph",
             "paragraph": {"rich_text": [{"text": {"content": f"🔗 Source: {original_url}", "link": {"url": original_url}}}]}
        })

    try:
        notion.pages.create(
            parent={"database_id": DB_SPANISH_ID},
            properties={
                "Name": {"title": [{"text": {"content": clean_text(title)}}]},
                "Tags": {"multi_select": [{"name": "Spanish"}]},
                "Category": {"select": {"name": category}},
                "URL": {"url": original_url if original_url else None}
            },
            children=children
        )
        print("✅ Study Note Created!")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def create_general_note(data, original_url=None):
    title = data.get('title', 'Unnamed')
    print(f"✍️ Creating General Note: {title}...")
    
    blocks = data.get('key_points', []) 
    children = build_content_blocks(data.get('summary'), blocks)

    # 插入小标题
    if len(children) > 1:
        children.insert(1, {
            "object": "block", "type": "heading_3",
            "heading_3": {"rich_text": [{"text": {"content": "📝 Key Takeaways"}}], "color": "blue"}
        })

    if original_url:
        children.append({
             "object": "block", "type": "paragraph",
             "paragraph": {"rich_text": [{"text": {"content": f"🔗 Source: {original_url}", "link": {"url": original_url}}}]}
        })

    try:
        if not DB_GENERAL_ID:
            print("❌ Error: DB_GENERAL_ID is missing.")
            return False

        notion.pages.create(
            parent={"database_id": DB_GENERAL_ID},
            properties={
                "Name": {"title": [{"text": {"content": clean_text(title)}}]},
                "Tags": {"multi_select": [{"name": tag} for tag in data.get('tags', [])]},
                "Type": {"select": {"name": "General Knowledge"}},
                "URL": {"url": original_url if original_url else None}
            },
            children=children
        )
        print("✅ General Note Created!")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def append_to_page(page_id, summary, blocks):
    print(f"➕ Appending content to page {page_id}...")
    children = []
    children.append({"object": "block", "type": "divider", "divider": {}})
    children.extend(build_content_blocks(f"New Update: {summary}", blocks))
    
    try:
        notion.blocks.children.append(block_id=page_id, children=children)
        print("✅ Appended successfully!")
    except Exception as e:
        print(f"❌ Append failed: {e}")

def add_row_to_table(table_id, row_data):
    print(f"➕ Inserting row into table {table_id}...")
    try:
        row_cells = [[{"text": {"content": str(cell)}}] for cell in row_data]
        notion.blocks.children.append(
            block_id=table_id,
            children=[{"type": "table_row", "table_row": {"cells": row_cells}}]
        )
        print("✅ Row inserted!")
    except Exception as e:
        print(f"❌ Table insert failed: {e}")