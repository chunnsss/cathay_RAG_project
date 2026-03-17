"""
export.py — 匯出評估結果

輸出檔案：
  results.jsonl  — 每題一行（主要格式）
  summary.json   — 整體指標
  results.json   — 完整結果（summary + results 合併，方便閱讀）
  results.csv    — 人工審閱 / 填寫評分用
"""

import csv
import json
import os
from typing import List


def export_results(results: List[dict], summary: dict, output_path: str) -> None:
    """
    Args:
        results:     per-question evaluation result list
        summary:     compute_summary() 回傳的 summary dict
        output_path: 輸出 JSON 路徑（其他檔案產生在同目錄）
    """
    out_dir = os.path.dirname(output_path)
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(output_path)[0]  # 不含副檔名的路徑前綴

    # ─── results.jsonl（每題一行） ──────────────────────────
    jsonl_path = base + ".jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[OK] JSONL 結果已儲存：{jsonl_path}")

    # ─── summary.json ───────────────────────────────────────
    summary_path = os.path.join(out_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"[OK] Summary 已儲存：{summary_path}")

    # ─── results.json（完整，方便 debug 閱讀） ──────────────
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=2)
    print(f"[OK] JSON 結果已儲存：{output_path}")

    # ─── results.csv（人工審閱 / 填分用） ───────────────────
    csv_path = base + ".csv"
    _export_csv(results, csv_path)


def _export_csv(results: List[dict], csv_path: str) -> None:
    """輸出 CSV，包含新增的 retrieval metrics 欄位。"""
    if not results:
        return

    fieldnames = [
        "id",
        "question",
        "expected_articles",
        "top5_retrieved_articles",
        "cited_articles",
        # retrieval metrics（自動計算）
        "hit_at_5",
        "recall_at_5",
        "precision_at_5",
        "mrr",
        # citation
        "citation_hit",
        # 人工填寫
        "answer_score_manual",  # 0=錯誤, 1=部分正確, 2=正確
        "notes",
        "final_answer",
    ]

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow({
                "id": row["id"],
                "question": row["question"],
                "expected_articles": "|".join(str(a) for a in row["expected_articles"]),
                "top5_retrieved_articles": "|".join(str(a) for a in row["top5_retrieved_articles"]),
                "cited_articles": "|".join(str(a) for a in row["cited_articles"]),
                "hit_at_5": row["hit_at_5"],
                "recall_at_5": row["recall_at_5"],
                "precision_at_5": row["precision_at_5"],
                "mrr": row["mrr"],
                "citation_hit": row["citation_hit"],
                "answer_score_manual": row.get("answer_score_manual") or "",
                "notes": row.get("notes") or "",
                "final_answer": row["final_answer"][:300],
            })

    print(f"[OK] CSV 結果已儲存：{csv_path}")
