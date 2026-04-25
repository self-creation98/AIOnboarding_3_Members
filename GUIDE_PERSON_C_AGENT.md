# 🤖 Guide cho Person C — Agent/ML Developer

> Tài liệu hướng dẫn tích hợp AI Agent với Backend API (RAG, Chatbot, Sentiment, Content Gap, Copilot).

---

## 1. Setup Backend

### Cài đặt

```bash
# Tạo virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate
# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Cấu hình .env

```bash
cp .env.example .env
```

> [!IMPORTANT]
> Xin **3 giá trị Supabase** từ Person B (Tung) rồi paste vào file `.env`:
> ```env
> SUPABASE_URL=https://xxxxx.supabase.co
> SUPABASE_SERVICE_ROLE_KEY=eyJ...
> SUPABASE_JWT_SECRET=your-jwt-secret
> ```
> **KHÔNG tự tạo** Supabase project riêng — cả team dùng chung 1 database.

### Chạy backend

```bash
uvicorn src.backend.main:app --reload --port 8000
```

- Swagger UI: **http://localhost:8000/docs**
- Health check: `GET http://localhost:8000/api/health`

---

## 2. Nhiệm vụ của bạn

| # | Nhiệm vụ | Mô tả |
|---|----------|-------|
| 1 | **RAG Pipeline** | Ingestion (chunking → embedding → pgvector) + Retrieval (hybrid search) |
| 2 | **Agent (LangGraph)** | Context-aware chatbot, tool use, multi-step reasoning |
| 3 | **Sentiment Analysis** | Phân tích cảm xúc chat → log vào `sentiment_logs` |
| 4 | **Content Gap Detection** | Cluster câu hỏi chưa trả lời được → báo HR |
| 5 | **HR Copilot** | AI tóm tắt + đề xuất hành động cho HR |

---

## 3. Folder của bạn

Tạo code trong `src/agent/`:

```
src/agent/
├── core/
│   ├── config.py          # LLM config, embedding model
│   ├── llm.py             # Gemini/OpenAI wrapper
│   └── embedder.py        # Embedding function
├── rag/
│   ├── chunking.py        # Text → chunks
│   └── retriever.py       # Hybrid search (vector + keyword)
├── graph/
│   ├── nodes.py           # LangGraph nodes
│   ├── state.py           # Graph state
│   └── builder.py         # Build graph
├── tools/                 # Agent tools
├── prompts/               # System prompts
└── interface.py           # ★ Expose functions cho backend gọi
```

> [!CAUTION]
> **KHÔNG sửa files trong `src/backend/`** — nếu cần thay đổi API, nhắn Person B.

---

## 4. Integration Contract — Hàm cần implement

Backend sẽ import và gọi các hàm này. Tạo file `src/agent/interface.py`:

```python
# src/agent/interface.py

from src.backend.database import get_supabase


async def search(query: str, department: str = None, role: str = None) -> list[dict]:
    """
    Hybrid search: vector + keyword.

    Backend gọi khi: chatbot cần tìm thông tin.

    Input:
        query: câu hỏi người dùng
        department: filter theo phòng ban (optional)
        role: filter theo vị trí (optional)

    Output:
        [
            {
                "chunk_id": "uuid",
                "content": "Nội dung chunk...",
                "score": 0.85,
                "source_title": "Chính sách nghỉ phép",
                "source_id": "uuid"
            }
        ]
    """
    pass


async def chat(message: str, employee_id: str, conversation_id: str) -> dict:
    """
    Agent flow chính: intent → search → generate → sentiment.

    Backend gọi khi: user POST /api/chat

    Input:
        message: tin nhắn của NV
        employee_id: UUID NV (để lấy context: role, department, checklist...)
        conversation_id: UUID conversation (để multi-turn)

    Output:
        {
            "response": "Câu trả lời AI...",
            "sources": [
                {"title": "Chính sách nghỉ phép", "chunk_id": "uuid"}
            ],
            "confidence": 0.85,
            "intent": "policy_question"  # hoặc "checklist_help", "escalation"
        }
    """
    pass


async def detect_content_gaps() -> list[dict]:
    """
    Cluster unanswered_questions → identify missing knowledge.

    Backend gọi khi: HR xem GET /api/analytics/content-gaps

    Output:
        [
            {
                "topic": "bảo hiểm",
                "count": 5,
                "sample_questions": ["BHXH tính thế nào?", ...]
            }
        ]
    """
    pass


async def copilot_analyze(employee_id: str) -> dict:
    """
    AI summary + action suggestions cho HR.

    Backend gọi khi: HR click POST /api/analytics/copilot

    Output:
        {
            "summary": "NV Minh đang chậm 3 tasks IT...",
            "risk_factors": ["Chưa có email", "Quá hạn 5 ngày"],
            "suggestions": [
                {"action": "escalate_it", "reason": "Email chưa setup sau 5 ngày"},
                {"action": "schedule_checkin", "reason": "NV có dấu hiệu confused"}
            ]
        }
    """
    pass
```

---

## 5. Database — Bảng bạn cần dùng

### 5.1. Bảng để ĐỌC (Backend đã tạo sẵn)

