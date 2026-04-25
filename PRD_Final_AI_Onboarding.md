# PRD Final: AI Onboarding Module
## Chương trình AI Thực Chiến — Vingroup

---

## 1. Tầm nhìn sản phẩm

### 1.1. Một câu mô tả

AI Onboarding Module là một plugin thông minh cắm vào hệ sinh thái HR hiện có của doanh nghiệp — không thay thế HRIS hay LMS, mà bổ sung AI layer để tự động hóa, cá nhân hóa, và theo dõi quy trình onboarding nhân viên mới.

### 1.2. Bối cảnh

Công ty 500+ nhân viên, tuyển 50-80 nhân viên mới mỗi năm theo batch. HR team 3 người phải trả lời 200+ câu hỏi lặp lại mỗi batch. Time-to-productivity trung bình 45 ngày. Không có visibility vào progress onboarding từng người.

### 1.3. Mục tiêu

- Giảm time-to-productivity từ 45 ngày xuống 25-30 ngày
- Giảm 70% câu hỏi lặp lại cho HR team
- 100% NV mới có checklist cá nhân hóa theo role
- HR có real-time dashboard với bottleneck detection
- Hệ thống tự phát hiện knowledge gaps và cải thiện theo thời gian

### 1.4. Điểm khác biệt so với sản phẩm hiện có

Các sản phẩm onboarding hiện tại (BambooHR, ServiceNow, Workday) làm tốt workflow automation và task management. Module này bổ sung những gì họ chưa có:

- AI Agent — không chỉ trả lời câu hỏi mà thực hiện hành động (tạo ticket, update checklist)
- Context-aware chatbot — biết NV đang ở đâu trong checklist, trả lời theo context cá nhân
- Self-improving system — tự phát hiện content gaps, tự đề xuất cải thiện
- Sentiment tracking — phát hiện NV gặp khó khăn mà không cần survey
- Modular integration — cắm vào HRIS/LMS/IT Ops hiện có qua webhook

---

## 2. Users & Personas

### 2.1. Chị Lan — HR Admin

Profile: HR Manager, 5 năm kinh nghiệm, quản lý 3 HR staff. Xử lý 3-4 batch onboarding mỗi năm, mỗi batch 15-20 NV.

Pain points:
- Mất 3 ngày/batch chỉ để trả lời 200+ câu hỏi lặp lại
- Không biết NV nào đang stuck cho đến khi quá muộn
- Checklist giấy/spreadsheet — không track được progress real-time
- Phải chase IT, Admin, Manager thủ công cho mỗi NV mới

Cần từ hệ thống:
- Dashboard 1 nhìn thấy hết: ai đang tốt, ai cần can thiệp
- Chatbot xử lý 70%+ câu hỏi thay chị
- Hệ thống tự assign task cho IT/Admin/Manager, tự nhắc khi overdue
- AI tóm tắt tình hình và đề xuất hành động cụ thể

### 2.2. Bạn Minh — Nhân viên mới (Software Engineer)

Profile: Fresh graduate, ngày đầu đi làm. Không biết hỏi ai, sợ hỏi "ngu", cần setup 10+ tools để bắt đầu code.

Pain points:
- Overwhelmed ngày đầu: 20 việc cần làm, không biết ưu tiên gì
- Cần thông tin ngoài giờ hành chính (10PM đọc docs, có thắc mắc)
- Chờ IT setup accounts mất 2-3 ngày, không làm được gì

Cần từ hệ thống:
- Checklist rõ ràng: việc gì, deadline khi nào, ai hỗ trợ
- Bot hỏi 24/7 mà không ngại
- Biết mình đang ở đâu trong quá trình onboarding

### 2.3. Anh Hùng — Hiring Manager (Engineering Lead)

Profile: Quản lý team 8 người, nhận 2-3 NV mới mỗi năm. Bận project, dễ quên follow up NV mới.

Cần từ hệ thống:
- Nhận reminder khi có task cần làm (1-on-1, set goals)
- Weekly summary về progress NV mới
- Alert khi NV đang struggling

### 2.4. IT Admin

Profile: Quản lý provisioning accounts, thiết bị cho toàn công ty.

Cần từ hệ thống:
- Task tự động tạo trước start date, đầy đủ spec (role → cần tools gì)
- Confirm hoàn thành 1 chỗ → NV tự nhận notification

---

## 3. Kiến trúc hệ thống

### 3.1. Sơ đồ tổng thể

