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
def clean_text(text):
    """
    清洗文本：去除 Markdown 符号
    """
    if text is None: return ""
    text = str(text)
    
    # 1. 去掉加粗 (**text** -> text)
    text = text.replace("**", "")
    
    # 2. 去掉代码符号 (`text` -> text)
    text = text.replace("`", "")
    
    # 3. 去掉行首多余的列表符
    if text.strip().startswith("- "):
        text = text.strip()[2:]
        
    return text[:2000]

def build_content_blocks(summary, blocks):
    children = []
    
    if summary:
        children.append({
            "object": "block", "type": "callout",
            "callout": {
                "rich_text": [{"text": {"content": clean_text(summary)}}],
                "icon": {"emoji": "💡"}, "color": "gray_background"
            }
        })

    if not blocks: return children

    for block in blocks:
        if isinstance(block, str):
            children.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"text": {"content": clean_text(block)}}]}
            })
            continue

        b_type = block.get('type')
        content = block.get('content')
        
        if b_type == 'heading':
            children.append({
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": clean_text(content)}}]}
            })
        
        elif b_type == 'text' or b_type == 'paragraph':
            children.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": clean_text(content)}}]}
            })
            
        elif b_type == 'list':
            if isinstance(content, list):
                for item in content:
                    children.append({
                        "object": "block", "type": "bulleted_list_item",
                        "bulleted_list_item": {"rich_text": [{"text": {"content": clean_text(item)}}]}
                    })
        
        elif b_type == 'table':
            table_rows = []
            # 表头
            if 'headers' in content:
                # ⚠️ 关键修复：这里加了 clean_text
                header_cells = [[{"text": {"content": clean_text(h)}}] for h in content['headers']]
                table_rows.append({"type": "table_row", "table_row": {"cells": header_cells}})
            
            # 数据行
            if 'rows' in content:
                for row in content['rows']:
                    # ⚠️ 关键修复：这里也加了 clean_text
                    row_cells = [[{"text": {"content": clean_text(c)}}] for c in row]
                    table_rows.append({"type": "table_row", "table_row": {"cells": row_cells}})
            
            if table_rows:
                children.append({
                    "object": "block", "type": "table",
                    "table": {
                        "table_width": len(content.get('headers', ['A', 'B'])),
                        "has_column_header": True, "children": table_rows
                    }
                })

    return children

# --- 功能函数 ---
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

# --- 核心操作 ---

def create_study_note(title, category, summary, blocks, original_url=None):
    print(f"✍️ Creating Spanish Note: {title}...")
    # 这里也要清洗标题
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

    # 兼容旧逻辑补标题
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
        # ⚠️ 关键修复：插入行时也要清洗
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