| Table | Mô tả | Bạn dùng để... |
|-------|-------|----------------|
| `knowledge_documents` | Metadata docs (.md/.txt) đã upload | Lấy source cho citation |
| `knowledge_chunks` | Chunks + embeddings (pgvector) | Vector search |
| `chatbot_conversations` | Chat sessions | Context cho multi-turn |
| `chatbot_messages` | Message history | Lịch sử hội thoại |
| `employees` | Thông tin NV | Lấy context (role, department, checklist) |

### 5.2. Bảng để GHI (Bạn insert data vào)

| Table | Mô tả | Bạn ghi khi... |
|-------|-------|----------------|
| `knowledge_chunks` | Chunks + embeddings | Ingestion pipeline chạy |
| `sentiment_logs` | Phân tích cảm xúc | Sau mỗi message |
| `unanswered_questions` | Câu hỏi AI không trả lời được | Confidence < threshold |

### 5.3. Cách kết nối DB

```python
from src.backend.database import get_supabase

supabase = get_supabase()

# Ví dụ: query knowledge_chunks
result = supabase.table("knowledge_chunks").select("*").limit(10).execute()
chunks = result.data
```

---

## 6. Hướng dẫn chi tiết từng nhiệm vụ

### 6.1. RAG Pipeline — Ingestion

Upload docs qua API đã có → bạn cần xử lý chunking + embedding:

```python
# Sau khi document được upload qua POST /api/documents/upload
# Backend đã lưu metadata vào knowledge_documents
# Bạn cần: chunk nội dung → embed → insert vào knowledge_chunks

async def ingest_document(doc_id: str, content: str):
    """Chunk → Embed → Store."""
    supabase = get_supabase()

    # 1. Chunking (400 chars, overlap 50)
    chunks = chunk_text(content, chunk_size=400, overlap=50)

    # 2. Embed từng chunk
    for i, chunk in enumerate(chunks):
        embedding = await embed_text(chunk)  # vector(768)

        supabase.table("knowledge_chunks").insert({
            "document_id": doc_id,
            "content": chunk,
            "chunk_index": i,
            "embedding": embedding,  # list[float] 768 dimensions
            "source_title": "...",
        }).execute()
```

### 6.2. RAG Pipeline — Retrieval (Hybrid Search)

```sql
-- Bảng knowledge_chunks đã có cột:
--   embedding vector(768)     ← Gemini text-embedding-004
--   content_tsvector tsvector ← Full-text search tiếng Việt

-- Vector search (cosine similarity):
SELECT id, content, source_title,
       1 - (embedding <=> '[query_vector]') AS similarity
FROM knowledge_chunks
ORDER BY embedding <=> '[query_vector]'
LIMIT 10;

-- Keyword search (BM25):
SELECT id, content, source_title,
       ts_rank(content_tsvector, plainto_tsquery('vietnamese', 'nghỉ phép')) AS rank
FROM knowledge_chunks
WHERE content_tsvector @@ plainto_tsquery('vietnamese', 'nghỉ phép')
ORDER BY rank DESC
LIMIT 10;
```

> [!TIP]
> Hybrid search = chạy cả 2 query song song → combine bằng **Reciprocal Rank Fusion (RRF)**.
> Keyword search quan trọng cho exact terms: VPN, Jira, BHXH.

### 6.3. Sentiment Analysis

Sau mỗi message, phân tích sentiment rồi ghi vào DB:

```python
supabase.table("sentiment_logs").insert({
    "employee_id": employee_id,
    "conversation_id": conversation_id,
    "sentiment": "confused",  # positive | neutral | confused | frustrated | negative
    "confidence": 0.82,
    "topics": ["vpn", "jira"],
}).execute()
```

### 6.4. Content Gap — Log câu hỏi không trả lời được

Khi AI confidence < threshold → log để HR review:

```python
supabase.table("unanswered_questions").insert({
    "employee_id": employee_id,
    "question": message,
    "suggested_topic": "insurance_policy",
    "reviewed": False,
}).execute()
```

---

## 7. Backend API liên quan đến bạn

| Method | Path | Mô tả | Bạn cần làm gì |
|--------|------|-------|-----------------|
| POST | `/api/chat` | User gửi tin nhắn | Implement AI response logic |
| GET | `/api/chat/history/{emp_id}` | Lịch sử chat | Backend đã xong ✅ |
| POST | `/api/chat/feedback` | User đánh giá AI | Backend đã xong ✅ |
| POST | `/api/documents/upload` | Upload knowledge doc | Hook ingestion pipeline vào |
| GET | `/api/analytics/content-gaps` | Content gap list | Implement clustering logic |
| POST | `/api/analytics/copilot` | AI phân tích cho HR | Implement summary + suggestions |
| GET | `/api/analytics/chatbot-stats` | Thống kê chatbot | Backend đã xong ✅ |

> [!IMPORTANT]
> Mở **http://localhost:8000/docs** (Swagger UI) để xem chi tiết request/response schema của tất cả endpoints.

---

## 8. Checklist nhanh

- [ ] Setup xong, chạy `uvicorn` thành công
- [ ] Tạo `src/agent/interface.py` với 4 hàm stub
- [ ] Implement `search()` — hybrid vector + keyword
- [ ] Implement `chat()` — LangGraph agent flow
- [ ] Implement sentiment logging
- [ ] Implement content gap clustering
- [ ] Implement `copilot_analyze()`
- [ ] Test accuracy ≥ 80% trên 50 câu test