```
┌──────────────────── External Systems ────────────────────┐
│  ┌──────┐  ┌──────┐  ┌─────────┐  ┌────────┐  ┌──────┐ │
│  │ HRIS │  │ LMS  │  │ IT Ops  │  │ Slack  │  │ Doc  │ │
│  │      │  │      │  │ (Jira)  │  │        │  │Portal│ │
│  └──┬───┘  └──┬───┘  └────┬────┘  └───┬────┘  └──┬───┘ │
├─────┼─────────┼───────────┼────────────┼──────────┼─────┤
│     ▼         ▼           ▼            ▼          ▼     │
│  ┌──────────────────────────────────────────────────┐   │
│  │            Integration Layer (Webhooks + API)     │   │
│  └────────────────────────┬─────────────────────────┘   │
│                           │                             │
│  ┌────────────────────────▼─────────────────────────┐   │
│  │           AI Onboarding Core Module               │   │
│  │                                                    │   │
│  │  ┌──────────────┐  ┌──────────────────────────┐   │   │
│  │  │  RAG Engine  │  │  Checklist Engine         │   │   │
│  │  │  - Hybrid    │  │  - AI Generate Plans      │   │   │
│  │  │    Search    │  │  - Multi-stakeholder      │   │   │
│  │  │  - Query     │  │  - Progress Tracking      │   │   │
│  │  │    Rewrite   │  │                            │   │   │
│  │  └──────────────┘  └──────────────────────────┘   │   │
│  │                                                    │   │
│  │  ┌──────────────┐  ┌──────────────────────────┐   │   │
│  │  │  AI Agent    │  │  Analytics Engine         │   │   │
│  │  │  - Chat      │  │  - Bottleneck Detection   │   │   │
│  │  │  - Actions   │  │  - Content Gap Detection  │   │   │
│  │  │  - Context   │  │  - Sentiment Tracking     │   │   │
│  │  │    Aware     │  │  - Health Score           │   │   │
│  │  └──────────────┘  └──────────────────────────┘   │   │
│  │                                                    │   │
│  │  ┌────────────────────────────────────────────┐   │   │
│  │  │  Supabase (Auth + PostgreSQL + pgvector    │   │   │
│  │  │            + Storage)                       │   │   │
│  │  └────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 3.2. Tech Stack

| Layer | Tech | Lý do |
|-------|------|-------|
| AI/LLM | Gemini API (abstraction layer sẵn sàng swap sang Ollama local) | Cloud API cho v1, có thể chuyển offline sau |
| Embedding | Gemini text-embedding-004 (abstraction layer sẵn sàng swap sang bge-m3) | 768 chiều, hỗ trợ tiếng Việt |
| Vector Search | pgvector trong Supabase | All-in-one, giảm ops cho team 3 người |
| Keyword Search | PostgreSQL tsvector (full-text search) | Hybrid search không cần thêm service |
| Database | Supabase PostgreSQL | Structured data, RLS, pg_cron |
| Auth | Supabase Auth (Google OAuth) | RLS tự động theo role |
| Backend | FastAPI (Python) | Python ecosystem, LangGraph, dễ test local |
| Agent | LangGraph | Agent workflow, tool use |
| Chat Integration | Slack Bolt SDK | Chatbot 24/7 |
| File Storage | Supabase Storage | Documents, uploads |
| Dashboard | React/Next.js hoặc Streamlit | HR dashboard |
| Scheduling | Supabase pg_cron | Reminders, reports |

### 3.3. Provider Abstraction (sẵn sàng swap API ↔ Local)

Toàn bộ LLM và Embedding calls đi qua abstraction layer. Khi chuyển sang local model, chỉ đổi 2 dòng trong .env:

```
# Hiện tại (API)
LLM_PROVIDER=gemini
EMBEDDING_PROVIDER=gemini

# Sau này (Local)
LLM_PROVIDER=ollama
EMBEDDING_PROVIDER=local
```

4 files abstraction: config.py, factory.py, llm.py (GeminiLLM + OllamaLLM), embedder.py (GeminiEmbedder + LocalEmbedder). Code RAG, Agent, mọi nơi gọi qua factory — không import trực tiếp provider.

Lưu ý khi swap embedding: Gemini = 768 chiều, bge-m3 = 1024 chiều → phải re-index toàn bộ docs.

---

## 4. RAG Pipeline chi tiết

### 4.1. Ingestion Pipeline

```
Upload .md/.txt files → Chunking → Embedding → pgvector + tsvector
```

Chunking strategy:
- Chunk size: ~400 characters (~300 tokens tiếng Việt)
- Overlap: ~80 characters (~50 tokens)
- Tách theo sentence boundary (không cắt giữa câu)
- Metadata mỗi chunk: department_tags, role_tags, source_title, source_url

Ghi chú: Tiếng Việt mật độ thông tin cao hơn tiếng Anh → chunk nhỏ hơn default. Con số 400 chars là điểm bắt đầu, sẽ tune qua evaluation.

Data source v1: Upload trực tiếp qua web form (không cần Confluence/Notion sync). 40 docs tiếng Việt cover 7 nhóm chủ đề.

### 4.2. Retrieval Pipeline (Hybrid Search + Query Rewriting)

```
User question
    ↓
Query Rewriting (Gemini rewrite câu hỏi mơ hồ)
    ↓
Parallel search:
├── Vector Search (pgvector cosine similarity, top 10)
│   └── Filter theo department + role
└── Keyword Search (tsvector BM25, top 10)
    ↓
Reciprocal Rank Fusion → top 5
    ↓
Inject vào prompt + Gemini generate answer
    ↓
