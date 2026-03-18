"""
answer_generator.py — 回答生成模組
根據檢索到的條文與使用者問題，呼叫 LLM 產生結構化回答。
"""

import config
from openai import OpenAI

_client = OpenAI(api_key=config.OPENAI_API_KEY)

_SYSTEM_PROMPT = """\
你是一位資深保險條款顧問，請根據檢索到的條款內容生成「結構化、使用者導向」的回答。

⚠️ 回答不能只是條款摘要，必須轉換成「使用者容易理解的決策資訊」。

【核心規則】
1. 只能根據提供的條款內容回答，不得補充條款外的知識或常識
2. 不同條款必須「整合」，不能逐條翻譯
   ❌ 禁止：只說「依據第30條...」
   ✅ 必須：將承保範圍、不保事項、文件、流程整合為一份使用者說明
3. 若某物品在主題保險屬不保事項，但另有專屬保險條款，必須主動告知
4. 若條款不足以回答，直接說明「目前提供的條款中未包含相關資訊」
5. 語氣像客服說明，不是條文朗讀

【條款融合策略】
當檢索結果包含以下類型時，自動合併轉換：
- 承保範圍     → 整理為「重要條件」
- 特別不保事項 → 整理為「不理賠情況」
- 理賠文件     → 整合進「申請流程」
- 事故處理     → 整合進「申請流程」的步驟

【強制輸出格式】
每個區塊結尾都必須標註該區塊實際引用的條款編號，格式為（第X條）或（第X條、第Y條）。

👉 核心答案：
（1～2句直接回答問題）（第X條）

👉 重要條件：
- （從承保範圍整理，列出關鍵門檻，例如幾小時、哪些物品）
（第X條、第Y條）

👉 申請流程：
① Step 1：...
② Step 2：...
（第X條）
（若無申請流程相關條款，省略此區塊）

👉 不理賠情況：
- （整合不保事項，一定要有；若無相關條款則寫「條款未列明」）
- ⚠️ 格式要求：每點用 4～8 個字的「短語」概括，禁止直接複製條文原文
  ✅ 正確範例：不明原因遺失、未報警或未取得證明、正常耗損或破損、可由航空公司賠償的損失
  ❌ 禁止範例：物品因生銹、發霉、變色、自然形成或正常使用之耗損、蟲鼠破壞或固有瑕疵
（第X條、第Y條）

👉 條款依據：
第XX條、第XX條（完整列出本次回答所有引用條款）
"""


def _build_messages(question: str, articles: list[dict]) -> list[dict]:
    context_parts = []
    for art in articles:
        header = f"【第{art['article_no']}條 {art['article_title']}｜{art['clause_type']}｜{art['scenario_name']}】"
        context_parts.append(f"{header}\n{art['content']}")
    context = "\n\n---\n\n".join(context_parts)
    user_prompt = f"""\
請根據以下條款內容回答使用者問題。

===== 相關條款 =====
{context}

===== 使用者問題 =====
{question}
"""
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def generate_answer(question: str, articles: list[dict]) -> str:
    """
    根據條文清單與問題生成結構化回答。

    articles 中每筆需有：article_no, article_title, clause_type, scenario_name, content
    """
    messages = _build_messages(question, articles)
    response = _client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=messages,
        temperature=0.2,
    )
    return response.choices[0].message.content


def generate_answer_stream(question: str, articles: list[dict]):
    """Streaming 版本，供 app.py 的 st.write_stream() 使用。"""
    messages = _build_messages(question, articles)
    response = _client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=messages,
        temperature=0.2,
        stream=True,
    )
    for chunk in response:
        content = chunk.choices[0].delta.content
        if content:
            yield content
