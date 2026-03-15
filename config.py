"""全域設定檔 — 所有可調參數集中管理"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── OpenAI API ────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ─── 模型設定 ──────────────────────────────────────────
EMBEDDING_MODEL = "text-embedding-3-small"   # 向量嵌入模型
LLM_MODEL = "gpt-4o-mini"                    # 生成回答模型

# ─── 分塊設定 ──────────────────────────────────────────
# 用 ^ 匹配行首 + 條號後面接空格，避免誤切「因第三十九條第一項...」這種引用
CHUNK_PATTERN = r"^第[一二三四五六七八九十百零壹貳參肆伍陸柒捌玖拾\d]+條\s"
MAX_CHUNK_LENGTH = 500

# ─── 檢索設定 ──────────────────────────────────────────
TOP_K = 5

# ─── 資料庫設定 ─────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "knowledge.db")

# ─── PDF 來源 ──────────────────────────────────────────
PDF_PATH = os.path.join(os.path.dirname(__file__), "海外旅行不便險條款-2.pdf")
