"""
db.py — SQLite 儲存模組
建立 articles 資料表並存入結構化條文與 embedding
"""

import os
import json
import sqlite3

from schema import Article


def init_db(db_path: str) -> sqlite3.Connection:
    """初始化資料庫，建立 articles 資料表（清除舊資料）"""
    dir_path = os.path.dirname(db_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            insurer          TEXT,
            product          TEXT,
            document_type    TEXT,
            document_version TEXT,
            source_file      TEXT,
            chapter_no       INTEGER,
            chapter_title    TEXT,
            chapter_code     TEXT,
            article_no       INTEGER,
            article_title    TEXT,
            article_full_id  TEXT,
            clause_type      TEXT,
            scenario_code    TEXT,
            scenario_name    TEXT,
            content          TEXT,
            embedding        TEXT
        )
    """)
    conn.execute("DELETE FROM articles")
    conn.commit()
    print("[OK] 資料庫初始化完成")
    return conn


def save_articles(
    conn: sqlite3.Connection,
    articles: list[Article],
    embeddings: list[list[float]],
) -> None:
    """將條文清單與對應 embedding 寫入資料庫"""
    if len(articles) != len(embeddings):
        raise ValueError(f"articles ({len(articles)}) 與 embeddings ({len(embeddings)}) 長度不一致")
    rows = []
    for art, emb in zip(articles, embeddings):
        d = art.to_dict()
        rows.append((
            d["insurer"], d["product"], d["document_type"],
            d["document_version"], d["source_file"],
            d["chapter_no"], d["chapter_title"], d["chapter_code"],
            d["article_no"], d["article_title"], d["article_full_id"],
            d["clause_type"], d["scenario_code"], d["scenario_name"],
            d["content"], json.dumps(emb, ensure_ascii=False),
        ))

    conn.executemany("""
        INSERT INTO articles (
            insurer, product, document_type, document_version, source_file,
            chapter_no, chapter_title, chapter_code,
            article_no, article_title, article_full_id,
            clause_type, scenario_code, scenario_name,
            content, embedding
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    conn.commit()
    print(f"[OK] 已存入 SQLite：{len(rows)} 筆條文")


def close(conn: sqlite3.Connection) -> None:
    conn.close()
