import os
import requests
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

# === 配置 ===
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DB_SPANISH_ID = os.environ.get("NOTION_DATABASE_ID")          
DB_GENERAL_ID = os.environ.get("NOTION_DATABASE_ID_GENERAL")  

notion = Client(auth=NOTION_TOKEN)

# --- 核心工具：排版引擎 ---
def clean_text(text):
    if text is None: return ""
    return str(text)[:2000]

def build_content_blocks(summary, blocks):
    """构建 Notion 区块结构"""
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
            if 'headers' in content:
                header_cells = [[{"text": {"content": str(h)}}] for h in content['headers']]
                table_rows.append({"type": "table_row", "table_row": {"cells": header_cells}})
            if 'rows' in content:
                for row in content['rows']:
                    row_cells = [[{"text": {"content": str(c)}}] for c in row]
                    table_rows.append({"type": "table_row", "table_row": {"cells": row_cells}})
            
            if table_rows:
                children.append({
                    "object": "block", "type": "table",
                    "table": {
                        "table_width": len(content.get('headers', ['A'])),
                        "has_column_header": True, "children": table_rows
                    }
                })

    return children

# --- 功能函数 ---
def get_all_page_titles(db_id=DB_SPANISH_ID):
    """使用原生 requests 查重，避免 SDK 报错"""
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
                # 尝试匹配常见的标题列名
                title_prop = props.get("Name") or props.get("Spanish") or props.get("Title")
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
                if b['heading_2']['rich_text']:
                    structure_desc.append(f"[Heading] {b['heading_2']['rich_text'][0]['plain_text']}")
            elif b["type"] == "table":
                tables.append({"id": b["id"], "desc": "Existing Table"})
                structure_desc.append(f"[Table] ID:{b['id']}")
        return "\n".join(structure_desc), tables
    except: return "", []

# --- 核心操作 (关键修复：返回 Page ID) ---

def create_study_note(title, category, summary, blocks, original_url=None):
    print(f"✍️ Creating Study Note: {title}...")
    children = build_content_blocks(summary, blocks)
    
    if original_url:
        children.append({
             "object": "block", "type": "paragraph",
             "paragraph": {"rich_text": [{"text": {"content": f"🔗 Source: {original_url}", "link": {"url": original_url}}}]}
        })

    try:
        # ⚠️ 这里的 properties 必须和你 Notion 的列名一致 (Name, Tags, URL)
        response = notion.pages.create(
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
        return response["id"] # 🔥 修复：返回 ID
    except Exception as e:
        print(f"❌ Failed: {e}")
        return None

def create_general_note(data, original_url=None):
    title = data.get('title', 'Unnamed')
    print(f"✍️ Creating General Note: {title}...")
    
    blocks = data.get('key_points', []) 
    children = build_content_blocks(data.get('summary'), blocks)
    if len(children) > 1:
        children.insert(1, {"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"text": {"content": "📝 Key Takeaways"}}], "color": "blue"}})

    if original_url:
        children.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": f"🔗 Source: {original_url}", "link": {"url": original_url}}}]}})

    try:
        response = notion.pages.create(
            parent={"database_id": DB_GENERAL_ID},
            properties={
                "Name": {"title": [{"text": {"content": clean_text(title)}}]},
                "Tags": {"multi_select": [{"name": tag} for tag in data.get('tags', [])]},
                "Type": {"select": {"name": "Article"}},
                "URL": {"url": original_url if original_url else None}
            },
            children=children
        )
        print("✅ General Note Created!")
        return response["id"] # 🔥 修复：返回 ID
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
        row_cells = [[{"text": {"content": str(cell)}}] for cell in row_data]
        notion.blocks.children.append(block_id=table_id, children=[{"object": "block", "type": "table_row", "table_row": {"cells": row_cells}}])
        print("✅ Row inserted!")
        return True
    except Exception as e:
        print(f"❌ Table insert failed: {e}")
        return False

def append_podcast_script(page_id, script):
    """保存播客剧本"""
    print(f"🎙️ Saving podcast script to page {page_id}...")
    script_children = []
    for line in script:
        speaker = line.get('speaker', 'Unknown')
        text = line.get('text', '')
        icon = "👩🏻‍🦰" if speaker == "Host" else "👨🏻‍🏫"
        script_children.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"text": {"content": f"{icon} {speaker}: ", "annotations": {"bold": True}}}, {"text": {"content": text}}]}
        })

    wrapper_block = [
        {"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"text": {"content": "🎧 AI Podcast Transcript"}}]}},
        {"object": "block", "type": "toggle", "toggle": {"rich_text": [{"text": {"content": "Click to read dialogue"}}], "children": script_children}}
    ]

    try:
        notion.blocks.children.append(block_id=page_id, children=wrapper_block)
        print("✅ Script saved!")
        return True
    except Exception as e:
        print(f"❌ Script save failed: {e}")
        return False