import os
import httpx # 👈 直接用底层 HTTP 库
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

# 这些用于 notion-client (用于创建页面，因为那个功能你测过是好的)
notion = Client(auth=os.getenv("NOTION_TOKEN"))
database_id = os.getenv("NOTION_DATABASE_ID")

# 这些用于 httpx (用于我们手动发请求绕过 bug)
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def clean_text(text):
    if not isinstance(text, str): return str(text)
    text = text.replace("**", "").replace("`", "")
    if text.strip().startswith("- "): text = text.strip()[2:]
    return text.strip()

# --- 🌟 核弹级修改：直接发送 HTTP 请求 ---
def get_all_page_titles():
    """
    [原生 HTTP 版] 踢开 notion-client 库，直接访问 Notion 服务器
    """
    print("🔍 正在通过原生 HTTP 同步数据...")
    all_pages = []
    has_more = True
    next_cursor = None
    
    # 构造标准 API 地址
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    
    try:
        while has_more:
            payload = {"page_size": 100}
            if next_cursor:
                payload["start_cursor"] = next_cursor

            # 🔥 这里的代码不依赖 notion-client 库
            response = httpx.post(url, headers=HEADERS, json=payload, timeout=30.0)
            
            # 检查 HTTP 状态码
            if response.status_code != 200:
                print(f"❌ Notion 拒绝了请求: {response.status_code}")
                print(f"❌ 原因: {response.text}")
                return []
                
            data = response.json()
            
            for page in data.get('results', []):
                try:
                    props = page['properties']
                    # 确保标题列名对应 (Spanish)
                    if 'Spanish' in props and props['Spanish']['title']:
                        title_text = props['Spanish']['title'][0]['text']['content']
                        all_pages.append({"id": page['id'], "title": title_text})
                except Exception:
                    continue
            
            has_more = data.get('has_more', False)
            next_cursor = data.get('next_cursor')

        return all_pages

    except Exception as e:
        print(f"❌ 原生请求失败: {e}")
        return []

# --- 下面的函数保持不变 (继续用 Client 创建页面，因为那个没坏) ---

def get_page_structure(page_id):
    try:
        response = notion.blocks.children.list(block_id=page_id)
        blocks = response['results']
        structure_info = []
        tables = []
        for block in blocks:
            b_type = block['type']
            b_id = block['id']
            if b_type == 'table':
                table_width = block['table']['table_width']
                info = f"[Table Block] ID: {b_id}, Width: {table_width} columns"
                structure_info.append(info)
                tables.append({"id": b_id, "width": table_width, "type": "table"})
            elif 'heading' in b_type:
                text = block[b_type]['rich_text'][0]['text']['content'] if block[b_type]['rich_text'] else ""
                structure_info.append(f"[Heading] {text}")
        return "\n".join(structure_info), tables
    except Exception as e:
        print(f"❌ 读取页面失败: {e}")
        return "", []

def add_row_to_table(table_block_id, row_data):
    cells = [[{"type": "text", "text": {"content": clean_text(str(cell))}}] for cell in row_data]
    try:
        notion.blocks.children.append(block_id=table_block_id, children=[{"object": "block", "type": "table_row", "table_row": {"cells": cells}}])
        return True
    except Exception as e:
        print(f"❌ 插入表格失败: {e}")
        return False

def create_table_block(table_data):
    headers = table_data.get('headers', [])
    rows = table_data.get('rows', [])
    table_rows = []
    header_cells = [[{"type": "text", "text": {"content": clean_text(str(h))}}] for h in headers]
    table_rows.append({"type": "table_row", "table_row": {"cells": header_cells}})
    for row in rows:
        padded_row = row + [""] * (len(headers) - len(row))
        cells = [[{"type": "text", "text": {"content": clean_text(str(cell))}}] for cell in padded_row[:len(headers)]]
        table_rows.append({"type": "table_row", "table_row": {"cells": cells}})
    return {"object": "block", "type": "table", "table": {"table_width": len(headers), "has_column_header": True, "has_row_header": False, "children": table_rows}}

def build_content_blocks(summary, blocks):
    children_blocks = []
    if summary:
        children_blocks.extend([
            {"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"text": {"content": "New Update"}}]}},
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": clean_text(summary)}}]}}
        ])
    for block in blocks:
        b_type = block.get('type')
        b_content = block.get('content')
        if b_type == 'heading':
            text = str(b_content) if not isinstance(b_content, list) else " ".join(b_content)
            children_blocks.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"text": {"content": clean_text(text)}}]}})
        elif b_type == 'text':
            text = "\n".join([str(s) for s in b_content]) if isinstance(b_content, list) else str(b_content)
            for line in text.split('\n'):
                if line.strip(): children_blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": clean_text(line)}}]}})
        elif b_type == 'list':
            lst = b_content if isinstance(b_content, list) else [str(b_content)]
            for item in lst: children_blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"text": {"content": clean_text(str(item))}}]}})
        elif b_type == 'table':
            try: children_blocks.append(create_table_block(b_content))
            except: pass
    return children_blocks

def append_to_page(page_id, summary, blocks):
    new_children = build_content_blocks(summary, blocks)
    try:
        notion.blocks.children.append(block_id=page_id, children=new_children)
        return True
    except Exception as e:
        print(f"❌ 追加失败: {e}")
        return False

def create_study_note(title, category, summary, blocks):
    children_blocks = [{"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Summary"}}]}},
                       {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": clean_text(summary)}}]}},
                       {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "Details"}}]}}]
    children_blocks.extend(build_content_blocks(None, blocks))
    try:
        notion.pages.create(parent={"database_id": database_id}, properties={"Spanish": {"title": [{"text": {"content": clean_text(title)}}]}, "Category": {"select": {"name": category}}}, children=children_blocks)
        return True
    except Exception as e:
        print(f"❌ 创建失败: {e}")
        return False
    

# --- notion_ops.py 追加内容 ---

def create_general_note(title, tags, summary, url, content_blocks, db_id):
    """
    通道 B：向【通用知识库】写入数据
    """
    print(f"✍️ 正在写入通用知识库: {title}")
    
    # 构造标签列表
    tag_objs = [{"name": tag} for tag in tags] if tags else []
    
    # 构造页面内容块 (摘要 + 正文详情)
    children_blocks = [
        {"object": "block", "type": "callout", "callout": {
            "rich_text": [{"text": {"content": f"💡 AI 摘要: {summary}"}}],
            "icon": {"emoji": "🤖"}
        }},
        {"object": "block", "type": "divider", "divider": {}}
    ]
    # 追加正文结构块
    children_blocks.extend(build_content_blocks(None, content_blocks))

    try:
        notion.pages.create(
            parent={"database_id": db_id},
            properties={
                "Name": {
                    "title": [{"text": {"content": clean_text(title)}}]
                },
                "Tags": {
                    "multi_select": tag_objs
                },
                "URL": {
                    "url": url if url else None
                },
                "Summary": {
                    "rich_text": [{"text": {"content": clean_text(summary)[:2000]}}]
                },
                "Type": {
                    "select": {"name": "Article"}
                }
            },
            children=children_blocks
        )
        print(f"✅ 通用笔记创建成功: {title}")
        return True
    except Exception as e:
        print(f"❌ 通用笔记创建失败: {e}")
        return False