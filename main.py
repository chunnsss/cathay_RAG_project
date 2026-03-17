"""
main.py — 統一入口，支援 --mode chat / --mode benchmark

使用方式：
  python main.py --mode chat
  python main.py --mode benchmark
  python main.py --mode benchmark --benchmark-file benchmark.jsonl --output outputs/eval/results.json
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime

# 預設路徑
_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BENCHMARK_FILE = os.path.join(_DIR, "benchmark.jsonl")


def _default_output_path() -> str:
    """產生帶時間戳記的預設輸出路徑，例如 outputs/eval/results_20260318_143022.json"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(_DIR, "outputs", "eval", f"results_{ts}.json")


def run_chat_mode() -> None:
    """啟動 Streamlit chatbot（等同於 streamlit run app.py）。"""
    app_path = os.path.join(_DIR, "app.py")
    print("啟動 Chat 模式 ...")
    print(f"  執行：streamlit run {app_path}")
    subprocess.run(["streamlit", "run", app_path], check=True)


def run_benchmark_mode(benchmark_file: str, output_path: str) -> None:
    """執行 benchmark 測試模式：逐題評估並輸出結果。"""
    # 載入環境變數（需在 import config 前完成）
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_DIR, ".env"))

    import config

    # 確認知識庫已建立
    if not os.path.exists(config.DB_PATH):
        print(f"[ERROR] 知識庫不存在：{config.DB_PATH}")
        print("  請先執行：python ingest.py")
        sys.exit(1)

    # 確認 benchmark 檔案存在
    if not os.path.exists(benchmark_file):
        print(f"[ERROR] Benchmark 檔案不存在：{benchmark_file}")
        sys.exit(1)

    from evaluation.benchmark_loader import load_benchmark
    from evaluation.evaluator import run_benchmark
    from evaluation.export import export_results
    from evaluation.metrics import compute_summary

    print("=" * 60)
    print("Benchmark 測試模式")
    print(f"  題庫：{benchmark_file}")
    print(f"  輸出：{output_path}")
    print("=" * 60)

    # 1. 載入題庫
    questions = load_benchmark(benchmark_file)

    # 2. 逐題評估
    results = run_benchmark(questions)

    # 3. 計算 summary
    summary = compute_summary(results)

    # 4. 匯出結果
    export_results(results, summary, output_path)

    # 5. 印出 summary
    out_dir = os.path.dirname(output_path)
    base = os.path.splitext(output_path)[0]

    print("\n" + "=" * 60)
    print("Benchmark Summary")
    print("=" * 60)
    print(f"  題目數量            : {summary['total_questions']}")
    print(f"  Hit@5               : {summary['hit_at_5']:.1%}")
    print(f"  Recall@5            : {summary['recall_at_5']:.1%}")
    print(f"  Precision@5         : {summary['precision_at_5']:.1%}")
    print(f"  MRR                 : {summary['mrr']:.4f}")
    print(f"  Citation Accuracy   : {summary['citation_accuracy']:.1%}")
    if summary["avg_answer_score_manual"] is not None:
        print(f"  Avg Answer Score    : {summary['avg_answer_score_manual']:.2f} / 2")
    else:
        print(f"  Avg Answer Score    : （待人工評分，請填寫 CSV 中的 answer_score_manual 欄位）")
    print("=" * 60)
    print(f"\n輸出檔案：")
    print(f"  {base}.jsonl        （每題詳細結果）")
    print(f"  {os.path.join(out_dir, 'summary.json')}  （整體指標）")
    print(f"  {output_path}  （完整結果）")
    print(f"  {base}.csv          （人工評分用）")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="旅行不便險 RAG Chatbot — 統一入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例：
  python main.py --mode chat
  python main.py --mode benchmark
  python main.py --mode benchmark --benchmark-file benchmark.jsonl --output outputs/eval/results.json
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["chat", "benchmark"],
        required=True,
        help="執行模式：chat（啟動聊天介面）或 benchmark（執行評估測試）",
    )
    parser.add_argument(
        "--benchmark-file",
        default=DEFAULT_BENCHMARK_FILE,
        help=f"benchmark 題庫路徑（預設：benchmark.jsonl）",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="評估結果輸出路徑（預設：outputs/eval/results_<時間戳記>.json）",
    )

    args = parser.parse_args()

    if args.mode == "chat":
        run_chat_mode()
    elif args.mode == "benchmark":
        output = args.output if args.output else _default_output_path()
        run_benchmark_mode(args.benchmark_file, output)


if __name__ == "__main__":
    main()