Answer + citations + confidence score
```

Query Rewriting: khi NV hỏi "tôi chưa vào được hệ thống", Gemini rewrite thành "cách truy cập VPN nội bộ công ty" trước khi search. Tăng retrieval quality cho câu hỏi mơ hồ. Chỉ 1 LLM call thêm.

Hybrid Search: vector search bắt semantic ("chế độ nghỉ ngơi" → "chính sách nghỉ phép"), keyword search bắt exact term ("VPN", "Jira", "BHXH"). Combine bằng RRF — không cần thêm service, dùng PostgreSQL tsvector có sẵn.

### 4.3. Knowledge Base

Target: 40 docs tiếng Việt, chia 7 nhóm:

| Nhóm | Số docs | Ưu tiên |
|------|---------|---------|
| Hành chính & giấy tờ (BHXH, lương, nghỉ phép, thử việc, OT, bảo hiểm, hợp đồng) | 8 | Cao |
| IT & công cụ (email, Slack, VPN, Jira, Git, bảo mật, phòng họp, thiết bị) | 8 | Cao |
| Onboarding specific (Day 1 guide, 30-60-90 plan, FAQ, tools theo role, moonlighting) | 5 | Cao |
| Văn hóa & quy định (giờ làm, WFH, dress code, nội quy, giá trị, chống quấy rối, MXH) | 7 | Trung bình |
| Cơ cấu tổ chức (org chart, buddy/mentor, 1-on-1, key contacts, đề xuất ý tưởng) | 5 | Trung bình |
| Phát triển sự nghiệp (career ladder Engineering, non-Engineering, đào tạo, đánh giá) | 4 | Nice to have |
| Tiện ích văn phòng (parking, canteen, facilities) | 3 | Nice to have |

Mỗi doc 300-600 từ, viết như tài liệu nội bộ thật: có số cụ thể, tên phòng ban cụ thể, email liên hệ cụ thể. Dùng AI draft → chỉnh lại cho realistic.

### 4.4. Evaluation Pipeline

50 câu hỏi test, chia đều theo topic:
- Nghỉ phép/HR (10 câu)
- Bảo hiểm/benefits (8 câu)
- IT setup (8 câu)
- Quy trình hành chính (8 câu)
- Văn hóa công ty (8 câu)
- Role-specific (8 câu)

Mỗi câu có expected answer. Chấm: đúng / đúng một phần / sai / không trả lời được. Target: ≥ 80% đúng hoặc đúng một phần.

Tune strategy: test 3 chunk sizes (400, 600, 800 chars), chọn config accuracy cao nhất. Đây là data chứng minh chất lượng khi present.

---

## 5. Use Cases chi tiết

### 5.1. Tổng quan 10 Use Cases

| UC | Tên | Tuần | Mô tả |
|----|-----|------|-------|
| UC-09 | Đăng nhập & xác thực | 1 | Google OAuth, phân quyền RLS 3 role |
| UC-11 | Upload & index tài liệu | 1 | Upload .md/.txt → chunk → embed → pgvector |
| UC-08 | RAG Pipeline | 1-2 | Hybrid search + query rewriting + citation |
| UC-02 | AI Agent Chatbot | 2-3 | Chat + actions + context-aware qua Slack |
| UC-17 | Pre-onboarding | 3 | Upload giấy tờ + thông tin ngày đầu |
| UC-03 | Tạo kế hoạch cá nhân hóa | 3 | AI generate → HR approve → multi-stakeholder |
| UC-07 | Theo dõi tiến độ | 3 | Đánh dấu hoàn thành, tính progress |
| UC-05 | Nhắc nhở tự động | 4 | Escalation 3 tầng (NV → Manager → HR) |
| UC-16 | HR Dashboard + Copilot | 4 | Dashboard + AI tóm tắt + action buttons |
| UC-18 | Content Gap Detection | 4 | Cluster câu hỏi chưa trả lời → đề xuất docs |

### 5.2. UC-02: AI Agent Chatbot

Khác biệt cốt lõi so với chatbot thông thường — Agent không chỉ trả lời mà thực hiện hành động.

Capabilities:

Trả lời câu hỏi (RAG):
- NV hỏi "Chính sách nghỉ phép?" → hybrid search → query rewriting nếu câu mơ hồ → Gemini generate → trả lời với citation

Context-aware từ checklist:
- NV hỏi "Tôi cần làm gì?" → Agent query checklist → "Bạn còn 3 việc tuần này, ưu tiên nhất là Security Training (deadline ngày mai)"
- NV hỏi về VPN → Agent trả lời + nhận ra checklist có "Setup VPN" chưa done → "Bạn muốn đánh dấu hoàn thành luôn không?"

Thực hiện hành động:
- NV nói "Tôi chưa có Jira" → Agent tạo stakeholder task cho IT → gửi Slack cho IT Admin → reply "Đã gửi yêu cầu cho IT"

Fallback thông minh:
- Confidence thấp → "Mình chưa chắc, bạn muốn chuyển cho HR không?"
- Câu hỏi nhạy cảm ("tôi bị quấy rối") → không trả lời, escalate ngay cho HR

Sentiment tracking ngầm:
- Mỗi conversation kết thúc → Gemini classify sentiment → lưu DB
- Không cần NV tự report

Sequence:
```
NV → Slack: "Tôi chưa có Jira, không setup dev env được"
Slack → FastAPI: webhook + user_id
FastAPI → Supabase: Lấy role + department + checklist hiện tại
FastAPI → Agent (LangGraph):
  ├── Query Rewriting: "cách tạo tài khoản Jira công ty"
  ├── Hybrid Search: vector + keyword → top 5 chunks
  ├── Detect intent: cần action (tạo task IT)
  ├── Execute: tạo stakeholder_task cho IT
  └── Generate response + citation
