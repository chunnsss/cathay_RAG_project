# 旅行不便險小幫手 — RAG V2

基於 RAG（Retrieval-Augmented Generation）架構的保險條款問答 Chatbot，專為「海外旅行不便險」設計。
使用者可用自然語言提問，系統自動檢索相關條款並整合為結構化、易懂的決策資訊。

> **面試一句話說明：** 這不是通用 RAG，是針對保險條款的知識結構與查詢特性，從資料前處理、檢索策略到回答格式全部客製化的領域導向問答系統。

---

## 問題背景與挑戰

保險條款的 RAG 比一般文件問答難，原因有三：

| 挑戰 | 說明 | 範例 |
|------|------|------|
| **語言落差** | 使用者口語 vs 條款法律文字 | 「手機被偷賠嗎？」vs「行動電話不負理賠責任」 |
| **跨條款整合** | 一個問題需要同時參考承保、不保、申請文件三種類型 | 行李遺失 → 第39條（承保）+ 第41條（不保）+ 第43條（文件）|
| **高混淆題** | 同一物件跨多個保險主題 | 手機放行李被偷 → 行李損失險 vs 行動電話被竊險 |

---

## V1 → V2 改善對比

| | V1 | V2 |
|--|--|--|
| 問題理解 | 無，直接 embedding | LLM 解析 intent / scenario / entities |
| 檢索方式 | 純 embedding search | 四段式檢索（metadata + embedding + entity + exclusion） |
| 高混淆題 | 錯誤（手機被偷 → 誤判為行李損失） | 正確（行李不保，主動提示第70條） |
| 不保事項 | 依賴 embedding，常常找不到 | Step D 強制補入，保證 LLM 看得到 |
| 回答格式 | 自由文字，資訊混雜 | 固定五段結構，多條條款整合為決策資訊 |
| 分類方式 | 無 | Rule-based（不呼叫 LLM，穩定低成本） |
| UI | 無 streaming | Streaming 回答 + 雙色條文 tag + 相關度過濾 |

---

## 系統架構

整個系統分為兩條 Pipeline：**離線資料處理（Ingest）** 與 **線上問答（Query）**。

### Pipeline 1：離線資料處理（執行一次，建立知識庫）

```
海外旅行不便險條款-2.pdf
    │
    ▼  parser.py
    │  ├─ pdfplumber 讀取 PDF 全文
    │  ├─ 正則偵測章節標題（第X章）→ 記錄 chapter_no / chapter_title
    │  └─ 正則切分條文（^第X條\s）→ 每條為一個 chunk
    │
    ▼  schema.py（rule-based 分類，不呼叫 LLM）
    │  ├─ detect_clause_type()  → 關鍵字判斷 clause_type（承保/不保/文件/程序...）
    │  └─ detect_scenario()     → 有序關鍵字 mapping → scenario_code（行李/延誤/手機...）
    │
    ▼  embedding.py
    │  └─ 組合輸入：article_title + clause_type + scenario_name + content
    │     → OpenAI text-embedding-3-small → 1536 維向量
    │
    ▼  db.py
       └─ 寫入 SQLite articles 資料表（含條文內容 + 向量 + metadata）
```

### Pipeline 2：線上問答（使用者每次提問）

```
使用者問題（自然語言）
    │
    ▼  query_parser.py（LLM，temperature=0）
    │  └─ 輸出：{ intent, scenario_code, entities }
    │     例：「行李裡的手機被偷算行李損失嗎？」
    │          → intent: coverage, scenario: baggage_loss, entities: ["行動電話"]
    │
    ▼  retriever.py — 四段式檢索
    │
    │  Step A：Metadata Filter
    │  └─ 依 scenario_code + clause_type 縮小候選集
    │     （若候選數 < TOP_K，自動放寬不限 scenario）
    │
    │  Step B：Embedding Search
    │  └─ 將問題向量化 → cosine similarity → Top-K=3 最相關條文
    │     （similarity < 0.3 → 視為無相關條款，不回傳）
    │
    │  Step C：Entity Expansion（跨主題補充）
    │  └─ 偵測 entities 中的關鍵物件（手機/護照/信用卡...）
    │     → 查 ENTITY_SCENARIO_MAP → 補撈對應主題 Top-3 條文
    │     （標記 is_expansion=True，UI 顯示藍色 ↗ tag）
    │
    │  Step D：強制補入 Exclusion 條文
    │  └─ scenario 已知時，直接補入該主題的不保事項條文（不依賴 embedding 排名）
    │     設計原因：不保事項語意上遠離「如何申請」類問題，embedding 排不進來
    │
    ▼  answer_generator.py（LLM，temperature=0.2）
    │  └─ System Prompt 要求：
    │     ・多條條款整合，禁止逐條翻譯
    │     ・輸出固定五段結構（核心答案 / 重要條件 / 申請流程 / 不理賠情況 / 條款依據）
    │     ・每段標注引用條款編號
    │
    ▼  app.py（Streamlit）
       └─ streaming 逐字輸出回答
          + 雙色條文 tag（深灰=主要 / 藍色=跨主題補充）
          + 折疊式檢索邏輯說明
```

