#!/usr/bin/env python3
"""
决策分析模板 Embedding 向量生成脚本

功能：
1. 从 prompt_configs 表加载 category='decision_analysis' 的模板
2. 使用阿里 text-embedding-v2 生成向量
3. 存储到 decision_analysis_template_embeddings 表

用法：
    python ai/analysis/generate_template_embeddings.py
"""

import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

import psycopg2
from psycopg2.extras import execute_batch

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ai.engine.alibaba_embedding import AlibabaEmbedding


# 数据库配置
DB_CONFIG = {
    "host": "192.168.1.225",
    "port": 5432,
    "user": "postgres",
    "password": "admin123",
    "database": "dev_metric"
}

# Embedding 配置
EMBEDDING_BATCH_SIZE = 10  # 每批处理的模板数
PROMPT_PREVIEW_LENGTH = 200  # prompt_preview 最大长度


def get_db_connection():
    """获取数据库连接"""
    return psycopg2.connect(**DB_CONFIG)


def ensure_embedding_column_exists(conn):
    """确保 embedding 列存在"""
    cur = conn.cursor()

    # 检查列是否存在
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'decision_analysis_template_embeddings'
        AND column_name = 'embedding'
    """)
    exists = cur.fetchone() is not None

    if not exists:
        print("[INFO] 添加 embedding 列到 decision_analysis_template_embeddings 表...")
        cur.execute("""
            ALTER TABLE decision_analysis_template_embeddings
            ADD COLUMN embedding JSONB
        """)
        conn.commit()
        print("[OK] embedding 列已添加")
    else:
        print("[INFO] embedding 列已存在")

    cur.close()


def load_templates(conn) -> List[Dict[str, Any]]:
    """从 prompt_configs 表加载 decision_analysis 模板"""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, prompt_text, category
        FROM prompt_configs
        WHERE category = 'decision_analysis'
        AND status = 1
    """)
    rows = cur.fetchall()
    cur.close()

    templates = []
    for row in rows:
        templates.append({
            "id": row[0],
            "name": row[1],
            "prompt_text": row[2],
            "category": row[3]
        })

    print(f"[INFO] 加载了 {len(templates)} 个 decision_analysis 模板")
    return templates


def extract_keywords(prompt_text: str) -> str:
    """从 prompt_text 中提取关键词"""
    import re

    # 提取 {metric_xxx} 格式的指标名
    metric_placeholders = re.findall(r'\{metric_(\w+)\}', prompt_text)

    # 提取 {insights: [...]} 中的洞察类型
    insight_match = re.search(r'\{insights:\s*\[(.*?)\]\}', prompt_text)
    insights = []
    if insight_match:
        insights_str = insight_match.group(1)
        insights = [s.strip().strip('"\'') for s in insights_str.split(',')]

    # 合并关键词
    keywords = metric_placeholders + insights
    return ",".join(keywords) if keywords else ""


def generate_embeddings_batch(embedding_client: AlibabaEmbedding, texts: List[str]) -> List[Optional[List[float]]]:
    """批量生成 embedding 向量"""
    try:
        return embedding_client.embed(texts)
    except Exception as e:
        print(f"[ERROR] 批量生成 embedding 失败: {e}")
        return [None] * len(texts)


def save_embeddings(conn, embeddings_data: List[Dict[str, Any]]):
    """保存 embedding 数据到数据库"""
    if not embeddings_data:
        print("[WARN] 没有 embedding 数据需要保存")
        return

    cur = conn.cursor()

    # 先删除已存在的 embedding（根据 template_id）
    template_ids = [d["template_id"] for d in embeddings_data]
    cur.execute("""
        DELETE FROM decision_analysis_template_embeddings
        WHERE template_id = ANY(%s)
    """, (template_ids,))

    # 批量插入
    insert_sql = """
        INSERT INTO decision_analysis_template_embeddings
        (template_id, name, keywords, category, prompt_preview, embedding, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    values = [
        (
            d["template_id"],
            d["name"],
            d["keywords"],
            d["category"],
            d["prompt_preview"],
            json.dumps(d["embedding"]),
            datetime.now()
        )
        for d in embeddings_data
    ]

    execute_batch(cur, insert_sql, values)
    conn.commit()
    cur.close()

    print(f"[OK] 保存了 {len(embeddings_data)} 个 embedding")


def main():
    print("=" * 60)
    print("决策分析模板 Embedding 向量生成")
    print("=" * 60)

    # 初始化 embedding 客户端
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        print("[ERROR] DASHSCOPE_API_KEY 环境变量未设置")
        sys.exit(1)

    embedding_client = AlibabaEmbedding(api_key=api_key)
    print(f"[INFO] Embedding 客户端初始化完成 (text-embedding-v2, 1536维)")

    # 连接数据库
    try:
        conn = get_db_connection()
        print(f"[INFO] 数据库连接成功")
    except Exception as e:
        print(f"[ERROR] 数据库连接失败: {e}")
        sys.exit(1)

    # 确保 embedding 列存在
    ensure_embedding_column_exists(conn)

    # 加载模板
    templates = load_templates(conn)

    if not templates:
        print("[WARN] 没有找到 decision_analysis 模板")
        sys.exit(0)

    # 准备要生成 embedding 的文本
    # 使用 name + prompt_preview（前200字符）作为向量化的文本
    texts_to_embed = []
    template_indices = []

    for i, template in enumerate(templates):
        # 使用 name + prompt_preview 构建待向量化的文本
        prompt_preview = template["prompt_text"][:PROMPT_PREVIEW_LENGTH] if template["prompt_text"] else ""
        text_to_embed = f"{template['name']} {prompt_preview}"
        texts_to_embed.append(text_to_embed)
        template_indices.append(i)

    print(f"[INFO] 开始生成 {len(texts_to_embed)} 个 embedding...")

    # 批量生成 embedding
    embeddings_data = []
    total = len(texts_to_embed)

    for batch_start in range(0, total, EMBEDDING_BATCH_SIZE):
        batch_end = min(batch_start + EMBEDDING_BATCH_SIZE, total)
        batch_texts = texts_to_embed[batch_start:batch_end]

        print(f"[INFO] 处理批次 {batch_start + 1}-{batch_end}/{total}...")

        # 生成 embedding
        batch_embeddings = generate_embeddings_batch(embedding_client, batch_texts)

        # 构建 embedding 数据
        for i, embedding in enumerate(batch_embeddings):
            template_idx = template_indices[batch_start + i]
            template = templates[template_idx]

            if embedding is None:
                print(f"[WARN] 模板 {template['name']} embedding 生成失败，跳过")
                continue

            # 提取关键词
            keywords = extract_keywords(template["prompt_text"])

            # 构建 prompt_preview
            prompt_preview = template["prompt_text"][:PROMPT_PREVIEW_LENGTH] if template["prompt_text"] else ""

            embeddings_data.append({
                "template_id": template["id"],
                "name": template["name"],
                "keywords": keywords,
                "category": template["category"],
                "prompt_preview": prompt_preview,
                "embedding": embedding
            })

        print(f"[OK] 批次完成，当前累计 {len(embeddings_data)} 个 embedding")

    # 保存到数据库
    print("[INFO] 保存 embedding 到数据库...")
    save_embeddings(conn, embeddings_data)

    # 验证结果
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM decision_analysis_template_embeddings
        WHERE category = 'decision_analysis'
    """)
    count = cur.fetchone()[0]
    cur.close()
    conn.close()

    print("=" * 60)
    print(f"[完成] 共生成并保存 {count} 个 decision_analysis 模板 embedding")
    print("=" * 60)


if __name__ == "__main__":
    main()