FastAPI → Slack: Reply NV + gửi Slack cho IT channel
FastAPI → Supabase: Lưu conversation + sentiment
```

### 5.3. UC-17: Pre-onboarding & Document Collection

Flow: NV ký offer → HR tạo NV → hệ thống gửi email preboarding → NV mở portal → upload giấy tờ + xem thông tin ngày đầu.

NV thấy trên portal:
- Danh sách giấy tờ cần nộp (CMND, ảnh 3x4, sổ BHXH, bằng cấp, số TK ngân hàng) với status từng cái
- Thông tin ngày đầu (địa chỉ, giờ đến, người đón, dress code, mang theo gì)

Hệ thống tự động:
- Tạo task IT (chuẩn bị laptop + accounts) trước start date
- Tạo task Admin (badge, chỗ ngồi)
- Tạo task Manager (assign buddy)
- Nhắc NV chưa nộp đủ (3 ngày và 1 ngày trước start date)

HR thấy trên dashboard:
- Bảng NV × documents (submitted/missing)
- Flag NV chưa mở email preboarding

Scope v1: upload files + thông tin ngày đầu + HR tracking. Bỏ: e-signature, form thông tin chi tiết.

### 5.4. UC-03: Tạo kế hoạch — Multi-stakeholder

Nâng cấp so với UML gốc: khi HR approve plan, không chỉ NV thấy checklist mà IT/Admin/Manager cũng nhận task riêng.

Flow:
```
HR tạo NV → Gemini generate plan (JSON mode + template + few-shot)
→ Plan status = "bản thảo" → HR xem, sửa nếu cần
→ HR nhấn "Phê duyệt"
→ Hệ thống tự động:
  ├── NV: 12 tasks (training, giấy tờ, meet team...)
  ├── IT: 3 tasks (laptop, accounts, VPN) → Slack notify
  ├── Admin: 2 tasks (badge, chỗ ngồi) → Slack notify
  └── Manager: 3 tasks (1-on-1, set goals, assign buddy) → Slack notify
```

### 5.5. UC-16: HR Dashboard + Copilot

Nâng cấp: không chỉ hiện data mà có AI tóm tắt + action buttons (từ insight đến hành động trong 1 click).

Dashboard views:
- Overview: tổng NV, avg completion %, overdue count, health score distribution
- Employee detail: checklist progress, stakeholder tasks, preboarding docs, sentiment trend
- Bottleneck: tasks có ≥ 3 NV overdue, avg ngày trễ, root cause hint
- Content Gaps: topic clusters từ unanswered questions, suggested actions

HR Copilot flow:
```
HR thấy NV An health_score = đỏ
→ Nhấn "Tóm tắt AI"
→ Gemini: "NV An stuck vì:
   1. Chưa được assign buddy (manager chưa làm)
   2. IT chưa provision Jira (quá hạn 3 ngày)
   3. Sentiment tiêu cực trong 2 cuộc chat gần nhất"
→ Action buttons:
   [Assign buddy ngay] → Slack gửi Manager
   [Escalate IT task] → Slack gửi IT Lead
   [Schedule check-in] → Tạo reminder
```

### 5.6. UC-18: Content Gap Detection

Mỗi khi chatbot trả lời confidence thấp hoặc fallback → log vào unanswered_questions. Cuối tuần, Gemini cluster thành 5-7 topics → hiện trên dashboard HR:

```
Content Gaps — Tuần 20/5 - 26/5

🔴 Quy trình claim bảo hiểm (4 câu hỏi) — HIGH
   → Đề xuất: Tạo doc "Hướng dẫn claim BHSK A-Z"
   [Tạo task]

🟡 Tiêu chí đánh giá thử việc (3 câu hỏi) — MEDIUM
   → Đề xuất: Tạo doc "Quy trình đánh giá probation"
   [Tạo task]