---

## 模組說明

| 檔案 | 職責 |
|------|------|
| `schema.py` | `Article` 資料結構、`detect_clause_type()`、`detect_scenario()`（純 rule-based） |
| `parser.py` | pdfplumber 解析 PDF，辨識第X章 / 第X條，切分為條文清單 |
| `embedding.py` | OpenAI `text-embedding-3-small` 批次向量化 |
| `db.py` | SQLite `articles` 資料表建立與寫入 |
| `ingest.py` | 資料處理 Pipeline：PDF → parse → embed → SQLite |
| `query_parser.py` | LLM 解析問題 → `{intent, scenario_code, entities}` |
| `retriever.py` | 四段式檢索，回傳帶 `is_expansion` 標記的條文清單 |
| `answer_generator.py` | LLM 生成結構化回答（支援 streaming） |
| `rag_core.py` | 整合三者，`ask()` 供 app 與 evaluation 呼叫 |
| `app.py` | Streamlit 對話介面 |
| `config.py` | 全域設定（模型、路徑、閾值） |

---

## 資料設計

### Chunking 策略

保險條款具有天然的語意邊界，採用**條號切分**而非固定字數切分：

| 設計決策 | 說明 |
|---------|------|
| **切分單位** | 每「第X條」為一個 chunk，條文語意完整不跨切 |
| **切分方式** | 正則 `^第X條\s`（匹配行首 + 條號），避免誤切「依第三十九條第一項...」這類引用句 |
| **長度上限** | MAX_CHUNK_LENGTH = 500 字，超長條文截斷為子塊 |
| **為何不用固定字數** | 保險條款每條語意完整，固定字數會將承保範圍與不保事項切入同一塊，破壞語意邊界 |

> **遇到的問題：** 初期測試時發現固定字數切分會讓「行李損失保險承保範圍」與「行李損失保險特別不保事項」被切進同一個 chunk。這導致 embedding 無法區分兩種條款，LLM 收到的 context 混雜承保與不保內容，回答品質明顯下降。
>
> **解法：** 改用條號作為切分邊界，每條條文自成一個語意完整的 chunk，再搭配 `clause_type` metadata 標記類型，讓後續 retrieval 可以精準過濾。

### Metadata 設計

每筆條文儲存以下欄位，**用途各不相同**：

```json
{
  "article_no": 40,
  "article_title": "行李損失保險特別不保事項",
  "clause_type": "exclusion",
  "scenario_code": "baggage_loss",
  "scenario_name": "行李損失保險",
  "content": "..."
}
```

| 欄位 | 用途 |
|------|------|
| `clause_type` | Step A metadata filter：按條款類型（承保/不保/文件）縮小候選集 |
| `scenario_code` | Step A metadata filter：按保險主題（行李/延誤/手機竊盜）縮小候選集 |
| `scenario_name` | 組入 embedding 輸入，讓同主題條文在向量空間中更聚集 |
| `article_no` | 回答引用來源標注（第X條），UI 顯示條文 tag |
| `article_title` | 組入 embedding 輸入，提升語意明確性 |

**Metadata filter 的作用：** 若不先用 metadata 縮小範圍，embedding search 在全庫數百條條文中排序，容易被語意相近但主題無關的條文干擾。先過濾到同主題 10～20 條，再做 cosine similarity，準確率大幅提升。

### Embedding 輸入設計

embedding 不只對 `content` 做向量化，而是組合多個欄位：

```
{article_title} {clause_type} {scenario_name}
{content}
```

**原因：** 純條文內容語意過於相似（都是法律文字），加入 title、分類標籤後，同類型條文（如「不保事項」）在向量空間中更聚集，提升檢索精準度。

---

## 四段式檢索設計

### 流程說明

| 步驟 | 說明 | 設計原因 |
|------|------|----------|
| Step A | metadata filter（scenario + clause_type）| 大幅縮小候選集，避免無關條款干擾 embedding 排序 |
| Step B | embedding cosine similarity Top-K | 語意相似度排序，找最貼近問題的條文 |
| Step C | entity expansion（跨主題補充） | 解決高混淆題，偵測關鍵物件後補撈跨主題條文 |
| Step D | 強制補入 exclusion 條文 | 解決 semantic gap：不保事項語意遠，embedding 找不到 |

### Step A 的放寬邏輯

