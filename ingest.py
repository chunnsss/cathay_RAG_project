"""
ingest.py — 資料處理 Pipeline
PDF → 文字提取 → 按條號分塊 → Embedding → 存入 SQLite

執行方式：python ingest.py
"""

import os
import re
import json
import sqlite3

import pdfplumber
from openai import OpenAI

import config


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """從 PDF 提取每頁文字，回傳 [{page: int, text: str}, ...]"""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                pages.append({"page": i, "text": text.strip()})
    print(f"[OK] 提取完成：共 {len(pages)} 頁有文字內容")
    return pages


def chunk_by_article(pages: list[dict]) -> list[dict]:
    """
    將全文按條號（第X條）切分為 chunks。
    每個 chunk 包含：article_no, content, page
    """
    # 合併全文，但保留頁碼標記
    full_text = ""
    page_markers = []  # (char_position, page_number)
    for p in pages:
        page_markers.append((len(full_text), p["page"]))
        full_text += p["text"] + "\n"

    # 找所有條號位置
    pattern = config.CHUNK_PATTERN
    matches = list(re.finditer(pattern, full_text, re.MULTILINE))

    chunks = []

    if not matches:
        # 沒有找到條號結構，退回固定長度分塊
        print("[!] 未找到條號結構，改用固定長度分塊")
        chunk_size = config.MAX_CHUNK_LENGTH
        for i in range(0, len(full_text), chunk_size):
            chunk_text = full_text[i:i + chunk_size].strip()
            if chunk_text:
                page_no = _find_page(i, page_markers)
                chunks.append({
                    "article_no": f"段落-{len(chunks) + 1}",
                    "content": chunk_text,
                    "page": page_no,
                })
    else:
        # 處理第一個條號之前的文字（前言 / 名詞定義等）
        if matches[0].start() > 0:
            preamble = full_text[:matches[0].start()].strip()
            if preamble:
                chunks.append({
                    "article_no": "前言",
                    "content": preamble,
                    "page": 1,
                })

        # 按條號切分
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
            chunk_text = full_text[start:end].strip()

            if chunk_text:
                article_no = match.group()
                page_no = _find_page(start, page_markers)
                chunks.append({
                    "article_no": article_no,
                    "content": chunk_text,
                    "page": page_no,
                })

    print(f"[OK] 分塊完成：共 {len(chunks)} 個 chunks")
    for c in chunks:
        preview = c["content"][:40].replace("\n", " ")
        print(f"    {c['article_no']:>8s} | 頁 {c['page']} | {preview}...")
    return chunks


def _find_page(char_pos: int, page_markers: list[tuple]) -> int:
    """根據字元位置找到對應頁碼"""
    page = 1
    for pos, p in page_markers:
        if char_pos >= pos:
            page = p
        else:
            break
    return page


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """批量取得文字的 embedding 向量"""
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.embeddings.create(
        model=config.EMBEDDING_MODEL,
        input=texts,
    )
    embeddings = [item.embedding for item in response.data]
    print(f"[OK] Embedding 完成：{len(embeddings)} 個向量，維度 {len(embeddings[0])}")
    return embeddings


def init_db(db_path: str):
    """初始化 SQLite 資料庫"""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            article_no  TEXT,
            content     TEXT,
            page        INTEGER,
            embedding   TEXT
        )
    """)
    # 清除舊資料（重新跑 ingest 時）
    conn.execute("DELETE FROM chunks")
    conn.commit()
    return conn


def save_to_db(conn: sqlite3.Connection, chunks: list[dict], embeddings: list[list[float]]):
    """將 chunks 和 embeddings 存入 SQLite"""
    for chunk, emb in zip(chunks, embeddings):
        conn.execute(
            "INSERT INTO chunks (article_no, content, page, embedding) VALUES (?, ?, ?, ?)",
            (chunk["article_no"], chunk["content"], chunk["page"], json.dumps(emb)),
        )
    conn.commit()
    print(f"[OK] 已存入 SQLite：{len(chunks)} 筆資料")


def main():
    print("=" * 50)
    print("開始資料處理 Pipeline")
    print("=" * 50)

    # Step 1: 提取 PDF 文字
    print(f"\n讀取 PDF：{config.PDF_PATH}")
    pages = extract_text_from_pdf(config.PDF_PATH)

    # Step 2: 按條號分塊
    print("\n開始分塊...")
    chunks = chunk_by_article(pages)

    # Step 3: 取得 Embedding
    print("\n取得 Embedding...")
    texts = [c["content"] for c in chunks]
    embeddings = get_embeddings(texts)

    # Step 4: 存入 SQLite
    print(f"\n存入資料庫：{config.DB_PATH}")
    conn = init_db(config.DB_PATH)
    save_to_db(conn, chunks, embeddings)
    conn.close()

    print("\n" + "=" * 50)
    print("[DONE] 資料處理完成! 可以啟動 chatbot 了")
    print("   執行：streamlit run app.py")
    print("=" * 50)


if __name__ == "__main__":
    main()
