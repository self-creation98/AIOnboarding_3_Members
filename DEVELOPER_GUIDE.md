# 🚀 Developer Guide — AI Onboarding Backend

> Tài liệu cho **Person A (Frontend)** và **Person C (Agent/ML)** sử dụng backend API.

---

## Mục lục

1. [Setup & Chạy Backend](#1-setup--chạy-backend)
2. [Kiến trúc Backend đã build](#2-kiến-trúc-backend-đã-build)
3. [Full API Reference (65 endpoints)](#3-full-api-reference-65-endpoints)
4. [Hướng dẫn cho Person A — Frontend](#4-hướng-dẫn-cho-person-a--frontend)
5. [Hướng dẫn cho Person C — Agent/ML](#5-hướng-dẫn-cho-person-c--agentmi)
6. [Database Schema](#6-database-schema)
7. [Authentication Guide](#7-authentication-guide)

---

## 1. Setup & Chạy Backend

### Prerequisites

- Python 3.12+
- Supabase project (URL + Service Role Key)

### Cài đặt

```bash
# Clone repo
git clone <repo-url>
cd A20-App-090

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
# Copy env template
cp .env.example .env
```

Sửa file `.env` — hướng dẫn lấy từng giá trị bên dưới.

---

### 🔑 Hướng dẫn lấy Supabase Credentials

> [!IMPORTANT]
> Cả 3 người dùng **CHUNG 1 Supabase project**. Person B (backend) sẽ gửi credentials cho cả team.
> **KHÔNG TỰ TẠO** project Supabase riêng — vì cần chung database.

#### Cách 1: Nhận từ Person B (Nhanh nhất)

Person B gửi cho bạn 3 giá trị này (qua Zalo/Slack/Discord riêng, **KHÔNG commit vào git**):

```env
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=your-jwt-secret-here
```

Paste vào file `.env`, xong.

#### Cách 2: Tự lấy từ Supabase Dashboard (nếu có quyền truy cập)

Person B cần **mời bạn vào Supabase Organization** trước:
- Supabase Dashboard → **Organization Settings** → **Members** → **Invite** → nhập email

Sau khi được mời, bạn tự lấy:

**Bước 1 — `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`:**
```
Supabase Dashboard
  → Chọn project "A20-App-090" (hoặc tên tương tự)
  → Sidebar trái: Settings (⚙️)
  → API
  → Mục "Project URL":     ← copy → SUPABASE_URL
  → Mục "Project API Keys":
     - anon (public) key    ← KHÔNG dùng cái này
     - service_role key     ← copy → SUPABASE_SERVICE_ROLE_KEY
```

> [!WARNING]
> **service_role key** có quyền bypass RLS (Row Level Security). 
> Chỉ dùng ở backend, **TUYỆT ĐỐI KHÔNG** đưa vào frontend code.

**Bước 2 — `SUPABASE_JWT_SECRET`:**
```
Supabase Dashboard
  → Settings (⚙️)
  → API
  → Kéo xuống mục "JWT Settings"
  → JWT Secret              ← copy → SUPABASE_JWT_SECRET
```

#### File `.env` hoàn chỉnh

```env
# ══════════════════════════════════════════════
# BẮT BUỘC — Supabase (lấy theo hướng dẫn trên)
# ══════════════════════════════════════════════
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret

# ══════════════════════════════════════════════
# OPTIONAL — Không cần thay đổi khi dev
# ══════════════════════════════════════════════

# Email service (mặc định: console — in email ra terminal)
EMAIL_PROVIDER=console

# URLs (mặc định ok cho localhost)
FRONTEND_BASE_URL=http://localhost:3000
BACKEND_BASE_URL=http://localhost:8000

# AI logging (giữ nguyên)
AI_LOG_SERVER=https://ai-logs.note.transformerlabs.ai/api/ingest
AI_LOG_API_KEY=lMfm8NPzHVHlOtYx2kOQ7c9PTxJOB0E3DJbD_UBlsFw
```

#### Kiểm tra credentials đúng chưa

```bash
# Chạy server
uvicorn src.backend.main:app --reload --port 8000

# Test health (không cần auth)
curl http://localhost:8000/api/health
# Kết quả mong đợi: {"status":"ok"}

# Nếu lỗi "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
# → Kiểm tra lại file .env, đảm bảo không có dấu cách thừa
```

#### Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách sửa |
|-----|-------------|----------|
| `SUPABASE_URL must be set` | Chưa tạo file `.env` | `cp .env.example .env` rồi điền credentials |
| `Invalid API key` | Sai `SUPABASE_SERVICE_ROLE_KEY` | Copy lại từ Dashboard → Settings → API |
| `relation "employees" does not exist` | Chưa tạo bảng trong DB | Chạy SQL schema trong Supabase → SQL Editor |
| `Token không hợp lệ` | Sai `SUPABASE_JWT_SECRET` | Copy lại từ Dashboard → Settings → API → JWT Settings |
| `FetchError: request to https://xxx.supabase.co failed` | Sai URL hoặc mất internet | Kiểm tra `SUPABASE_URL` — phải bắt đầu bằng `https://` |

---

### Chạy server

```bash
uvicorn src.backend.main:app --reload --port 8000
```

### Kiểm tra hoạt động

- Health check: `GET http://localhost:8000/api/health`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

> [!TIP]
> Swagger UI tại `/docs` có nút **Authorize** — nhập JWT token để test các endpoint cần auth.

---

## 2. Kiến trúc Backend đã build

```
src/backend/
├── main.py                       # FastAPI app, router registration, CORS
├── database.py                   # Supabase client singleton
├── schemas.py                    # Shared Pydantic models (UserInfo, LoginRequest...)
│
├── api/                          # 15 router files = 65 endpoints
│   ├── auth.py                   # Login, /me
│   ├── employees.py              # CRUD nhân viên
│   ├── checklist.py              # Generate/approve/complete checklist
│   ├── stakeholder.py            # Multi-stakeholder task management
│   ├── task_confirm.py           # ★ Magic link confirm (PUBLIC, no auth)
│   ├── preboarding.py            # Document upload/download/verify
│   ├── documents.py              # Knowledge base CRUD
│   ├── chat.py                   # Chatbot (calls Agent)
│   ├── analytics.py              # Dashboard, health, copilot
│   ├── actions.py                # HR action buttons
│   ├── reminders.py              # Reminder system trigger
│   ├── webhooks.py               # Incoming webhooks (HRIS, IT, LMS)
│   ├── webhook_configs.py        # Outgoing webhook management
│   └── deps.py                   # Auth dependencies
│
├── services/                     # Business logic services
│   ├── reminder.py               # 3-tier escalation logic
│   ├── event_dispatcher.py       # Outgoing webhook sender (HMAC + retry)
│   ├── email_service.py          # Email sender (Resend/console)
│   ├── magic_link.py             # JWT token for stakeholder confirm
│   └── stakeholder_notifier.py   # Email orchestrator
```

### Đặc điểm quan trọng

| Tính năng | Trạng thái |
|-----------|-----------|
| Auth (JWT via Supabase) | ✅ Production-ready |
| CRUD Employees | ✅ Full CRUD |
| 3-Layer Checklist Engine | ✅ HR Template + Role-Specific + AI (stub) |
| Multi-Stakeholder Tasks | ✅ IT/Admin/Manager routing |
| Magic Link (stakeholder confirm) | ✅ No-login confirm via email |
| Preboarding Documents | ✅ Upload/Download (Supabase Storage) |
| Webhook In (HRIS/IT/LMS) | ✅ 4 endpoints |
| Webhook Out (Event Dispatcher) | ✅ HMAC + retry |
| 3-Tier Reminder Escalation | ✅ Employee → Manager → HR |
| Health Score Recalculation | ✅ Auto red/yellow/green |
| Bottleneck Analytics | ✅ Top stuck tasks |
| Content Gap Detection | ⚠️ API ready, cần Person C implement logic |
| HR Copilot (AI Summary) | ⚠️ API ready, cần Person C implement AI |
| Chat/RAG | ⚠️ API ready, cần Person C implement RAG pipeline |

---

## 3. Full API Reference (65 endpoints)

### 🔐 Auth

| Method | Path | Auth | Mô tả |
|--------|------|------|-------|
| POST | `/api/auth/login` | ❌ | Đăng nhập, trả JWT token |
| GET | `/api/auth/me` | ✅ | Thông tin user hiện tại |

### 👤 Employees

| Method | Path | Auth | Mô tả |
|--------|------|------|-------|
| POST | `/api/employees` | ✅ | Tạo nhân viên mới |
| GET | `/api/employees` | ✅ | Danh sách NV (filter: status, department) |
| GET | `/api/employees/{id}` | ✅ | Chi tiết 1 NV |
| PATCH | `/api/employees/{id}` | ✅ | Cập nhật thông tin NV |
| DELETE | `/api/employees/{id}` | ✅ | Xóa NV |
| GET | `/api/employees/{id}/checklist` | ✅ | Checklist theo NV |

### ✅ Checklist

| Method | Path | Auth | Mô tả |
|--------|------|------|-------|
| POST | `/api/checklist/generate` | ✅ | Tạo checklist (3-layer) |
| GET | `/api/checklist/{plan_id}` | ✅ | Chi tiết plan + items |
| POST | `/api/checklist/{plan_id}/approve` | ✅ | Duyệt plan → tạo stakeholder tasks → **gửi email** |
| PATCH | `/api/checklist/items/{item_id}/complete` | ✅ | Hoàn thành 1 item |
| DELETE | `/api/checklist/{plan_id}` | ✅ | Xóa plan |

### 👥 Stakeholder Tasks

| Method | Path | Auth | Mô tả |
|--------|------|------|-------|
| GET | `/api/stakeholder-tasks` | ✅ | List tasks (filter: team, status) |
| GET | `/api/stakeholder-tasks/summary` | ✅ | Summary theo team |
| GET | `/api/stakeholder-tasks/{id}` | ✅ | Chi tiết 1 task |
| PATCH | `/api/stakeholder-tasks/{id}/complete` | ✅ | Complete task (internal) |

### 🔗 Magic Link Confirm (PUBLIC — không cần auth!)

| Method | Path | Auth | Mô tả |
|--------|------|------|-------|
| GET | `/api/tasks/confirm/{token}` | ❌ | Xem tasks từ magic link (JSON) |
| POST | `/api/tasks/confirm/{token}` | ❌ | Xác nhận hoàn thành tasks |
| GET | `/api/tasks/confirm-page/{token}` | ❌ | **HTML page** tự chứa (có form confirm) |

### 📄 Preboarding Documents

| Method | Path | Auth | Mô tả |
|--------|------|------|-------|
| GET | `/api/preboarding/overview` | ✅ | Tổng quan tất cả NV |
| GET | `/api/preboarding/{emp_id}` | ✅ | Documents theo NV |
| POST | `/api/preboarding/{emp_id}/upload` | ✅ | Upload file (Supabase Storage) |
| GET | `/api/preboarding/{emp_id}/download/{doc_id}` | ✅ | Download (signed URL) |
| POST | `/api/preboarding/{emp_id}/verify/{doc_id}` | ✅ | HR xác nhận hợp lệ |
| POST | `/api/preboarding/{emp_id}/reject/{doc_id}` | ✅ | HR từ chối |

### 📚 Knowledge Documents

| Method | Path | Auth | Mô tả |
|--------|------|------|-------|
| POST | `/api/documents/upload` | ✅ | Upload .md/.txt → chunking |
| GET | `/api/documents` | ✅ | List documents |
| GET | `/api/documents/{id}` | ✅ | Chi tiết document |
| DELETE | `/api/documents/{id}` | ✅ | Xóa document + chunks |

### 💬 Chat (Person C cần implement AI)

| Method | Path | Auth | Mô tả |
|--------|------|------|-------|
| POST | `/api/chat` | ✅ | Gửi message → AI trả lời |
| GET | `/api/chat/history/{emp_id}` | ✅ | Lịch sử chat |
| POST | `/api/chat/feedback` | ✅ | Feedback cho AI response |

### 📊 Analytics

| Method | Path | Auth | Mô tả |
|--------|------|------|-------|
| GET | `/api/analytics/overview` | ✅ | Dashboard tổng quan |
| GET | `/api/analytics/employee/{id}` | ✅ | Analytics cá nhân |
| GET | `/api/analytics/bottlenecks` | ✅ | Top stuck tasks |
| GET | `/api/analytics/content-gaps` | ✅ | Câu hỏi chưa trả lời được |
| GET | `/api/analytics/chatbot-stats` | ✅ | Thống kê chatbot |
| POST | `/api/analytics/copilot` | ✅ | AI phân tích + đề xuất (Person C) |
| POST | `/api/analytics/recalculate-health` | ✅ | Tính lại health score |

### ⚡ Actions

| Method | Path | Auth | Mô tả |
|--------|------|------|-------|
| POST | `/api/actions/send-reminder` | ✅ | Gửi reminder thủ công |
| POST | `/api/actions/schedule-checkin` | ✅ | Lên lịch check-in |
| POST | `/api/actions/assign-buddy` | ✅ | Assign buddy cho NV |
| POST | `/api/actions/escalate-it` | ✅ | Tạo IT ticket |
| GET | `/api/actions/history` | ✅ | Lịch sử actions |

### ⏰ Reminders

| Method | Path | Auth | Mô tả |
|--------|------|------|-------|
| POST | `/api/reminders/run` | ✅ | Chạy reminder engine |
| GET | `/api/reminders/logs` | ✅ | Lịch sử reminders |
| GET | `/api/reminders/stats` | ✅ | Thống kê |

### 🔔 Webhooks (Incoming)

| Method | Path | Auth | Mô tả |
|--------|------|------|-------|
| POST | `/api/webhooks/hris/new-employee` | ❌ | HRIS tạo NV mới (full auto flow) |
| POST | `/api/webhooks/hris/employee-updated` | ❌ | HRIS cập nhật NV |
| POST | `/api/webhooks/it/ticket-resolved` | ❌ | IT hoàn thành ticket |
| POST | `/api/webhooks/lms/course-completed` | ❌ | LMS báo hoàn thành khóa học |
| POST | `/api/webhooks/documents/submitted` | ❌ | Doc portal báo upload |

### ⚙️ Webhook Configs (Outgoing)

| Method | Path | Auth | Mô tả |
|--------|------|------|-------|
| POST | `/api/webhook-configs` | ✅ | Đăng ký webhook URL |
| GET | `/api/webhook-configs` | ✅ | List configs |
| GET | `/api/webhook-configs/{id}` | ✅ | Detail + stats |
| PATCH | `/api/webhook-configs/{id}` | ✅ | Update |
| DELETE | `/api/webhook-configs/{id}` | ✅ | Delete |
| POST | `/api/webhook-configs/{id}/test` | ✅ | Test gửi payload |

---

## 4. Hướng dẫn cho Person A — Frontend

### Nhiệm vụ chính

1. **HR Dashboard** — Overview, employee list, bottleneck alerts, content gaps
2. **Mock Control Panel** — Trigger webhooks (tạo NV, IT resolve, LMS complete)
3. **Preboarding Portal** — Upload/verify giấy tờ
4. **Employee Checklist View** — NV xem tiến độ onboarding

### Kết nối API

```typescript
// api/client.ts
const API_BASE = "http://localhost:8000";

// Login → lấy token
const login = async (email: string, password: string) => {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return res.json(); // { access_token, user, expires_at }
};

// Gọi API có auth
const apiCall = async (path: string, options: RequestInit = {}) => {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
  return res.json(); // { success: true, data: ... } hoặc { success: false, error: "..." }
};
```

### Response format chuẩn

**Tất cả** endpoints trả về format nhất quán:

```json
// Success
{ "success": true, "data": { ... } }

// Error
{ "success": false, "error": "Mô tả lỗi" }
```

### Key Pages & API mapping

| Page | Endpoints cần gọi |
|------|-------------------|
| **Dashboard Overview** | `GET /api/analytics/overview` |
| **Employee List** | `GET /api/employees?status=in_progress` |
| **Employee Detail** | `GET /api/employees/{id}` + `GET /api/analytics/employee/{id}` |
| **Checklist View** | `GET /api/employees/{id}/checklist` |
| **Bottleneck Tab** | `GET /api/analytics/bottlenecks` |
| **Content Gaps** | `GET /api/analytics/content-gaps` |
| **Preboarding** | `GET /api/preboarding/{id}` + `POST .../upload` |
| **Stakeholder Tasks** | `GET /api/stakeholder-tasks?team=it` |
| **HR Copilot** | `POST /api/analytics/copilot` body: `{"employee_id": "..."}` |

### Mock Control Panel — Webhook triggers

```typescript
// Nút "HRIS: Tạo NV mới"
await fetch(`${API_BASE}/api/webhooks/hris/new-employee`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    full_name: "Nguyễn Văn An",
    email: "an.nguyen@company.com",
    role: "Software Engineer",
    department: "Engineering",
    start_date: "2026-05-20",
    seniority_level: "junior",
    location: "HCM",
  }),
});

// Nút "IT: Resolve Ticket"
await fetch(`${API_BASE}/api/webhooks/it/ticket-resolved`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    ticket_id: "IT-1234",
    employee_id: "uuid-here",
    task_type: "email_setup",
    resolved_by: "it_admin@company.com",
  }),
});

// Nút "LMS: Course Done"
await fetch(`${API_BASE}/api/webhooks/lms/course-completed`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    employee_id: "uuid-here",
    course_id: "SEC-101",
    course_name: "Security Awareness Training",
    score: 85,
    completed_at: "2026-05-20T14:30:00Z",
  }),
});
```

### CORS

Backend đã cấu hình CORS cho `localhost:3000`. Nếu frontend chạy port khác, báo cho Person B (mình) sửa trong `main.py`.

---

## 5. Hướng dẫn cho Person C — Agent/ML

### Nhiệm vụ chính

1. **RAG Pipeline** — Ingestion (chunking → embedding → pgvector) + Retrieval (hybrid search)
2. **Agent (LangGraph)** — Context-aware chatbot, tool use, multi-step reasoning
3. **Sentiment Analysis** — Phân tích cảm xúc chat → log vào `sentiment_logs`
4. **Content Gap Detection** — Cluster câu hỏi chưa trả lời được → báo HR
5. **HR Copilot** — AI tóm tắt + đề xuất hành động

### Integration Points — Backend đã sẵn sàng

#### 5.1. Chat endpoint — `POST /api/chat`

Backend đã có endpoint, Person C cần implement logic AI:

```python
# Trong src/backend/api/chat.py — function cần Person C sửa:
# _call_agent(message, employee_id, conversation_id) → AI response

# Input: message (str), employee context
# Output cần trả: {
#   "response": "Câu trả lời AI...",
#   "sources": [{"title": "...", "chunk_id": "..."}],
#   "confidence": 0.85,
#   "intent": "policy_question"  # hoặc "checklist_help", "escalation"
# }
```

#### 5.2. Bảng dữ liệu sẵn sàng cho Person C

| Table | Mô tả | Person C dùng để... |
|-------|-------|---------------------|
| `knowledge_documents` | Metadata docs đã upload | Lấy source cho citation |
| `knowledge_chunks` | Chunks + embeddings (pgvector) | Vector search |
| `chatbot_conversations` | Conversation sessions | Context cho multi-turn |
| `chatbot_messages` | Message history | RAG retrieval context |
| `sentiment_logs` | Sentiment per message | Ghi kết quả phân tích |
| `unanswered_questions` | Câu hỏi AI không trả lời được | Content gap input |

#### 5.3. Hàm cần implement

```python
# File: src/agent/interface.py (Person C tạo file này)

async def search(query: str, department: str = None, role: str = None) -> list[dict]:
    """
    Hybrid search: vector + keyword
    Returns: [{"chunk_id": "...", "content": "...", "score": 0.85, "source_title": "..."}]
    """
    pass

async def chat(message: str, employee_id: str, conversation_id: str) -> dict:
    """
    Agent flow: intent → search → generate → sentiment
    Returns: {"response": "...", "sources": [...], "confidence": 0.8}
    """
    pass

async def detect_content_gaps() -> list[dict]:
    """
    Cluster unanswered_questions → identify missing knowledge
    Returns: [{"topic": "bảo hiểm", "count": 5, "sample_questions": [...]}]
    """
    pass

async def copilot_analyze(employee_id: str) -> dict:
    """
    AI summary + action suggestions for HR
    Returns: {"summary": "...", "risk_factors": [...], "suggestions": [...]}
    """
    pass
```

#### 5.4. Cách ghi sentiment

```python
# Sau khi phân tích sentiment, insert vào DB:
supabase.table("sentiment_logs").insert({
    "employee_id": employee_id,
    "conversation_id": conversation_id,
    "sentiment": "confused",  # positive|neutral|confused|frustrated|negative
    "confidence": 0.82,
    "topics": ["vpn", "jira"],
}).execute()
```

#### 5.5. Cách log câu hỏi không trả lời được

```python
# Khi confidence < threshold:
supabase.table("unanswered_questions").insert({
    "employee_id": employee_id,
    "question": message,
    "suggested_topic": "insurance_policy",
    "reviewed": False,
}).execute()
```

#### 5.6. Embedding & Vector Search

```sql
-- Bảng knowledge_chunks đã có cột:
--   embedding vector(768)     ← Gemini text-embedding-004
--   content_tsvector tsvector ← Full-text search

-- Vector search (pgvector):
SELECT id, content, source_title,
       1 - (embedding <=> '[query_vector]') AS similarity
FROM knowledge_chunks
WHERE department_tags @> ARRAY['engineering']
ORDER BY embedding <=> '[query_vector]'
LIMIT 10;

-- Keyword search (tsvector):
SELECT id, content, source_title,
       ts_rank(content_tsvector, plainto_tsquery('vietnamese', 'nghỉ phép')) AS rank
FROM knowledge_chunks
WHERE content_tsvector @@ plainto_tsquery('vietnamese', 'nghỉ phép')
ORDER BY rank DESC
LIMIT 10;
```

---

## 6. Database Schema

### Bảng chính

| Table | Owner | Rows mẫu |
|-------|-------|-----------|
| `employees` | Person B | Thông tin NV + health_score + onboarding_status |
| `onboarding_plans` | Person B | Plan per NV, status: cho_duyet → da_duyet → hoan_thanh |
| `checklist_items` | Person B | Tasks in plan, status: chua_bat_dau → dang_lam → hoan_thanh |
| `stakeholder_tasks` | Person B | IT/Admin/Manager tasks, linked to checklist_items |
| `preboarding_documents` | Person B | Giấy tờ NV (CMND, bằng cấp...) |
| `knowledge_documents` | Person B+C | Metadata docs (.md/.txt) |
| `knowledge_chunks` | Person C | Chunks + embeddings |
| `chatbot_conversations` | Person B+C | Chat sessions |
| `chatbot_messages` | Person B+C | Messages + AI responses |
| `sentiment_logs` | Person C | Phân tích cảm xúc |
| `unanswered_questions` | Person C | Câu hỏi chưa trả lời |
| `reminder_logs` | Person B | Lịch sử gửi reminder |
| `webhook_configs` | Person B | Outgoing webhook URLs |
| `webhook_logs` | Person B | Audit log in/out webhooks |

### Key relationships

```
employees ─┬─ onboarding_plans ── checklist_items
            ├─ stakeholder_tasks (via plan)
            ├─ preboarding_documents
            ├─ chatbot_conversations ── chatbot_messages
            └─ sentiment_logs
```

---

## 7. Authentication Guide

### Flow

```
1. POST /api/auth/login { email, password }
   → Supabase Auth verify
   → Return { access_token, user: UserInfo }

2. Gọi API: Header "Authorization: Bearer <access_token>"
   → deps.py verify token via Supabase
   → Inject UserInfo vào endpoint
```

### Test accounts

Tạo test accounts trong Supabase Dashboard > Authentication > Users, **đồng thời** insert vào bảng `employees` với cùng email:

```sql
-- HR Admin (login chính cho demo)
INSERT INTO employees (email, full_name, vai_tro, department, employee_code)
VALUES ('hr@company.com', 'Chị Lan', 'hr_admin', 'Human Resources', 'HR001');

-- NV mới (test chatbot)
INSERT INTO employees (email, full_name, vai_tro, department, employee_code, start_date)
VALUES ('minh@company.com', 'Bạn Minh', 'nhan_vien_moi', 'Engineering', 'ENG042', '2026-05-20');
```

### Roles

| vai_tro | Quyền |
|---------|-------|
| `hr_admin` | Full access mọi endpoint |
| `it_admin` | Giờ chỉ cần dùng magic link (không login) |
| `quan_ly` | Giờ chỉ cần dùng magic link (không login) |
| `nhan_vien_moi` | Xem checklist + chat với bot |

---

> [!IMPORTANT]
> **TLDR cho teammate:**
>
> ```bash
> # 1. Cài dependencies
> pip install -r requirements.txt
>
> # 2. Copy .env và điền Supabase credentials (xin từ Person B)
> cp .env.example .env
>
> # 3. Chạy backend
> uvicorn src.backend.main:app --reload --port 8000
>
> # 4. Mở trình duyệt
> # http://localhost:8000/docs  ← Swagger UI (xem tất cả 65 endpoints)
> ```
>
> - Response format: `{"success": true, "data": {...}}` hoặc `{"success": false, "error": "..."}`
> - Login: `POST /api/auth/login` → lấy `access_token` → Header `Authorization: Bearer <token>`

