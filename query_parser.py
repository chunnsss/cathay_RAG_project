"""
query_parser.py — 問題理解模組
使用 LLM 將使用者問題解析為結構化 JSON，供後續檢索使用。
"""

import json
import config
from openai import OpenAI

_client = OpenAI(api_key=config.OPENAI_API_KEY)

_SYSTEM_PROMPT = """\
你是保險條款問答系統的問題分析器。
請將使用者問題解析為 JSON，格式如下：

{
  "intent": "coverage | exclusion | claim_document | general",
  "scenario_code": "baggage_loss | flight_delay | trip_cancellation | mobile_phone_theft | travel_document_loss | baggage_delay | trip_change | alternate_airport_landing | hijack | food_poisoning | cash_theft | credit_card_fraud | home_theft | rental_car_accident | special_event_cancellation | sports_event_cancellation | emergency_assistance | general",
  "entities": ["行動電話", "護照"]
}

規則：
- intent 判斷優先順序：
    exclusion     → 問「不理賠」、「不保事項」、「哪些情況不賠」、「除外」
    claim_document → 問「要準備哪些文件」、「需要什麼證明」、「申請文件」
                     ⚠️ 注意：「申請理賠」本身不是 claim_document，要看後面的問法
                     ⚠️ 「多久可以申請」、「申請條件」、「可以理賠嗎」→ coverage
    coverage      → 問「有沒有保障」、「承保範圍」、「多久才賠」、「理賠條件」、
                    「可以申請嗎」、「幾小時後」、「理賠金額」、「賠多少」
    general       → 其他或無法判斷
- scenario_code：優先對應問題主題，無法判斷填 "general"
- entities：抓出問題中的關鍵物件（可為空陣列）
- 只輸出合法 JSON，不要加任何說明文字
"""


def parse_query(question: str) -> dict:
    """
    解析使用者問題，回傳：
    {"intent": str, "scenario_code": str, "entities": list[str]}
    若 LLM 回傳格式有誤，回傳 fallback。
    """
    response = _client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    try:
        parsed = json.loads(raw)
        return {
            "intent": parsed.get("intent", "general"),
            "scenario_code": parsed.get("scenario_code", "general"),
            "entities": parsed.get("entities", []),
        }
    except (json.JSONDecodeError, AttributeError):
        return {"intent": "general", "scenario_code": "general", "entities": []}
