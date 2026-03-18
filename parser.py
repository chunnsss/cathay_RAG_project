"""
parser.py — PDF 解析模組
將保險條款 PDF 解析為結構化的 Article 清單
"""

import re
import os
import pdfplumber

from schema import Article, detect_clause_type, detect_scenario

# ─── 文件 Metadata（依實際 PDF 修改）────────────────────────────────────────
DOC_META = {
    "insurer": "國泰產物",
    "product": "享樂遊海外旅行綜合保險",
    "document_type": "保險條款",
    "document_version": "112.06.27",
}

# ─── 章別 code mapping────────────────────────────────────────────────────────
CHAPTER_CODE_MAP: dict[str, str] = {
    "旅行不便": "travel_inconvenience",
    "醫療": "medical",
    "意外": "accident",
    "行李": "baggage",
    "班機": "flight",
    "旅程": "trip",
    "緊急": "emergency",
    "急難": "emergency",
    "責任": "liability",
    "定義": "definition",
    "一般": "general",
}

_CN_DIGITS = {"零":0,"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9}
_CN_UNITS  = {"十":10,"百":100,"千":1000}


def _cn_to_int(s: str) -> int:
    """中文數字字串轉整數，支援純阿拉伯數字與任意中文數字（十、百、千）"""
    if s.isdigit():
        return int(s)
    result, current = 0, 0
    for c in s:
        if c in _CN_DIGITS:
            current = _CN_DIGITS[c]
        elif c in _CN_UNITS:
            result += (current or 1) * _CN_UNITS[c]   # 「十」無前綴視為「一十」
            current = 0
    return result + current


def _chapter_code(title: str) -> str:
    for keyword, code in CHAPTER_CODE_MAP.items():
        if keyword in title:
            return code
    return "general"


def _extract_full_text(pdf_path: str) -> str:
    """提取 PDF 全文"""
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text.strip())
    return "\n".join(parts)


def _split_chapters(full_text: str) -> list[dict]:
    """
    找出所有「第X章 <標題>」段落，回傳：
    [{"no": int, "title": str, "text": str}, ...]
    """
    pattern = re.compile(
        r"第([一二三四五六七八九十]+)章\s*([^\n]+)", re.MULTILINE
    )
    matches = list(pattern.finditer(full_text))

    if not matches:
        return [{"no": 0, "title": "全文", "text": full_text}]

    chapters = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        chapters.append({
            "no": _cn_to_int(m.group(1)),
            "title": m.group(2).strip(),
            "text": full_text[start:end].strip(),
        })
    return chapters


def _split_articles(chapter_text: str) -> list[dict]:
    """
    在章節內找出所有「第X條 <標題>」，回傳：
    [{"no": int, "title": str, "content": str}, ...]
    """
    pattern = re.compile(
        r"^第(\d+|[一二三四五六七八九十百零壹貳參肆伍陸柒捌玖拾]+)條\s*([^\n]*)",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(chapter_text))

    if not matches:
        return []

    articles = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(chapter_text)
        raw = chapter_text[start:end].strip()
        articles.append({
            "no": _cn_to_int(m.group(1)),
            "title": m.group(2).strip(),
            "content": raw,
        })
    return articles


def parse_pdf(pdf_path: str) -> list[Article]:
    """主要解析函式：PDF → [Article]"""
    source_file = os.path.basename(pdf_path)
    full_text = _extract_full_text(pdf_path)
    chapters = _split_chapters(full_text)

    results: list[Article] = []

    for ch in chapters:
        chapter_no = ch["no"]
        chapter_title = ch["title"]
        chapter_code = _chapter_code(chapter_title)
        articles = _split_articles(ch["text"])

        # 若章節內沒有條文，整章當一筆
        if not articles:
            clause_type = detect_clause_type(ch["text"])
            scenario_code, scenario_name = detect_scenario(ch["text"])
            results.append(Article(
                **DOC_META,
                source_file=source_file,
                chapter_no=chapter_no,
                chapter_title=chapter_title,
                chapter_code=chapter_code,
                article_no=0,
                article_title=chapter_title,
                article_full_id=f"第{chapter_no}章",
                clause_type=clause_type,
                scenario_code=scenario_code,
                scenario_name=scenario_name,
                content=ch["text"],
            ))
            continue

        for art in articles:
            clause_type = detect_clause_type(art["title"] + art["content"])
            scenario_code, scenario_name = detect_scenario(art["title"])
            if scenario_code == "general":
                scenario_code, scenario_name = detect_scenario(art["content"])
            results.append(Article(
                **DOC_META,
                source_file=source_file,
                chapter_no=chapter_no,
                chapter_title=chapter_title,
                chapter_code=chapter_code,
                article_no=art["no"],
                article_title=art["title"],
                article_full_id=f"第{chapter_no}章-第{art['no']}條",
                clause_type=clause_type,
                scenario_code=scenario_code,
                scenario_name=scenario_name,
                content=art["content"],
            ))

    print(f"[OK] 解析完成：共 {len(results)} 條條文")
    return results