> **遇到的問題：** 部分問題的 scenario 偵測不夠精準（例如問題很籠統），導致 metadata filter 後候選集太少（< TOP_K），embedding search 無法正常排序。
>
> **解法：** 加入自動放寬機制——若 Step A 過濾後候選數不足，自動移除 scenario_code 限制，改為全庫搜尋。代價是搜尋範圍擴大，但保證不會因 metadata 誤判而讓使用者得不到任何回答。

### Step C 的設計動機

> **遇到的問題：** 「行李裡的手機被偷，算行李損失嗎？」這類問題，query_parser 正確判斷 `scenario = baggage_loss`，但正確答案需要同時引用行李損失險的**不保事項**（手機不賠）以及行動電話被竊險的**承保範圍**（可另外申請）。純靠 `baggage_loss` 主題的 embedding search，永遠找不到屬於 `mobile_phone_theft` 的第70條。
>
> **解法：** 在問題中偵測關鍵物件（entity），透過 `ENTITY_SCENARIO_MAP` 對應到跨主題的 scenario，主動補撈相關條文。這讓系統可以主動告知使用者「雖然這個情況不賠，但你可以從另一個險種申請」，而不是只給出「不理賠」的片面回答。

### Step D 的設計洞察

> **問題：** Embedding search 找的是「語意相近」的條文。「不保事項」在語意上不接近「如何申請理賠」，導致 embedding 排不到前幾名，LLM 看不到不保事項，回答出現「條款未列明」。
>
> **解法：** 當 scenario 已知時，強制把 exclusion 條文補進去，不依賴 embedding 排名，確保 LLM 永遠能看到完整的不賠情況。
>
> **這個 bug 是從測試中發現的**：「行李遺失如何申請理賠？」回答不理賠情況寫「條款未列明」，追查後發現 embedding 完全找不到第41條，原因就是語意距離太遠。

### 高混淆題解法

> 問：行李裡的手機被偷，算行李損失嗎？

| 步驟 | 結果 |
|------|------|
| query_parser | `scenario: baggage_loss`、`entities: ["行動電話"]` |
| Step B | 找到 baggage_loss 相關條文（含第40條不保事項） |
| Step C | `行動電話` → `mobile_phone_theft` → 補撈第70條承保範圍 |
| LLM | 正確回答：行動電話屬行李損失不保事項，可參考第70條行動電話被竊損失保險 |

---

## 關鍵設計決策：Rule-based vs LLM

> 條款分類（`clause_type`、`scenario_code`）**全部使用 rule-based 關鍵字判斷，不呼叫 LLM**。
>
> 原因：保險條款的分類規則明確（含「不保事項」→ exclusion，含「承保範圍」→ coverage），關鍵字即可穩定判斷，不需要 LLM 推理。用 LLM 只會增加延遲與 token 成本，且分類結果反而不穩定。

| 環節 | 方式 | 原因 |
|------|------|------|
| clause_type 分類 | Rule-based 關鍵字 | 規則明確，LLM 不必要 |
| scenario_code 分類 | Rule-based 有序 mapping | 長詞優先避免誤判（「行李延誤」先於「行李」）|
| 問題意圖解析 | LLM | 口語語意理解，rule 不足以處理 |
| 回答生成 | LLM | 多條款整合與語言轉換，需要推理能力 |

---

## Prompt Engineering 設計

回答生成使用兩層 prompt 策略：

### 1. 條款融合策略

強制 LLM 整合多種條款類型，而非逐條翻譯：

| 條款類型 | 轉換為 |
|---------|--------|
| 承保範圍 | 👉 重要條件（整理關鍵門檻） |
| 特別不保事項 | 👉 不理賠情況（短語格式） |
| 理賠文件 | 👉 整合進申請流程 Step |
| 事故處理 | 👉 整合進申請流程 Step |

### 2. 格式強制規則

- **禁止逐條翻譯**（`❌ 禁止：只說依據第30條... ✅ 必須：將多條整合`）
- **不理賠情況**：每點用 4～8 字短語概括，禁止複製條文原文
- **每個區塊標注條款來源**：`（第X條、第Y條）`
- **語氣像客服說明**，不是條文朗讀

---

## Streamlit UI 設計

### 功能說明

| 功能 | 說明 | 設計考量 |
|------|------|----------|
| **Streaming 回答** | 回答逐字出現 | 提升等待體驗，像 ChatGPT 的感受；spinner 只蓋住檢索階段 |
| **雙色條文 tag** | 主要條文深灰，跨主題補充藍色 + ↗ | 一眼看出哪些是 entity expansion 補充的條文 |
| **引用數量 badge** | `📎 引用條文（3 條，補充 2 條）` | 讓使用者了解回答依據的條文數量 |
| **檢索邏輯 expander** | 折疊式小字顯示意圖/主題/關鍵物件 | Demo 時可展開說明 pipeline，日常使用不干擾 |
| **MIN_SIMILARITY 過濾** | 相似度低於 0.3 不回傳條文 | 過濾「周杰倫是誰」等無關問題，不顯示假陽性條文 |
| **側欄推薦問題** | 9 個推薦問題，含高混淆題 | 面試 demo 可快速展示各種情境 |
| **清除對話按鈕** | 固定在側欄，無對話時 disabled | 不管捲動到哪都看得到，不需滾回頂部 |

