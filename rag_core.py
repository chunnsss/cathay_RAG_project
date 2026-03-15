"""
rag_core.py — 檢索 + 生成核心邏輯

核心函式：
  ask(question) → 端到端問答入口
  search_similar(query, top_k) → 向量相似度檢索
  get_embedding(text) → 文字轉向量
"""

import json
import sqlite3

import numpy as np
from openai import OpenAI

import config


# ─── OpenAI Client（模組級別，避免重複建立） ───────────
_client = OpenAI(api_key=config.OPENAI_API_KEY)


# ─── System Prompt ─────────────────────────────────────
SYSTEM_PROMPT = """
你是一位專業且謹慎的保險條款顧問，專門根據提供的「海外旅行不便險」條款內容回答問題。

你的任務不是只回覆單一句答案，而是要：
1. 先直接回答使用者問題的核心答案
2. 若同一條款、相鄰條款或同一理賠主題中，有與問題高度相關的重要資訊，應一併補充
3. 補充資訊僅限於與使用者問題高度相關的內容，不可過度延伸

【回答原則】
1. 只能根據提供的條款內容回答，不得自行補充常識、實務經驗、法規或未出現在條款中的內容
2. 每個重要結論後面都要標示條款來源，例如：
   - 依據第三十條
   - 依據第五十七條、第五十九條
3. 若提供的條款內容不足以回答，必須明確說：
   「目前提供的條款中未包含相關資訊」
4. 使用繁體中文回答
5. 語氣要專業、清楚、像協助民眾理解條款的保險顧問
6. 不可把不相關的條款硬塞進答案
7. 若不同條款分別涉及「理賠條件、理賠文件、不保事項、通知義務、時效」，可依問題關聯性一起整理

【你應優先補充的相關資訊類型】
當使用者問到某一保險事故時，除回答核心問題外，應優先檢查是否還有以下資訊可補充：
- 理賠門檻 / 成立條件
- 給付方式 / 給付次數 / 給付上限
- 應備文件
- 不保事項 / 例外情形
- 事故發生後應採取的處理步驟
- 通知義務或時限

【輸出格式】
請盡量依下列格式回答：

【核心答案】
先用 1～2 句直接回答使用者問題。

【相關補充】
若有高度相關資訊，條列整理，僅列出與本題直接相關者。

【條款依據】
列出本次回答所依據的條款編號。

如果查無答案，請改為：
【核心答案】
目前提供的條款中未包含相關資訊。

【條款依據】
無明確對應條款
"""


def get_embedding(text: str) -> list[float]:
    """將文字轉為向量"""
    response = _client.embeddings.create(
        model=config.EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """計算兩個向量的 cosine similarity"""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def search_similar(query: str, top_k: int = None) -> list[dict]:
    """
    從 SQLite 讀取所有 chunks，計算與 query 的相似度，
    回傳 Top-K 最相似的 chunks。

    回傳格式: [{"article_no": str, "content": str, "page": int, "score": float}, ...]
    """
    if top_k is None:
        top_k = config.TOP_K

    # 取得 query 的 embedding
    query_emb = np.array(get_embedding(query))

    # 從 SQLite 讀取所有 chunks
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.execute("SELECT article_no, content, page, embedding FROM chunks")
    rows = cursor.fetchall()
    conn.close()

    # 計算相似度
    results = []
    for article_no, content, page, emb_json in rows:
        chunk_emb = np.array(json.loads(emb_json))
        score = cosine_similarity(query_emb, chunk_emb)
        results.append({
            "article_no": article_no,
            "content": content,
            "page": page,
            "score": score,
        })

    # 排序取 Top-K
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]



def build_prompt(question, retrieved_chunks):
    context_parts = []
    for chunk in retrieved_chunks:
        context_parts.append(
            f"【來源: {chunk['article_no']}, 頁碼: P.{chunk['page']}】\n{chunk['content']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    return f"""你現在要根據提供的條款內容回答使用者問題。

請注意：
1. 先回答使用者問題的核心答案
2. 若同一條款或相鄰條款中有與本問題高度相關的理賠條件、文件、不保事項、處理步驟或限制，請一併補充
3. 若條款無法支持答案，請明確說明「目前提供的條款中未包含相關資訊」
4. 不可使用條款以外的知識

===== 相關條款 =====
{context}

===== 使用者問題 =====
{question}
"""


def ask(question: str) -> dict:
    """
    端到端問答入口。

    輸入：使用者問題
    輸出：{"answer": str, "sources": [{"article_no": str, "page": int, "score": float}]}
    """
    # Step 1: 檢索相關 chunks
    chunks = search_similar(question)

    # Step 2: 組裝 prompt
    user_prompt = build_prompt(question, chunks)

    # Step 3: 呼叫 LLM
    response = _client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,  # 低溫度 → 更忠實於條款內容
    )

    answer = response.choices[0].message.content

    # 整理引用來源
    sources = [
        {"article_no": c["article_no"], "page": c["page"], "score": round(c["score"], 4)}
        for c in chunks
    ]

    return {"answer": answer, "sources": sources}
