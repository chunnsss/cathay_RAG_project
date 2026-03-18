"""
rag_core.py — RAG V2 核心整合
流程：query_parser → retriever → answer_generator

ask(question) 回傳：
{
    "answer": str,
    "retrieved_articles": [int, ...],
    "retrieved_contexts": [str, ...],
    "parsed_query": {"intent": str, "scenario_code": str, "entities": list},
}
"""

from query_parser import parse_query
from retriever import retrieve
from answer_generator import generate_answer


def ask(question: str) -> dict:
    """端到端問答入口，供 app.py 與 evaluation 呼叫。"""

    # Step 1: 問題理解
    parsed = parse_query(question)

    # Step 2: 三段式檢索
    articles = retrieve(question, parsed)

    # Step 3: 生成回答
    answer = generate_answer(question, articles)

    return {
        "answer": answer,
        "retrieved_articles": [art["article_no"] for art in articles],
        "retrieved_contexts": [art["content"] for art in articles],
        "parsed_query": parsed,
    }
