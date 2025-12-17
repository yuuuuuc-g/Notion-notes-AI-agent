import os
from notion_client import Client

# === 1. 初始化配置 ===
# 确保你的 .env 文件里有这些变量
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DB_SPANISH_ID = os.environ.get("NOTION_DATABASE_ID")          # 西语数据库 ID
DB_GENERAL_ID = os.environ.get("NOTION_DATABASE_ID_GENERAL")  # 通用数据库 ID

# 初始化客户端
notion = Client(auth=NOTION_TOKEN)

# --- 工具函数：清洗文本 ---
def clean_text(text):
    """防止 Notion 因为文本过长或为 None 而报错"""
    if text is None:
        return ""
    return str(text)[:2000]  # Notion 一个 block 最多存 2000 字

# --- 功能 A: 创建西语笔记 (带单词表) ---
def create_study_note(title, summary, word_list, original_url=None):
    """
    参数:
    - title: 笔记标题
    - summary: 摘要
    - word_list: 单词列表 [{'word':..., 'meaning':..., 'example':...}]
    - original_url: 来源链接
    """
    print(f"✍️ Writing Spanish Note: {title}...")
    
    # 1. 构建单词表 (Table Blocks)
    table_rows = []
    
    # A. 表头
    table_rows.append({
        "type": "table_row",
        "table_row": {
            "cells": [
                [{"text": {"content": "单词/短语"}}],
                [{"text": {"content": "中文含义"}}],
                [{"text": {"content": "例句"}}],
            ]
        }
    })
    
    # B. 数据行 (循环 word_list)
    for item in word_list:
        # 确保每个字段都是字符串
        w = clean_text(item.get('word', ''))
        m = clean_text(item.get('meaning', ''))
        e = clean_text(item.get('example', ''))
        
        table_rows.append({
            "type": "table_row",
            "table_row": {
                "cells": [
                    [{"text": {"content": w}}],
                    [{"text": {"content": m}}],
                    [{"text": {"content": e}}],
                ]
            }
        })

    # 2. 组装页面内容 (Children)
    children_blocks = [
        # 摘要块 (Callout)
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"text": {"content": clean_text(summary)}}],
                "icon": {"emoji": "📝"},
                "color": "gray_background"
            }
        },
        # 标题
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"text": {"content": "📚 核心词汇表 (Vocabulario)"}}],
                "color": "orange"
            }
        },
        # 表格块
        {
            "object": "block",
            "type": "table",
            "table": {
                "table_width": 3,
                "has_column_header": True,
                "has_row_header": False,
                "children": table_rows
            }
        }
    ]

    # 3. 如果有 URL，加在最后
    if original_url:
        children_blocks.append({
             "object": "block",
             "type": "paragraph",
             "paragraph": {
                 "rich_text": [
                     {"text": {"content": "🔗 Source: "}},
                     {"text": {"content": original_url, "link": {"url": original_url}}}
                 ]
             }
        })

    # 4. 创建页面
    try:
        notion.pages.create(
            parent={"database_id": DB_SPANISH_ID},
            properties={
                "Name": {"title": [{"text": {"content": clean_text(title)}}]},
                "Tags": {"multi_select": [{"name": "Spanish"}]},
                # 如果你的数据库里有 "Type" 或 "Category" 列，可以在这里加
                "Type": {"select": {"name": "Study Note"}},
                "URL": {"url": original_url if original_url else None}
            },
            children=children_blocks
        )
        print("✅ Spanish Note Created Successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to create Spanish note: {e}")
        return False


# --- 功能 B: 创建通用笔记 (带 Key Points) ---
def create_general_note(data, original_url=None):
    """
    参数 data: 字典, 包含 title, summary, key_points (List[str]), tags
    """
    title = data.get('title', 'Unnamed Note')
    print(f"✍️ Writing General Note: {title}...")
    
    # 1. 准备摘要块
    children_blocks = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"text": {"content": clean_text(data.get('summary', 'No Summary'))}}],
                "icon": {"emoji": "💡"},
                "color": "gray_background"
            }
        },
        {
            "object": "block",
            "type": "divider",
            "divider": {}
        },
        {
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"text": {"content": "📝 Key Takeaways"}}],
                "color": "blue"
            }
        }
    ]

    # 2. 循环添加核心知识点 (Bullet Points)
    # main.py 传过来的是字符串列表 ['point1', 'point2']
    points = data.get('key_points', [])
    for point in points:
        children_blocks.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"text": {"content": clean_text(point)}}]
            }
        })

    # 3. 添加 URL
    if original_url:
        children_blocks.append({
             "object": "block",
             "type": "paragraph",
             "paragraph": {
                 "rich_text": [
                     {"text": {"content": "🔗 Source: "}},
                     {"text": {"content": original_url, "link": {"url": original_url}}}
                 ]
             }
        })

    # 4. 创建页面
    try:
        if not DB_GENERAL_ID:
            print("❌ Error: NOTION_DATABASE_ID_GENERAL is not set in .env")
            return False

        notion.pages.create(
            parent={"database_id": DB_GENERAL_ID},
            properties={
                "Name": {"title": [{"text": {"content": clean_text(title)}}]},
                "Tags": {"multi_select": [{"name": tag} for tag in data.get('tags', [])]},
                "Type": {"select": {"name": "General Knowledge"}},
                "URL": {"url": original_url if original_url else None}
            },
            children=children_blocks
        )
        print("✅ General Note Created Successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to create General note: {e}")
        return False