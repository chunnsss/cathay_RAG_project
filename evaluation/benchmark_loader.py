"""
benchmark_loader.py — 載入 benchmark 題庫

支援格式：.jsonl（每行一筆 JSON）
"""

import json
from typing import List


def load_benchmark(filepath: str) -> List[dict]:
    """
    讀取 benchmark.jsonl，回傳 list of dict。

    每筆格式：
    {
        "id": int,
        "question": str,
        "expected_articles": List[int],
        ...
    }
    """
    questions = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                questions.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[WARN] 第 {line_no} 行解析失敗，已略過：{e}")

    print(f"[OK] 載入 benchmark：共 {len(questions)} 題（{filepath}）")
    return questions
