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
    return str(text)[:2000]  # 确保转为字符串并截断

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
            # === 核心修复：表格结构修正 ===
            table_rows = []
            
            # 1. 处理表头
            if 'headers' in content:
                # 关键修改：每个 header 必须包在 [] 里，变成 [[text], [text]]
                header_cells = [[{"text": {"content": str(h)}}] for h in content['headers']]
                table_rows.append({"type": "table_row", "table_row": {"cells": header_cells}})
            
            # 2. 处理数据行
            if 'rows' in content:
                for row in content['rows']:
                    # 关键修改：每个 cell 也必须包在 [] 里
                    row_cells = [[{"text": {"content": str(c)}}] for c in row]
                    table_rows.append({"type": "table_row", "table_row": {"cells": row_cells}})
            
            # 只有当有行数据时才添加表格块
            if table_rows:
                children.append({
                    "object": "block",
                    "type": "table",
                    "table": {
                        "table_width": len(content.get('headers', ['A'])),
                        "has_column_header": True, # 声明第一行是表头
                        "has_row_header": False,
                        "children": table_rows
                    }
                })

    return children

# --- 功能函数 ---

def get_all_page_titles():
    """获取现有笔记标题 (httpx 实现)"""
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {os.getenv('NOTION_TOKEN')}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    try:
        payload = {"filter_properties": ["title"]}
        response = httpx.post(url, headers=headers, json=payload, timeout=10.0)
        data = response.json()
        
        results = []
        for page in data.get("results", []):
            try:
                props = page.get("properties", {})
                # 兼容不同列名
                title_prop = props.get("Spanish") or props.get("Name") or list(props.values())[0]
                
                if title_prop and title_prop.get("title"):
                    title_text = title_prop["title"][0]["plain_text"]
                    results.append({"id": page["id"], "title": title_text})
            except:
                continue
        return results
    except Exception as e:
        print(f"❌ 获取标题失败: {e}")
        return []

def create_study_note(title, category, summary, blocks):
    """创建西语笔记"""
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

def create_general_note(data, original_url=None):
    """
    在 Notion 创建通用笔记 (带摘要 + 核心知识点)
    """
    notion = Client(auth=NOTION_TOKEN)
    
    # 1. 准备摘要块 (Callout)
    children_blocks = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"text": {"content": data.get('summary', '无摘要')}}],
                "icon": {"emoji": "💡"},
                "color": "gray_background"
            }
        },
        # 加一个分割线
        {
            "object": "block",
            "type": "divider",
            "divider": {}
        },
        # 加一个小标题
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"text": {"content": "📝 核心知识点 (Key Takeaways)"}}],
                "color": "blue"
            }
        }
    ]

    # 2. 循环添加核心知识点 (Bullet Points)
    key_points = data.get('key_points', [])
    for point in key_points:
        children_blocks.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"text": {"content": str(point)}}]
            }
        })

    # 3. 如果有 URL，加在最后
    if original_url:
        children_blocks.append({
             "object": "block",
             "type": "paragraph",
             "paragraph": {
                 "rich_text": [
                     {"text": {"content": "🔗 来源链接: "}},
                     {"text": {"content": original_url, "link": {"url": original_url}}}
                 ]
             }
        })

    # 4. 创建页面
    new_page = notion.pages.create(
        parent={"database_id": NOTION_DB_ID},
        properties={
            "Name": {"title": [{"text": {"content": data.get('title', '无标题')}}]},
            "Tags": {"multi_select": [{"name": tag} for tag in data.get('tags', [])]},
            "Type": {"select": {"name": "Article"}},
            "URL": {"url": original_url if original_url else None}
        },
        children=children_blocks
    )
    
    print(f"✅ 通用笔记已创建: {data.get('title')}")
    return new_page['url']

def get_page_structure(page_id):
    """获取页面结构"""
    try:
        blocks = notion.blocks.children.list(block_id=page_id).get("results", [])
        structure_desc = []
        tables = []
        for b in blocks:
            if b["type"] == "heading_2":
                text = b["heading_2"]["rich_text"][0]["plain_text"]
                structure_desc.append(f"[标题] {text}")
            elif b["type"] == "table":
                tables.append({"id": b["id"], "desc": "现有表格"})
                structure_desc.append(f"[表格] ID:{b['id']}")
        return "\n".join(structure_desc), tables
    except Exception as e:
        return "", []

def append_to_page(page_id, summary, blocks):
    """追加内容"""
    print(f"➕ 正在追加内容...")
    children = []
    children.append({"object": "block", "type": "divider", "divider": {}})
    if summary:
        children.append({
            "object": "block", 
            "type": "paragraph", 
            "paragraph": {"rich_text": [{"text": {"content": f"📝 补充: {summary}", "annotations": {"italic": True}}}]}
        })
    children.extend(build_content_blocks(None, blocks))
    
    try:
        notion.blocks.children.append(block_id=page_id, children=children)
        print("✅ 追加成功！")
    except Exception as e:
        print(f"❌ 追加失败: {e}")

def add_row_to_table(table_id, row_data):
    """插入表格行"""
    print(f"➕ 正在插入表格行...")
    try:
        # 修复：这里的 row_data 也要遵循 [[text], [text]] 结构
        row_cells = [[{"text": {"content": str(cell)}}] for cell in row_data]
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