"""
ingest.py — 資料處理 Pipeline 主程式
流程：PDF → parse → JSON → embedding → SQLite

執行方式：python ingest.py
"""

import json
import config
from parser import parse_pdf
from embedding import embed_texts
from db import init_db, save_articles, close


def main():
    print("=" * 50)
    print("開始資料處理 Pipeline")
    print("=" * 50)

    # Step 1: 解析 PDF → Article 清單
    print(f"\n[1/4] 解析 PDF：{config.PDF_PATH}")
    articles = parse_pdf(config.PDF_PATH)
    if not articles:
        raise ValueError("parse_pdf 回傳空清單，請確認 PDF 格式是否正確")

    # Step 2: 預覽結構（輸出前 3 筆 JSON）
    print(f"\n[2/4] 結構預覽（前 3 筆）：")
    for art in articles[:3]:
        print(json.dumps(art.to_dict(), ensure_ascii=False, indent=2))

    # Step 3: Embedding
    print(f"\n[3/4] 取得 Embedding...")
    texts = [
        f"{art.article_title} {art.clause_type} {art.scenario_name}\n{art.content}"
        for art in articles
    ]
    embeddings = embed_texts(texts)

    # Step 4: 存入 SQLite
    print(f"\n[4/4] 存入資料庫：{config.DB_PATH}")
    conn = init_db(config.DB_PATH)
    save_articles(conn, articles, embeddings)
    close(conn)

    print("\n" + "=" * 50)
    print("[DONE] 資料處理完成！可以啟動 chatbot 了")
    print("   執行：streamlit run app.py")
    print("=" * 50)


if __name__ == "__main__":
    main()
