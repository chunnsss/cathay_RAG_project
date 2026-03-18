"""
embedding.py — 向量化模組
使用 OpenAI text-embedding-3-small 對條文內容做 embedding
"""

import config
from openai import OpenAI

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


def embed_texts(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    """
    批量取得 embedding 向量。
    OpenAI API 單次上限約 2048 inputs，這裡以 batch_size 分批送出。
    """
    client = _get_client()
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i: i + batch_size]
        response = client.embeddings.create(
            model=config.EMBEDDING_MODEL,
            input=batch,
        )
        all_embeddings.extend(item.embedding for item in response.data)
        print(f"[OK] Embedding batch {i // batch_size + 1}：{len(batch)} 筆")

    print(f"[OK] Embedding 完成：共 {len(all_embeddings)} 個向量，維度 {len(all_embeddings[0])}")
    return all_embeddings