```

Câu chuyện present: "Hệ thống không chỉ trả lời — mà tự biết mình thiếu gì và đề xuất cải thiện."

---

## 6. Data Model

### 6.1. Core Tables

```sql
-- Nhân viên
CREATE TABLE employees (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_code TEXT UNIQUE NOT NULL,
  full_name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  personal_email TEXT,
  phone TEXT,
  role TEXT NOT NULL,
  department TEXT NOT NULL,
  seniority TEXT DEFAULT 'junior',
  location TEXT DEFAULT 'HCM',
  start_date DATE NOT NULL,
  probation_end_date DATE,
  manager_id UUID REFERENCES employees(id),
  contract_type TEXT DEFAULT 'full_time',
  vai_tro TEXT DEFAULT 'nhan_vien_moi'
    CHECK (vai_tro IN ('nhan_vien_moi', 'quan_ly', 'hr_admin', 'it_admin')),
  onboarding_status TEXT DEFAULT 'pre_boarding'
    CHECK (onboarding_status IN ('pre_boarding', 'in_progress', 'completed', 'terminated')),
  health_score TEXT DEFAULT 'green'
    CHECK (health_score IN ('green', 'yellow', 'red')),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Kế hoạch onboarding
CREATE TABLE onboarding_plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id UUID REFERENCES employees(id) UNIQUE,
  status TEXT DEFAULT 'ban_thao'
    CHECK (status IN ('ban_thao', 'da_duyet', 'dang_thuc_hien', 'hoan_thanh')),
  generated_by TEXT DEFAULT 'ai',
  approved_by UUID REFERENCES employees(id),
  approved_at TIMESTAMPTZ,
  total_items INTEGER DEFAULT 0,
  completed_items INTEGER DEFAULT 0,
  completion_percentage FLOAT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Nhiệm vụ checklist
CREATE TABLE checklist_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id UUID REFERENCES onboarding_plans(id),
  employee_id UUID REFERENCES employees(id),
  title TEXT NOT NULL,
  description TEXT,
  category TEXT NOT NULL
    CHECK (category IN ('admin', 'training', 'tools', 'compliance', 'role_specific', 'social')),
  week INTEGER NOT NULL DEFAULT 1,
  deadline_day INTEGER NOT NULL,
  deadline_date DATE,
  owner TEXT NOT NULL
    CHECK (owner IN ('new_hire', 'manager', 'hr', 'it', 'admin', 'finance')),
  is_mandatory BOOLEAN DEFAULT true,
  is_compliance BOOLEAN DEFAULT false,
  status TEXT DEFAULT 'chua_bat_dau'
    CHECK (status IN ('chua_bat_dau', 'dang_lam', 'hoan_thanh', 'qua_han', 'bo_qua')),
  completed_at TIMESTAMPTZ,
  completed_by UUID,
  depends_on UUID REFERENCES checklist_items(id),
  external_ref_type TEXT,
  external_ref_id TEXT,
  sort_order INTEGER DEFAULT 0,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Task cho stakeholders
CREATE TABLE stakeholder_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_id UUID REFERENCES onboarding_plans(id),
  employee_id UUID REFERENCES employees(id),
  checklist_item_id UUID REFERENCES checklist_items(id),
  assigned_to_team TEXT NOT NULL
    CHECK (assigned_to_team IN ('it', 'admin', 'finance', 'manager')),
  assigned_to_user_id UUID REFERENCES employees(id),
  title TEXT NOT NULL,
  description TEXT,
  details JSONB,
  status TEXT DEFAULT 'pending'
    CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
  deadline DATE,
  external_ticket_id TEXT,
  slack_message_ts TEXT,
  completed_at TIMESTAMPTZ,
  completed_by TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Tài liệu Knowledge Base
CREATE TABLE knowledge_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type TEXT NOT NULL DEFAULT 'manual_upload',
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  content_tsvector TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
  department_tags TEXT[],
  role_tags TEXT[],
  category TEXT,
  language TEXT DEFAULT 'vi',
  is_indexed BOOLEAN DEFAULT false,
  word_count INTEGER,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Vector chunks
CREATE TABLE knowledge_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID REFERENCES knowledge_documents(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  content_tsvector TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
  chunk_index INTEGER NOT NULL,
  token_count INTEGER,
  embedding VECTOR(768),
  department_tags TEXT[],
  role_tags TEXT[],
  metadata JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Chatbot conversations
CREATE TABLE chatbot_conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id UUID REFERENCES employees(id),
  channel TEXT NOT NULL CHECK (channel IN ('slack', 'teams', 'web')),
  started_at TIMESTAMPTZ DEFAULT now(),
  ended_at TIMESTAMPTZ,
  message_count INTEGER DEFAULT 0,
  sentiment_overall TEXT,
  escalated BOOLEAN DEFAULT false
);

-- Messages
CREATE TABLE chatbot_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID REFERENCES chatbot_conversations(id),
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content TEXT NOT NULL,
  sources JSONB,
  actions_taken JSONB,
  confidence_score FLOAT,
  feedback TEXT CHECK (feedback IN ('positive', 'negative')),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Câu hỏi chưa trả lời (content gap detection)
CREATE TABLE unanswered_questions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id UUID REFERENCES employees(id),
  conversation_id UUID REFERENCES chatbot_conversations(id),
  question_text TEXT NOT NULL,
  reason TEXT CHECK (reason IN ('low_confidence', 'no_match', 'escalated', 'negative_feedback')),
  confidence_score FLOAT,
  topic_cluster TEXT,
  reviewed BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Sentiment logs
CREATE TABLE sentiment_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id UUID REFERENCES employees(id),
  conversation_id UUID REFERENCES chatbot_conversations(id),
  sentiment TEXT CHECK (sentiment IN ('positive', 'neutral', 'confused', 'frustrated', 'negative')),
  confidence FLOAT,
  topics TEXT[],
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Preboarding documents
CREATE TABLE preboarding_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id UUID REFERENCES employees(id),
  document_type TEXT NOT NULL,
  filename TEXT,
  storage_path TEXT,
  status TEXT DEFAULT 'missing'
    CHECK (status IN ('missing', 'uploaded', 'verified', 'rejected')),
  verified_by UUID,
  uploaded_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Reminder logs
CREATE TABLE reminder_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  checklist_item_id UUID REFERENCES checklist_items(id),
  employee_id UUID REFERENCES employees(id),
  escalation_tier INTEGER NOT NULL,
  sent_to TEXT NOT NULL,
  channel TEXT NOT NULL,
  sent_at TIMESTAMPTZ DEFAULT now()
);

