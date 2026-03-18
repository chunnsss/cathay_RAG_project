"""
schema.py — 資料結構定義
每條保險條文的標準化格式
"""

from dataclasses import dataclass, asdict


# ─── Scenario Mapping（規則 mapping，不使用 LLM）─────────────────────────────
# ⚠️ 順序重要：較長 / 較具體的關鍵字必須排在較短 / 寬泛的關鍵字前面，
#    避免「行李」先命中「行動電話行李」這類文字，或「手機」先於「行動電話」。
#
# 匹配策略：先做精確短語匹配（長字優先），命中即停止。

# List of (keyword, scenario_code)，順序即優先級
_SCENARIO_RULES_ORDERED: list[tuple[str, str]] = [
    # ── 精確長詞優先 ──────────────────────────────────────────────────────────
    ("行動電話",          "mobile_phone_theft"),     # 比「行李」或「手機」更長
    ("手機",              "mobile_phone_theft"),     # 口語簡稱
    ("班機延誤",          "flight_delay"),           # 比「班機」長
    ("旅程取消",          "trip_cancellation"),
    ("旅程更改",          "trip_change"),
    ("行程更改",          "trip_change"),
    ("行程取消",          "trip_cancellation"),
    ("行李延誤",          "baggage_delay"),          # 比「行李」長且更具體
    ("行李遺失",          "baggage_loss"),           # 精確詞
    ("行李損失",          "baggage_loss"),
    ("行李",              "baggage_loss"),           # 兜底（比電話、延誤等短）
    ("護照",              "travel_document_loss"),
    ("旅行文件",          "travel_document_loss"),
    ("替代機場降落",      "alternate_airport_landing"),
    ("備降",              "alternate_airport_landing"),
    ("劫機",              "hijack"),
    ("食物中毒",          "food_poisoning"),
    ("現金被竊",          "cash_theft"),
    ("現金損失",          "cash_theft"),
    ("信用卡",            "credit_card_fraud"),
    ("住家竊盜",          "home_theft"),
    ("租車",              "rental_car_accident"),
    ("特殊事件取消",      "special_event_cancellation"),
    ("特殊活動",          "special_event_cancellation"),
    ("運動賽事取消",      "sports_event_cancellation"),
    ("運動賽事",          "sports_event_cancellation"),
    ("緊急救援",          "emergency_assistance"),
    ("緊急協助",          "emergency_assistance"),
]

# 供外部讀取的 dict（保留相容性）
SCENARIO_RULES: dict[str, str] = dict(_SCENARIO_RULES_ORDERED)

SCENARIO_NAMES: dict[str, str] = {
    "baggage_loss":                "行李遺失",
    "baggage_delay":               "行李延誤",
    "flight_delay":                "班機延誤",
    "trip_cancellation":           "旅程取消",
    "trip_change":                 "旅程更改",
    "mobile_phone_theft":          "行動電話被竊",
    "travel_document_loss":        "旅行文件遺失",
    "alternate_airport_landing":   "替代機場降落",
    "hijack":                      "劫機",
    "food_poisoning":              "食物中毒",
    "cash_theft":                  "現金被竊",
    "credit_card_fraud":           "信用卡盜刷",
    "home_theft":                  "住家竊盜",
    "rental_car_accident":         "租車事故",
    "special_event_cancellation":  "特殊事件取消",
    "sports_event_cancellation":   "運動賽事取消",
    "emergency_assistance":        "緊急救援協助",
    "general":                     "一般",
}


@dataclass
class Article:
    # 文件基本資訊
    insurer: str
    product: str
    document_type: str
    document_version: str
    source_file: str

    # 章節資訊
    chapter_no: int
    chapter_title: str
    chapter_code: str

    # 條文資訊
    article_no: int
    article_title: str
    article_full_id: str

    # 分類
    clause_type: str      # coverage / exclusion / claim_document / definition /
                          # claim_limit / claim_procedure / payment_rule / general_rule
    scenario_code: str
    scenario_name: str

    # 內容
    content: str

    def to_dict(self) -> dict:
        return asdict(self)


def detect_clause_type(text: str) -> str:
    """
    根據關鍵字判斷條款類型（rule-based，不使用 LLM）。
    順序：特定詞優先，general_rule 兜底。
    """
    if "承保範圍" in text:
        return "coverage"
    if "不保事項" in text:
        return "exclusion"
    if "最高賠償限額" in text:
        return "claim_limit"
    if "事故發生時之處理" in text or "通知" in text:
        return "claim_procedure"
    if "支付保險金之方式" in text or "計價" in text:
        return "payment_rule"
    if "文件" in text:
        return "claim_document"
    if "定義" in text:
        return "definition"
    return "general_rule"


def detect_scenario(text: str) -> tuple[str, str]:
    """
    根據有序關鍵字清單判斷情境（rule-based，不使用 LLM）。
    使用 _SCENARIO_RULES_ORDERED 確保長詞 / 精確詞優先命中。
    """
    for keyword, code in _SCENARIO_RULES_ORDERED:
        if keyword in text:
            return code, SCENARIO_NAMES[code]
    return "general", SCENARIO_NAMES["general"]
