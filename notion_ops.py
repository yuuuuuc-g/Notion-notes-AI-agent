import os
from notion_client import Client

# === 配置 ===
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
# 同时支持两个数据库 ID
DB_SPANISH_ID = os.environ.get("NOTION_DATABASE_ID")          
DB_GENERAL_ID = os.environ.get("NOTION_DATABASE_ID_GENERAL")  

notion = Client(auth=NOTION_TOKEN)

# --- 核心工具：排版引擎 (找回了这个关键函数) ---
def clean_text(text):
    if text is None: return ""
    return str(text)[:2000]

def build_content_blocks(summary, blocks):
    """
    负责构建复杂的 Notion 区块结构 (Heading, Table, List, Callout)
    兼容：既能处理字典列表(复杂结构)，也能处理字符串列表(简单Key Points)
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
        # A. 容错处理：如果是字符串 (通用模式 key_points 的情况)，直接转为 bullet
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
            # 处理列表内容
            if isinstance(content, list):
                for item in content:
                    children.append({
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {"rich_text": [{"text": {"content": clean_text(item)}}]}
                    })
        
        elif b_type == 'table':
            # === 表格构建逻辑 (最复杂的部分) ===
            table_rows = []
            # 表头
            if 'headers' in content:
                header_cells = [[{"text": {"content": str(h)}}] for h in content['headers']]
                table_rows.append({"type": "table_row", "table_row": {"cells": header_cells}})
            # 数据行
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

# --- 功能函数：查重与获取结构 (完全保留) ---
def get_all_page_titles(db_id=DB_SPANISH_ID):
    """获取现有笔记标题用于查重"""
    try:
        response = notion.databases.query(database_id=db_id, filter_properties=["title"])
        results = []
        for page in response.get("results", []):
            try:
                # 兼容不同的 Title 字段名 (Name, Spanish, Title)
                props = page.get("properties", {})
                # 寻找类型为 title 的属性
                title_prop = next((v for k, v in props.items() if v["type"] == "title"), None)
                if title_prop and title_prop.get("title"):
                    title_text = title_prop["title"][0]["plain_text"]
                    results.append({"id": page["id"], "title": title_text})
            except:
                continue
        return results
    except Exception as e:
        print(f"❌ Error fetching titles: {e}")
        return []

def get_page_structure(page_id):
    """获取页面现有的结构 (用于判断是否插入表格)"""
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
    """创建西语笔记 (完整版，支持 blocks)"""
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
                "Category": {"select": {"name": category}}, # 需要数据库有 Category 列 (Select)
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
    """创建通用笔记"""
    title = data.get('title', 'Unnamed')
    print(f"✍️ Creating General Note: {title}...")
    
    # 将简单的 key_points 列表传给 build_content_blocks 处理
    blocks = data.get('key_points', []) 
    
    children = build_content_blocks(data.get('summary'), blocks)

    # 插入一个小标题
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
    """追加内容到现有页面 (找回了这个功能)"""
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
    """向现有表格插入行 (找回了这个功能)"""
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