-- Webhook configs
CREATE TABLE webhook_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  url TEXT NOT NULL,
  secret TEXT NOT NULL,
  events TEXT[] NOT NULL,
  active BOOLEAN DEFAULT true,
  created_by UUID REFERENCES employees(id),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Webhook logs
CREATE TABLE webhook_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  webhook_config_id UUID REFERENCES webhook_configs(id),
  direction TEXT NOT NULL CHECK (direction IN ('in', 'out')),
  event_type TEXT NOT NULL,
  endpoint_url TEXT NOT NULL,
  request_body JSONB NOT NULL,
  response_status INTEGER,
  success BOOLEAN,
  retry_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX idx_chunks_embedding ON knowledge_chunks
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_chunks_tsvector ON knowledge_chunks USING gin(content_tsvector);
CREATE INDEX idx_docs_tsvector ON knowledge_documents USING gin(content_tsvector);
CREATE INDEX idx_checklist_employee ON checklist_items(employee_id);
CREATE INDEX idx_checklist_overdue ON checklist_items(deadline_date, status)
  WHERE status != 'hoan_thanh';
CREATE INDEX idx_stakeholder_team ON stakeholder_tasks(assigned_to_team, status);
CREATE INDEX idx_sentiment_employee ON sentiment_logs(employee_id, created_at);
CREATE INDEX idx_unanswered_reviewed ON unanswered_questions(reviewed, created_at);
```

---

## 7. Integration Points (Modular Architecture)

### 7.1. Webhooks In — nhận từ hệ thống bên ngoài

| Endpoint | Source | Trigger |
|----------|--------|---------|
| POST /api/webhooks/hris/new-employee | HRIS | NV mới được tạo |
| POST /api/webhooks/hris/employee-updated | HRIS | Đổi dept/role/start date |
| POST /api/webhooks/lms/course-completed | LMS | NV hoàn thành training |
| POST /api/webhooks/it/ticket-resolved | IT Ops | IT xong provision |
| POST /api/webhooks/documents/submitted | Doc Portal | NV upload giấy tờ |

### 7.2. Webhooks Out — gửi ra hệ thống bên ngoài

| Event | Khi nào | Gửi cho |
|-------|---------|---------|
| employee.onboarding.started | HR approve plan | HRIS, IT |
| employee.task.assigned_to_stakeholder | Plan approve → tạo tasks | IT, Admin, Manager |
| employee.task.overdue | Task quá hạn | Slack + external |
| employee.risk.detected | Health score → đỏ | HR, Manager |
| employee.onboarding.completed | Tất cả mandatory done | HRIS |
| content.gap.detected | Weekly clustering | HR |

### 7.3. REST API

| Endpoint | Mô tả |
|----------|-------|
| GET /api/employees/:id/onboarding-status | Trạng thái + health score |
| GET /api/employees/:id/checklist | Checklist chi tiết + progress |
| GET /api/analytics/batch/:id/summary | Overview batch |
| GET /api/analytics/bottlenecks | Bottleneck detection |
| GET /api/analytics/content-gaps | Content gap clusters |

### 7.4. Demo Strategy

Không build HRIS/LMS thật. Tạo Mock Control Panel:
- Nút "HRIS: Tạo NV mới" → gọi webhook → trigger full flow
- Nút "LMS: Hoàn thành training" → gọi webhook → checklist auto-update
- Nút "IT: Ticket resolved" → gọi webhook → NV nhận notification

Giám khảo thấy 2-3 hệ thống "nói chuyện" real-time.

Chi tiết webhook schema: xem file Webhook_API_Schema.md

---

## 8. Team Structure & Contracts

### 8.1. Phân công 3 người

| Người | Role | Own |
|-------|------|-----|
| A | Frontend | Dashboard, Preboarding portal, Mock panel, UI/UX |
| B | Backend (FastAPI) | API endpoints, Supabase integration, webhooks, reminders |
| C | Agent/ML (LangGraph) | RAG pipeline, Agent logic, sentiment, content gap |

### 8.2. Development Contracts

Cả 3 người chốt ngày đầu tiên, không tự sửa mà không thông báo:

API Contract (Frontend ↔ Backend): mọi endpoint, request/response format.
Agent Contract (Backend ↔ Agent): input/output format cho search, chat, generate checklist, detect gaps.
Shared Types (Pydantic schemas): cả 3 người import từ 1 file.

### 8.3. Cấu trúc project

```
A20-App-090/
├── contracts/                    ← Chốt ngày đầu, cả 3 tuân theo
│   ├── api-contract.md
│   ├── agent-contract.py
│   └── shared-types.py
│
├── app/                          ← Người A: Frontend
│   ├── src/pages/
│   ├── src/components/
│   ├── src/api/client.ts
│   └── src/types.ts
│
├── backend/                      ← Người B: FastAPI Backend
│   ├── api/
│   │   ├── auth.py
│   │   ├── employees.py
│   │   ├── chat.py
│   │   ├── checklist.py
│   │   ├── analytics.py
│   │   ├── preboarding.py
│   │   └── webhooks.py
│   ├── schemas.py
│   ├── database.py
│   └── main.py
│
├── agent/                        ← Người C: Agent/ML
│   ├── core/
│   │   ├── config.py
│   │   ├── factory.py
│   │   ├── llm.py
│   │   └── embedder.py
│   ├── rag/
│   │   ├── chunking.py
│   │   └── retriever.py
│   ├── graph/
│   │   ├── nodes.py
│   │   ├── state.py
│   │   └── builder.py
│   ├── tools/
│   ├── prompts/
│   └── interface.py              ← Expose functions theo contract
│
├── data/raw_docs/                ← 40 docs .md
├── scripts/
│   ├── ingest.py
│   └── evaluate.py
└── docs/
```

### 8.4. Quy tắc tránh conflict

- Mỗi người chỉ sửa file trong folder của mình
- Folder contracts/ cần cả 3 đồng ý trước khi sửa
- Git branching: main + dev/frontend + dev/backend + dev/agent
- Integration test thứ 6 hàng tuần: merge + test end-to-end
- Standup 15 phút mỗi ngày

---

## 9. Sprint Plan — 6 tuần

### Sprint 1 (Tuần 1) — Nền tảng & Data

| Người | Tasks chính | Deliverable |
|-------|-------------|-------------|
| A | Viết 25+ docs (nhóm đỏ trước). Dashboard skeleton. | 25+ docs + dashboard layout |
| B | SQL schema + Auth + Employees CRUD + Upload endpoint | Schema + Login + Upload chạy |
| C | Ingestion pipeline (chunk → embed → pgvector). Search function | ingest() + search() hoạt động |

Demo cuối sprint: Upload doc → search "nghỉ phép" → trả đúng kết quả.

### Sprint 2 (Tuần 2) — Chatbot + Checklist

| Người | Tasks chính | Deliverable |
|-------|-------------|-------------|
| A | Dashboard Overview + Employee detail. Thêm 15 docs. | 40 docs total + dashboard functional |
| B | Checklist engine (generate → approve → view → complete) | Checklist E2E |
| C | Slack bot RAG flow + hybrid search + query rewriting + feedback | Bot accuracy ≥ 70% |

Demo cuối sprint: Bot Slack trả lời với citation. Tạo NV → checklist generate → approve.

### Sprint 3 (Tuần 3) — Agent + Integration

| Người | Tasks chính | Deliverable |
|-------|-------------|-------------|
| A | Bottleneck tab + Mock control panel + Preboarding portal | Mock panel + portal |
| B | Multi-stakeholder tasks + Webhook handlers + Preboarding backend | Webhooks + stakeholders |
| C | Agent upgrade (context-aware, actions, sentiment) | Agent hoạt động |

Demo cuối sprint: Bot hành động. Mock panel trigger flow. Multi-stakeholder.

### Sprint 4 (Tuần 4) — Intelligence Layer + Polish

| Người | Tasks chính | Deliverable |
|-------|-------------|-------------|
| A | Content Gap UI + Copilot UI + action buttons + UI polish | Dashboard đẹp |
| B | Reminders 3 tầng + Action APIs + Welcome flow | Auto-reminders |
| C | Content gap detection + HR Copilot function + RAG eval 50 câu | Accuracy ≥ 80% |

Demo cuối sprint: Content gap + Copilot + Reminders. CODE FREEZE.

### Sprint 5 (Tuần 5) — Stabilize + Prepare

| Tất cả | Tasks |
|--------|-------|
| T2-T3 | Chạy full flow 3 lần. Fix bugs. Edge case testing |
| T4 | Demo script 5 phút + Slides 5-7 trang + Q&A prep 10 câu |
| T5 | Record backup video. Rehearse lần 1 cả team |
| T6 | Rehearse lần 2 trước bạn bè. Demo data finalize |

### Sprint 6 (Tuần 6) — Rehearse + Demo Day

| Tất cả | Tasks |
|--------|-------|
| T2 | Rehearse lần 3 |
| T3 | Rehearse lần 4 trước team khác/mentor |
| T4 | Final check: internet, API, Supabase, backup |
| T5 | Rehearse lần 5: final confidence run |
| T6 | DEMO DAY |

---

## 10. Demo Script — 5 phút

### Phút 1: Mở đầu bằng pain point

"Chị Lan, HR Manager, mỗi tháng mất 3 ngày chỉ để trả lời cùng 200 câu hỏi. Bạn Minh, ngày đầu đi làm, overwhelmed không biết hỏi ai. Hệ thống này giải quyết cả hai."

### Phút 2: Demo flow tự động

Nhấn "HRIS: Tạo NV mới" trên mock panel → Show Slack: bot gửi welcome message + checklist xuất hiện. "Toàn bộ tự động, IT và Admin đã nhận task trên Slack — HR không cần làm gì."

### Phút 3: Demo AI Agent

Slack: "Chính sách nghỉ phép?" → Bot trả lời + citation.
Slack: "Tôi cần làm gì tiếp?" → Bot trả lời từ checklist.
Slack: "Tôi chưa có Jira" → Bot tạo task IT + reply.

### Phút 4: Demo HR Dashboard + Copilot

Dashboard overview → Chỉ NV đỏ → "Tóm tắt AI" → AI phân tích + đề xuất → Click action button → Slack notify.
Content gap tab: "Hệ thống tự phát hiện thiếu docs về bảo hiểm."

### Phút 5: Kiến trúc + Kết

Architecture: "Module cắm vào HRIS, LMS, IT Ops hiện có."
Metrics: "50 câu test, accuracy 82%. Tiết kiệm ước tính 15 giờ HR/batch."
Câu chốt: "Hệ thống không chỉ trả lời — mà hành động, và tự biết mình cần cải thiện gì."

---

## 11. Success Metrics

| Metric | Cách đo | Target v1 |
|--------|---------|-----------|
| RAG accuracy | 50 câu test, chấm manual | ≥ 80% |
| Response time | Log timestamp | < 5 giây |
| End-to-end flow | HRIS webhook → complete | Chạy mượt demo |
| Stakeholder notification | Approve → Slack sent | < 30 giây |
| Bottleneck detection | 10 NV test data, 3 stuck cùng task | Hiện đúng |
| Content gap | 10 câu hỏi ngoài KB → cluster | ≥ 3 clusters chính xác |
| Sentiment accuracy | 20 conversations test | ≥ 75% |

---

## 12. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| RAG quality thấp tiếng Việt | Bot trả lời sai | Chunk 400 chars, hybrid search, eval 50 câu, tune |
| Gemini hallucination | NV nhận sai info | Strict RAG-only, confidence threshold, fallback HR |
| Slack API rate limit | Bot chậm/miss | Queue messages, batch notifications |
| Demo day API/internet down | Không demo được | Backup video, mobile hotspot |
| Knowledge base thiếu | Bot không answer được | 40 docs cover top 50 câu hỏi |
| 3 người code conflict | Mất thời gian merge | Contracts + vertical folders + weekly integration |
| Webhook integration lỗi | Flow không chạy | Mock panel thay thế |

---

## 13. Những gì KHÔNG làm trong v1

- Microsoft Teams integration (chỉ Slack)
- HRIS/LMS thật (dùng mock panel)
- Confluence/Notion sync (dùng upload trực tiếp)
- Offline/local model (dùng Gemini API, có abstraction layer)
- Adaptive learning path
- Gamification
- Multi-tenant
- Mobile app
- E-signature thật
- Knowledge graph
- Video transcript ingestion
- Reranking, Multi-query, HyDE, Parent-child retrieval

---

## 14. Roadmap v1 → v3

| Phase | Timeline | Features |
|-------|----------|----------|
| v1.0 | 6 tuần | 10 UC + mock integrations + 40 docs |
| v1.1 | +2 tuần | Teams integration, Confluence sync, reranking |
| v2.0 | +4 tuần | Real HRIS integration, LMS auto-enroll, local model option |
| v3.0 | +6 tuần | Knowledge graph, video ingestion, multi-tenant, cross-batch analytics |

---

## 15. Q&A Prep — 10 câu giám khảo sẽ hỏi

1. Tại sao pgvector mà không dùng ChromaDB/Qdrant?
   → pgvector tích hợp Supabase, giảm ops cho team 3 người. Kiến trúc tách interface, swap được.

2. Chunking strategy tiếng Việt?
   → 400 chars (~300 tokens), nhỏ hơn EN vì mật độ thông tin cao hơn. Đã test 3 sizes, chọn accuracy cao nhất.

3. Handle hallucination thế nào?
   → Strict RAG-only, confidence threshold, fallback "chuyển HR". Không generate từ knowledge chung.

4. Scale thế nào nếu 5000 NV?
   → pgvector swap sang Qdrant (đã có interface). Supabase scale vertical. FastAPI stateless, horizontal scale.

5. Security/Privacy?
   → RLS Supabase: NV chỉ thấy data mình. HR thấy tất cả. Không log PII trong conversations.

6. Chi phí vận hành?
   → Gemini API ~$50-100/tháng ở scale này. Supabase free tier đủ cho 500 NV.

7. Tại sao không dùng LangChain Text Splitter?
   → Code chunking hiện tại tách theo sentence, có overlap, đã test đạt accuracy 82%. Thêm library không cải thiện mà thêm dependency.

8. Hybrid search cụ thể thế nào?
   → Vector (cosine) + Keyword (tsvector BM25) chạy song song, combine bằng Reciprocal Rank Fusion. Keyword quan trọng cho exact terms (VPN, Jira, BHXH).

9. Sau này chuyển offline thế nào?
   → Đổi 2 dòng .env: LLM_PROVIDER=ollama, EMBEDDING_PROVIDER=local. Re-index docs. Code không đổi.

10. So với sản phẩm hiện có (BambooHR, ServiceNow)?
    → Họ có workflow tốt nhưng không có: AI Agent hành động, self-improving content gap, sentiment tracking, context-aware chatbot.
