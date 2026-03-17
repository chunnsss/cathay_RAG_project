"""
metrics.py — 計算 benchmark evaluation metrics

Retrieval metrics（自動計算）：
  compute_hit_at_5      → Hit@5
  compute_recall_at_5   → Recall@5
  compute_precision_at_5 → Precision@5
  compute_mrr           → MRR

Summary：
  compute_summary       → 所有指標的整體平均
"""

from typing import List, Optional


# ─── 單題 Retrieval Metrics ─────────────────────────────────

def compute_hit_at_5(expected: List[int], retrieved: List[int]) -> int:
    """
    Hit@5：expected 中任一條款出現在 retrieved 中 → 1，否則 → 0
    """
    return int(any(a in retrieved for a in expected))


def compute_recall_at_5(expected: List[int], retrieved: List[int]) -> float:
    """
    Recall@5 = 命中的正確條款數 / expected 總數

    若 expected 為空回傳 0。
    """
    if not expected:
        return 0.0
    hit_count = sum(1 for a in expected if a in retrieved)
    return hit_count / len(expected)


def compute_precision_at_5(expected: List[int], retrieved: List[int]) -> float:
    """
    Precision@5 = retrieved 中正確條款數 / retrieved 總數

    若 retrieved 為空回傳 0。
    """
    if not retrieved:
        return 0.0
    hit_count = sum(1 for a in retrieved if a in expected)
    return hit_count / len(retrieved)


def compute_mrr(expected: List[int], retrieved: List[int]) -> float:
    """
    MRR（Mean Reciprocal Rank）：
    找到第一個命中位置的倒數排名。
    第1名 → 1.0，第2名 → 0.5，第3名 → 0.333...，未命中 → 0.0
    """
    for idx, a in enumerate(retrieved):
        if a in expected:
            return 1 / (idx + 1)
    return 0.0


# ─── 整體 Summary ───────────────────────────────────────────

def compute_summary(results: List[dict]) -> dict:
    """
    根據 per-question results 計算整體 summary。

    自動計算（retrieval metrics）：
      hit_at_5, recall_at_5, precision_at_5, mrr

    人工評分（需填寫 CSV）：
      avg_answer_score_manual

    Returns:
        {
            "total_questions": int,
            "hit_at_5": float,
            "recall_at_5": float,
            "precision_at_5": float,
            "mrr": float,
            "citation_accuracy": float,
            "avg_answer_score_manual": float | None
        }
    """
    total = len(results)
    if total == 0:
        return {
            "total_questions": 0,
            "hit_at_5": 0.0,
            "recall_at_5": 0.0,
            "precision_at_5": 0.0,
            "mrr": 0.0,
            "citation_accuracy": 0.0,
            "avg_answer_score_manual": None,
        }

    def _avg(key: str) -> float:
        return round(sum(r[key] for r in results) / total, 4)

    citation_hits = sum(r["citation_hit"] for r in results)

    scored = [r["answer_score_manual"] for r in results if r["answer_score_manual"] is not None]
    avg_score: Optional[float] = round(sum(scored) / len(scored), 4) if scored else None

    return {
        "total_questions": total,
        "hit_at_5": _avg("hit_at_5"),
        "recall_at_5": _avg("recall_at_5"),
        "precision_at_5": _avg("precision_at_5"),
        "mrr": _avg("mrr"),
        "citation_accuracy": round(citation_hits / total, 4),
        "avg_answer_score_manual": avg_score,
    }
