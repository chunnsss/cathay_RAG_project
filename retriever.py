"""
retriever.py — 三段式檢索模組
Step A. metadata filter（scenario_code + clause_type）
Step B. embedding search（cosine similarity, Top-K=3）
Step C. entity expansion（跨主題補充條文）
"""

import json
import sqlite3

import numpy as np
from openai import OpenAI

import config

_client = OpenAI(api_key=config.OPENAI_API_KEY)

# intent → clause_type 映射
# coverage 不限制 clause_type：「X 算 Y 嗎？」類問題需要同時看承保範圍與不保事項才能答對
INTENT_CLAUSE_MAP: dict[str, str | None] = {
    "coverage":       None,
    "exclusion":      "exclusion",
    "claim_document": None,   # 申請流程類問題需同時看承保/不保/文件，不限 clause_type
    "general":        None,
}

# entity → scenario_code（用於跨主題補充）
ENTITY_SCENARIO_MAP: dict[str, str] = {
    "行動電話": "mobile_phone_theft",
    "手機":     "mobile_phone_theft",
    "護照":     "travel_document_loss",
    "旅行文件": "travel_document_loss",
    "信用卡":   "credit_card_fraud",
    "現金":     "cash_theft",
    "行李":     "baggage_loss",
}

TOP_K = 3


def _load_articles(conn: sqlite3.Connection, scenario_code: str | None, clause_type: str | None) -> list[dict]:
    """從 articles 資料表載入，依 metadata 過濾。"""
    conditions = []
    params = []

    if scenario_code and scenario_code != "general":
        conditions.append("scenario_code = ?")
        params.append(scenario_code)

    if clause_type:
        conditions.append("clause_type = ?")
        params.append(clause_type)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"SELECT id, article_no, article_title, clause_type, scenario_code, scenario_name, content, embedding FROM articles {where}"
    cursor = conn.execute(sql, params)

    rows = []
    for row in cursor.fetchall():
        rows.append({
            "id": row[0],
            "article_no": row[1],
            "article_title": row[2],
            "clause_type": row[3],
            "scenario_code": row[4],
            "scenario_name": row[5],
            "content": row[6],
            "embedding": json.loads(row[7]),
        })
    return rows


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0


def _embed(text: str) -> np.ndarray:
    response = _client.embeddings.create(model=config.EMBEDDING_MODEL, input=text)
    return np.array(response.data[0].embedding)


def _top_k_by_similarity(query_emb: np.ndarray, candidates: list[dict], k: int) -> list[dict]:
    scored = []
    for art in candidates:
        score = _cosine(query_emb, np.array(art["embedding"]))
        scored.append({**art, "score": round(score, 4)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]


def retrieve(question: str, parsed_query: dict) -> list[dict]:
    """
    三段式檢索，回傳去重後的條文清單（含 score）。

    參數：
        question     — 原始使用者問題
        parsed_query — query_parser.parse_query() 的輸出

    回傳：[{"article_no", "article_title", "clause_type", "scenario_code",
             "scenario_name", "content", "score"}, ...]
    """
    intent = parsed_query.get("intent", "general")
    scenario_code = parsed_query.get("scenario_code", "general")
    entities = parsed_query.get("entities", [])

    clause_type = INTENT_CLAUSE_MAP.get(intent)

    conn = sqlite3.connect(config.DB_PATH)

    # ── Step A: metadata filter ────────────────────────────────────────────
    candidates = _load_articles(conn, scenario_code, clause_type)

    # 若 metadata filter 後太少，放寬為不限 scenario 再試
    if len(candidates) < TOP_K:
        candidates = _load_articles(conn, None, clause_type)

    # ── Step B: embedding search ───────────────────────────────────────────
    query_emb = _embed(question)
    main_results = _top_k_by_similarity(query_emb, candidates, TOP_K)

    # 若最高分低於門檻，視為無相關條文
    if not main_results or main_results[0]["score"] < config.MIN_SIMILARITY:
        conn.close()
        return []

    for art in main_results:
        art["is_expansion"] = False

    # ── Step C: entity expansion ───────────────────────────────────────────
    seen_ids = {art["id"] for art in main_results}
    expansion_results = []

    for entity in entities:
        exp_scenario = ENTITY_SCENARIO_MAP.get(entity)
        if not exp_scenario:
            continue
        # 不要重複撈和主流程相同的 scenario
        if exp_scenario == scenario_code:
            continue
        exp_candidates = _load_articles(conn, exp_scenario, None)
        for art in _top_k_by_similarity(query_emb, exp_candidates, 3):
            if art["id"] not in seen_ids:
                art["is_expansion"] = True
                expansion_results.append(art)
                seen_ids.add(art["id"])

    # ── Step D: 強制補入 scenario 的 exclusion 條文 ───────────────────────────
    # 不保事項語意上離「申請流程」較遠，embedding search 不一定排得進來，
    # 但使用者決策一定需要知道「哪些情況不賠」，故強制補入。
    if scenario_code and scenario_code != "general":
        excl_candidates = _load_articles(conn, scenario_code, "exclusion")
        for art in _top_k_by_similarity(query_emb, excl_candidates, 2):
            if art["id"] not in seen_ids:
                art["is_expansion"] = False
                main_results.append(art)
                seen_ids.add(art["id"])

    conn.close()

    # 主結果在前，expansion 補充在後
    return main_results + expansion_results
