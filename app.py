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
import rag_core


# ─── 頁面設定 ──────────────────────────────────────────
st.set_page_config(
    page_title="旅行不便險小幫手",
    page_icon="✈️",
    layout="centered",
)

# ─── 樣式 ─────────────────────────────────────────────
st.markdown("""
<style>
    .source-tag {
        display: inline-block;
        background-color: #2d3748;
        color: #e2e8f0;
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
</style>
""", unsafe_allow_html=True)


# ─── 檢查資料庫是否存在 ──────────────────────────────────
if not os.path.exists(config.DB_PATH):
    st.error("⚠️ 尚未建立知識庫！請先執行：`python ingest.py`")
    st.stop()


# ─── Session State 初始化 ──────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None


# ─── 歡迎介面（僅在對話為空時顯示）────────────────────────
if not st.session_state.messages:
    st.markdown("""
    <div class="welcome-box">
        <h1>✈️ 旅行不便險小幫手</h1>
        <p>您好！我是專為<strong>海外旅行不便險</strong>設計的條款問答助理。<br>
        無論是理賠條件、申請文件、不保事項，歡迎直接提問！</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**常見問題，點擊即可發問：**")

    EXAMPLE_QUESTIONS = [
        "航班延誤多久可以申請理賠？",
        "行李遺失要準備哪些文件？",
        "信用卡在海外被盜刷怎麼辦？",
        "旅程取消可以申請哪些費用？",
        "手機在海外被偷有保障嗎？",
        "親友探視費用有理賠嗎？",
    ]

    cols = st.columns(2)
    for i, q in enumerate(EXAMPLE_QUESTIONS):
        if cols[i % 2].button(q, use_container_width=True):
            st.session_state.pending_question = q
            st.rerun()

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
        with st.spinner("🔍 正在檢索條款並生成回答..."):
            result = rag_core.ask(question)

        st.markdown(result["answer"])

        st.divider()
        st.markdown("**📎 引用來源：**")
        sources_html = ""
        for src in result["sources"]:
            sources_html += (
                f'<span class="source-tag">'
                f'{src["article_no"]} (P.{src["page"]}) '
                f'相似度: {src["score"]:.2%}'
                f'</span>'
            )
        st.markdown(sources_html, unsafe_allow_html=True)

    full_response = result["answer"] + "\n\n---\n📎 " + " | ".join(
        f'{s["article_no"]} P.{s["page"]}' for s in result["sources"]
    )
    st.session_state.messages.append({"role": "assistant", "content": full_response})
