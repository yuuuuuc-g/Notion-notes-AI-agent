import os
import json
import httpx
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

# 初始化 Notion Client
notion = Client(auth=os.getenv("NOTION_TOKEN"))
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# --- 核心工具函数 ---

def clean_text(text):
    """清洗文本，防止 Notion 报错"""
    if not text: return ""
    return text[:2000]  # Notion 文本块上限 2000 字符

def build_content_blocks(summary, blocks):
    """构建 Notion 页面内容的通用函数"""
    children = []
    
    # 1. 插入摘要 (如果有)
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
    for block in blocks:
        b_type = block.get('type')
        content = block.get('content')
        
        if b_type == 'heading':
            children.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": clean_text(content)}}]}
            })
        
        elif b_type == 'text':
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": clean_text(content)}}]}
            })
            
        elif b_type == 'list':
            for item in content:
                children.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": [{"text": {"content": clean_text(item)}}]}
                })
        
        elif b_type == 'table':
            # 构建表格 (Table)
            table_rows = []
            # 表头
            if 'headers' in content:
                header_cells = [{"text": {"content": h}} for h in content['headers']]
                table_rows.append({"type": "table_row", "table_row": {"cells": header_cells}})
            # 数据行
            if 'rows' in content:
                for row in content['rows']:
                    row_cells = [{"text": {"content": str(c)}} for c in row]
                    table_rows.append({"type": "table_row", "table_row": {"cells": row_cells}})
            
            children.append({
                "object": "block",
                "type": "table",
                "table": {
                    "table_width": len(content.get('headers', ['A'])),
                    "has_column_header": True,
                    "has_row_header": False,
                    "children": table_rows
                }
            })

    return children

# --- 功能函数 ---

def get_all_page_titles():
    """
    获取现有笔记标题 (使用 httpx 绕过 SDK bug)
    """
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {os.getenv('NOTION_TOKEN')}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    try:
        # 只查询标题列，减少数据量
        payload = {
            "filter_properties": ["title"] 
        }
        response = httpx.post(url, headers=headers, json=payload, timeout=10.0)
        data = response.json()
        
        results = []
        for page in data.get("results", []):
            try:
                # 兼容不同列名 (Name 或 Spanish)
                props = page.get("properties", {})
                title_prop = props.get("Spanish") or props.get("Name") or list(props.values())[0]
                
                if title_prop and title_prop.get("title"):
                    title_text = title_prop["title"][0]["plain_text"]
                    results.append({"id": page["id"], "title": title_text})
            except:
                continue
                
        return results
    except Exception as e:
        print(f"❌ 获取标题失败 (httpx): {e}")
        return []

def create_study_note(title, category, summary, blocks):
    """创建西语笔记 (通道 A)"""
    print(f"✍️ 正在创建西语笔记: {title}...")
    children_blocks = build_content_blocks(summary, blocks)
    
    try:
        notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties={
                "Spanish": {"title": [{"text": {"content": clean_text(title)}}]},
                "Category": {"select": {"name": category}},
            },
            children=children_blocks
        )
        print("✅ 创建成功！")
        return True
    except Exception as e:
        print(f"❌ 创建失败: {e}")
        return False

def create_general_note(title, tags, summary, url, content_blocks, db_id):
    """创建通用笔记 (通道 B)"""
    print(f"✍️ 正在创建通用笔记: {title}...")
    
    # 构造标签对象
    tag_objs = [{"name": tag} for tag in tags] if tags else []
    
    # 构造内容块 (摘要+正文)
    children_blocks = build_content_blocks(summary, content_blocks)
    
    try:
        notion.pages.create(
            parent={"database_id": db_id},
            properties={
                "Name": {"title": [{"text": {"content": clean_text(title)}}]},
                "Tags": {"multi_select": tag_objs},
                "URL": {"url": url if url else None},
                "Type": {"select": {"name": "Article"}}
            },
            children=children_blocks
        )
        print("✅ 通用笔记创建成功！")
        return True
    except Exception as e:
        print(f"❌ 通用笔记创建失败: {e}")
        return False

def get_page_structure(page_id):
    """获取页面结构 (用于融合)"""
    try:
        blocks = notion.blocks.children.list(block_id=page_id).get("results", [])
        structure_desc = []
        tables = []
        
        for b in blocks:
            b_type = b["type"]
            if b_type == "heading_2":
                text = b["heading_2"]["rich_text"][0]["plain_text"]
                structure_desc.append(f"[标题] {text}")
            elif b_type == "table":
                table_id = b["id"]
                # 获取表格内容（这里简化，只标记有表格）
                tables.append({"id": table_id, "desc": "现有表格"})
                structure_desc.append(f"[表格] ID:{table_id}")
                
        return "\n".join(structure_desc), tables
    except Exception as e:
        print(f"读取页面结构失败: {e}")
        return "", []

def append_to_page(page_id, summary, blocks):
    """追加内容到页面末尾"""
    print(f"➕ 正在追加内容到页面 {page_id}...")
    children = []
    # 加个分割线
    children.append({"object": "block", "type": "divider", "divider": {}})
    # 如果有新摘要，也加上
    if summary:
        children.append({
            "object": "block", 
            "type": "paragraph", 
            "paragraph": {"rich_text": [{"text": {"content": f"📝 补充更新: {summary}", "annotations": {"italic": True}}}]}
        })
    
    children.extend(build_content_blocks(None, blocks))
    
    try:
        notion.blocks.children.append(block_id=page_id, children=children)
        print("✅ 追加成功！")
    except Exception as e:
        print(f"❌ 追加失败: {e}")

def add_row_to_table(table_id, row_data):
    """向现有表格插入行"""
    print(f"➕ 正在插入表格行...")
    try:
        row_cells = [{"text": {"content": str(cell)}} for cell in row_data]
        notion.blocks.children.append(
            block_id=table_id,
            children=[{
                "type": "table_row",
                "table_row": {"cells": row_cells}
            }]
        )
        print("✅ 插入成功！")
    except Exception as e:
        print(f"❌ 插入表格失败: {e}")