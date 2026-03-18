"""
app.py — Streamlit Chatbot 介面

執行方式：streamlit run app.py
"""

import os
import streamlit as st

# 確保在 import config 前載入 .env
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import config
from query_parser import parse_query
from retriever import retrieve
from answer_generator import generate_answer_stream


# ─── 頁面設定 ──────────────────────────────────────────
st.set_page_config(
    page_title="旅行不便險小幫手",
    page_icon="✈️",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ─── 樣式 ─────────────────────────────────────────────
st.markdown("""
<style>
    /* 主要條文 tag（深灰） */
    .source-tag {
        display: inline-block;
        background-color: #2d3748;
        color: #e2e8f0;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.8em;
        margin: 2px 4px;
    }
    /* 跨主題補充 tag（藍綠） */
    .expansion-tag {
        display: inline-block;
        background-color: #2b6cb0;
        color: #ebf8ff;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.8em;
        margin: 2px 4px;
    }
    .welcome-box {
        background: #ffffff;
        color: #1a202c;
        padding: 2.2rem 2rem;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 1.5rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 16px rgba(0,0,0,0.07);
        border-top: 4px solid #87cb82;
    }
    .welcome-box h1 {
        font-size: 1.8rem;
        margin-bottom: 0.6rem;
        color: #1a202c;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    .welcome-box p {
        font-size: 0.97rem;
        color: #4a5568;
        line-height: 1.75;
    }
    /* 縮小 expander 標題字體並降低存在感 */
    details summary p {
        font-size: 0.78em !important;
        color: #a0aec0 !important;
    }
</style>
""", unsafe_allow_html=True)


# ─── 檢查資料庫是否存在且已建立 articles 資料表 ───────────
def _db_ready() -> bool:
    if not os.path.exists(config.DB_PATH):
        return False
    try:
        import sqlite3
        conn = sqlite3.connect(config.DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False

if not _db_ready():
    st.error("⚠️ 尚未建立知識庫（或資料表為空）！請先執行：`python ingest.py`")
    st.stop()


# ─── Session State 初始化 ──────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None
if "show_examples" not in st.session_state:
    st.session_state.show_examples = False

# ─── 側欄：固定工具列 ────────────────────────────────────
EXAMPLE_QUESTIONS = [
    "什麼情況下可以申請旅遊延誤賠償？",
    "行李遺失後應該如何申請理賠？",
    "哪些原因屬於不可理賠範圍？",
    "行李裡的手機被偷，算行李損失嗎？",
    "旅程取消可以申請哪些費用？",
    "手機在海外被偷有保障嗎？",
    "親友探視費用有理賠嗎？",
    "航班延誤多久可以申請理賠？",
    "信用卡在海外被盜刷怎麼辦？",
]

with st.sidebar:
    st.markdown("### 🛠️ 工具")
    has_messages = bool(st.session_state.messages)
    if st.button("🗑️ 清除對話", use_container_width=True, disabled=not has_messages):
        st.session_state.messages = []
        st.session_state.show_examples = False
        st.rerun()
    st.divider()
    st.markdown("**💡 推薦問題**")
    for q in EXAMPLE_QUESTIONS:
        if st.button(q, use_container_width=True, key=f"side_{q}"):
            st.session_state.pending_question = q
            st.rerun()


# ─── 歡迎介面（僅在對話為空時顯示）────────────────────────
if not st.session_state.messages:
    st.markdown("""
    <div class="welcome-box">
        <h1>✈️ 旅行不便險小幫手</h1>
        <p>您好！我是專為<strong>海外旅行不便險</strong>設計的條款問答助理。<br>
        無論是理賠條件、申請文件、不保事項，歡迎直接提問！</p>
    </div>
    """, unsafe_allow_html=True)

    st.caption("← 點選左側推薦問題快速開始，或直接在下方輸入問題")

else:
    st.markdown("### ✈️ 旅行不便險小幫手")


# ─── 顯示歷史對話 ──────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"], unsafe_allow_html=True)


# ─── 處理問題（來自輸入框或範例按鈕）─────────────────────
question = st.chat_input("請輸入您的問題，例如：航班延誤多久可以理賠？")

if st.session_state.pending_question:
    question = st.session_state.pending_question
    st.session_state.pending_question = None

if question:
    with st.chat_message("user"):
        st.markdown(question)
    st.session_state.messages.append({"role": "user", "content": question})

    with st.chat_message("assistant"):
        # Step 1 & 2：解析 + 檢索（spinner 僅蓋住這段）
        with st.spinner("🔍 正在檢索條款..."):
            parsed = parse_query(question)
            articles = retrieve(question, parsed)

        # Step 3：streaming 生成回答
        answer = st.write_stream(generate_answer_stream(question, articles))

        st.divider()

        # 有相關條文才顯示引用區塊
        valid_articles = [a for a in articles if a["article_no"] and a["article_no"] != 0]
        if valid_articles:
            main_count = sum(1 for a in valid_articles if not a.get("is_expansion"))
            exp_count  = sum(1 for a in valid_articles if a.get("is_expansion"))
            label = f"**📎 引用條文（{main_count} 條"
            label += f"，補充 {exp_count} 條）**" if exp_count else "）**"
            st.markdown(label)

            sources_html = ""
            for art in valid_articles:
                if art.get("is_expansion"):
                    sources_html += f'<span class="expansion-tag">第 {art["article_no"]} 條 ↗</span>'
                else:
                    sources_html += f'<span class="source-tag">第 {art["article_no"]} 條</span>'
            st.markdown(sources_html, unsafe_allow_html=True)

        # 檢索邏輯（小字折疊）
        with st.expander("檢索邏輯"):
            st.caption(
                f"意圖：{parsed.get('intent', '-')}　"
                f"主題：{parsed.get('scenario_code', '-')}　"
                f"關鍵物件：{', '.join(parsed.get('entities', [])) or '無'}"
            )

    article_refs = " | ".join(f'第{a["article_no"]}條' for a in articles if a.get("article_no"))
    full_response = answer + (f"\n\n---\n📎 {article_refs}" if article_refs else "")
    st.session_state.messages.append({"role": "assistant", "content": full_response})
