"""
evaluator.py — 逐題執行 RAG pipeline 並評估結果

主要函式：
  evaluate_question(item) → per-question result dict
  run_benchmark(questions) → List[dict]
"""

import os
import re
import sys
from typing import List, Optional

# 確保能 import 上層目錄的 rag_core
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import rag_core
from evaluation.metrics import (
    compute_hit_at_5,
    compute_recall_at_5,
    compute_precision_at_5,
    compute_mrr,
)


# ─── 中文數字轉換 ─────────────────────────────────────────

_CN_MAP = {
    '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
}
_UNIT_MAP = {'十': 10, '百': 100}


def _chinese_to_int(s: str) -> int:
    """將中文數字字串轉為整數（支援到三位數）。"""
    result = 0
    current = 0
    is_first = True
    for char in s:
        if char in _CN_MAP:
            current = _CN_MAP[char]
            is_first = False
        elif char in _UNIT_MAP:
            # 例如「第十條」，十前面沒有數字時視為 1
            if is_first:
                current = 1
                is_first = False
            result += current * _UNIT_MAP[char]
            current = 0
    result += current
    return result


def _parse_article_no_to_int(article_no: str) -> Optional[int]:
    """
    將條號字串（如 '第三十條 '、'第57條 '）解析為整數。
    無法解析（如 '前言'、'段落-1'）時回傳 None。
    """
    match = re.search(r'第([\d一二三四五六七八九十百零]+)條', article_no)
    if not match:
        return None
    num_str = match.group(1)
    if num_str.isdigit():
        return int(num_str)
    return _chinese_to_int(num_str)


def _extract_cited_from_answer(answer: str) -> List[int]:
    """
    從回答文字中解析引用條款編號。

    例如「依據第三十條」、「依據第五十七條、第五十九條」
    皆可正確擷取。
    """
    pattern = r'第([\d一二三四五六七八九十百零]+)條'
    matches = re.findall(pattern, answer)
    seen: set = set()
    articles: List[int] = []
    for m in matches:
        n = int(m) if m.isdigit() else _chinese_to_int(m)
        if n and n not in seen:
            articles.append(n)
            seen.add(n)
    return articles


# ─── 單題評估 ─────────────────────────────────────────────

def evaluate_question(item: dict) -> dict:
    """
    對單題執行 RAG pipeline 並評估。

    Args:
        item: benchmark 題目 dict，需含 id, question, expected_articles

    Returns:
        per-question evaluation result dict
    """
    question: str = item["question"]
    expected: List[int] = item["expected_articles"]

    # 呼叫 RAG pipeline
    result = rag_core.ask(question)
    answer: str = result["answer"]
    sources: List[dict] = result["sources"]

    # 整理 retrieved_articles（去重，保持檢索排名順序）
    seen: set = set()
    retrieved: List[int] = []
    for src in sources:
        n = _parse_article_no_to_int(src["article_no"])
        if n is not None and n not in seen:
            retrieved.append(n)
            seen.add(n)

    # 整理 cited_articles（從回答文字中 parse）
    cited: List[int] = _extract_cited_from_answer(answer)

    # 評估 hit（舊指標，保留相容）
    retrieval_hit: int = 1 if any(a in retrieved for a in expected) else 0
    citation_hit: int = 1 if any(a in cited for a in expected) else 0

    # 新增 Retrieval Evaluation Metrics（自動計算）
    hit_at_5 = compute_hit_at_5(expected, retrieved)
    recall_at_5 = round(compute_recall_at_5(expected, retrieved), 4)
    precision_at_5 = round(compute_precision_at_5(expected, retrieved), 4)
    mrr = round(compute_mrr(expected, retrieved), 4)

    return {
        "id": item["id"],
        "question": question,
        "expected_articles": expected,
        "top5_retrieved_articles": retrieved,
        "cited_articles": cited,
        "final_answer": answer,
        # retrieval metrics
        "hit_at_5": hit_at_5,
        "recall_at_5": recall_at_5,
        "precision_at_5": precision_at_5,
        "mrr": mrr,
        # citation & manual
        "retrieval_hit": retrieval_hit,
        "citation_hit": citation_hit,
        "answer_score_manual": None,  # 待人工填寫（0=錯誤, 1=部分正確, 2=正確）
        "notes": "",
    }


# ─── 批次評估 ─────────────────────────────────────────────

def run_benchmark(questions: List[dict]) -> List[dict]:
    """
    逐題執行評估，回傳 results list。

    Args:
        questions: load_benchmark() 回傳的題目 list

    Returns:
        List of per-question evaluation result dicts
    """
    results: List[dict] = []
    total = len(questions)

    for i, item in enumerate(questions, start=1):
        print(f"\n[{i}/{total}] {item['question']}")
        try:
            result = evaluate_question(item)
        except Exception as e:
            print(f"  [ERROR] 評估失敗：{e}")
            result = {
                "id": item["id"],
                "question": item["question"],
                "expected_articles": item["expected_articles"],
                "top5_retrieved_articles": [],
                "cited_articles": [],
                "final_answer": f"[ERROR] {e}",
                "hit_at_5": 0,
                "recall_at_5": 0.0,
                "precision_at_5": 0.0,
                "mrr": 0.0,
                "retrieval_hit": 0,
                "citation_hit": 0,
                "answer_score_manual": None,
                "notes": f"評估時發生例外：{e}",
            }

        print(f"  expected:      {result['expected_articles']}")
        print(f"  retrieved:     {result['top5_retrieved_articles']}")
        print(f"  cited:         {result['cited_articles']}")
        print(f"  hit@5={result['hit_at_5']}  recall@5={result['recall_at_5']:.2f}  precision@5={result['precision_at_5']:.2f}  mrr={result['mrr']:.4f}")
        results.append(result)

    return results