### 推薦問題設計邏輯

```
一般查詢類     → 航班延誤多久可以申請理賠？
申請流程類     → 行李遺失後應該如何申請理賠？
不保事項類     → 哪些原因屬於不可理賠範圍？
高混淆題       → 行李裡的手機被偷，算行李損失嗎？  ← 展示 V2 最核心的改善
跨主題查詢     → 手機在海外被偷有保障嗎？
```

---

## 迭代除錯紀錄（面試談談 debug 過程）

這些是開發過程中發現並解決的實際問題，可在面試中說明：

| 問題 | 根因 | 解法 |
|------|------|------|
| `article_no` 全部為 0 | `_cn_to_int()` 只支援到「三十」，四十以上回傳 0 | 改用逐字解析演算法，支援任意中文數字 |
| 「航班延誤多久可以申請？」找不到條文 | LLM 將「申請」誤判為 `claim_document` intent | 細化 prompt 規則，明確說明「申請理賠條件」= `coverage` |
| 「如何申請理賠」不顯示不保事項 | `claim_document` intent 只撈 `claim_document` 條文 | 改為 `None`（不限 clause_type），同時加 Step D 強制補入 |
| 高混淆題回答錯誤 | `coverage` intent 過濾掉 exclusion 條文 | `coverage → None`，讓 embedding 自然排序 |
| 第70條（手機承保）未被補入 | entity expansion 只取 top 2，第70條排第3 | 擴大至 top 3 |

---

## 回答格式

```
👉 核心答案：（第X條）

👉 重要條件：
- ...
（第X條、第Y條）

👉 申請流程：
① Step 1：...
② Step 2：...
（第X條）

👉 不理賠情況：
- 不明原因遺失
- 未報警或未取得證明
（第X條、第Y條）

👉 條款依據：第XX條、第XX條
```

---

## Design Highlights

| 亮點 | 說明 |
|------|------|
| **Domain-aware retrieval** | 不是通用 RAG，針對保險條款結構設計四段式檢索 |
| **Semantic gap 解法** | Exclusion 條文語意距離遠，rule-based 強制補入而非依賴 embedding |
| **Cross-topic confusion 解法** | Entity extraction → 跨主題 expansion，解決高混淆題 |
| **Cost-conscious design** | 分類全用 rule-based，LLM 只用在必要兩個環節 |
| **使用者導向回答** | 多條條款整合為決策資訊，禁止逐條翻譯條文 |
| **UI 透明度設計** | 雙色 tag 顯示檢索來源，expander 展示解析邏輯 |

---

## 已知限制與未來優化方向

| 項目 | 說明 |
|------|------|
| 單一 PDF 來源 | 目前只支援一份條款 PDF；未來可擴展至多家保險公司比較 |
| 無對話記憶 | 每題獨立問答，不支援追問；可加入 conversation history |
| Evaluation 量化 | 有 benchmark 資料，可補齊自動評估指標（precision@K、answer accuracy）|
| 中文數字上限 | 目前支援到千位；超過千條的條款需再確認 |
| Reranker | 目前只用 cosine similarity；可加入 cross-encoder reranker 提升排序品質 |

---

## 快速開始

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

### 2. 設定 API Key

建立 `.env` 檔：

```
OPENAI_API_KEY=sk-xxxx
```

### 3. 建立知識庫（首次或 PDF 更新時執行）

```bash
python ingest.py
```

### 4. 啟動 Chatbot

```bash
streamlit run app.py
```

---

## 設定參數（config.py）

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding 模型 |
| `LLM_MODEL` | `gpt-4o-mini` | 問答生成模型（成本低、速度快） |
| `TOP_K` | `5` | embedding search 取前幾筆 |
| `MIN_SIMILARITY` | `0.3` | 低於此分數視為無相關條文（過濾不相關問題） |

---

## 專案結構

```
├── app.py                  # Streamlit 介面
├── rag_core.py             # 核心整合（供 app & evaluation 使用）
├── query_parser.py         # 問題理解
├── retriever.py            # 四段式檢索
├── answer_generator.py     # 回答生成（含 streaming）
├── ingest.py               # 資料處理 Pipeline
├── parser.py               # PDF 解析
├── embedding.py            # 向量化
├── db.py                   # SQLite 存取
├── schema.py               # 資料結構 & rule-based 分類
├── config.py               # 全域設定
├── data/
│   └── knowledge.db        # SQLite 知識庫
└── 海外旅行不便險條款-2.pdf
```
