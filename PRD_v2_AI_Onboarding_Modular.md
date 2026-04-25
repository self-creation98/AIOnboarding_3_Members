# PRD v2: AI Onboarding Module — Kiến trúc Modular

## 1. Tầm nhìn sản phẩm

### 1.1. Một câu mô tả

AI Onboarding Module là một **plugin thông minh** cắm vào hệ sinh thái HR hiện có của doanh nghiệp — nó không thay thế HRIS hay LMS, mà bổ sung AI layer để tự động hóa, cá nhân hóa, và theo dõi quy trình onboarding nhân viên mới.

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

- **AI Agent** — không chỉ trả lời câu hỏi mà thực hiện hành động (tạo ticket, update checklist, đặt lịch)
- **Context-aware chatbot** — biết NV đang ở đâu trong checklist, trả lời theo context cá nhân
- **Self-improving system** — tự phát hiện content gaps, tự đề xuất cải thiện
- **Sentiment tracking** — phát hiện NV gặp khó khăn mà không cần survey
- **Modular integration** — cắm vào HRIS/LMS/IT Ops hiện có qua webhook, không yêu cầu thay đổi hệ thống

---

## 2. Users & Personas

### 2.1. Chị Lan — HR Admin

**Profile:** HR Manager, 5 năm kinh nghiệm, quản lý 3 HR staff. Xử lý 3-4 batch onboarding mỗi năm, mỗi batch 15-20 NV.

**Pain points:**
- Mất 3 ngày/batch chỉ để trả lời cùng 200+ câu hỏi lặp lại
- Không biết NV nào đang stuck cho đến khi quá muộn
- Checklist giấy/spreadsheet — không track được progress real-time
- Phải chase IT, Admin, Manager thủ công cho mỗi NV mới

**Cần từ hệ thống:**
- Dashboard 1 nhìn thấy hết: ai đang tốt, ai cần can thiệp
- Chatbot xử lý 70%+ câu hỏi thay chị
- Hệ thống tự assign task cho IT/Admin/Manager, tự nhắc khi overdue
- AI tóm tắt tình hình + đề xuất hành động cụ thể

### 2.2. Bạn Minh — Nhân viên mới (Software Engineer)

**Profile:** Fresh graduate, ngày đầu đi làm. Không biết hỏi ai, sợ hỏi "ngu", cần setup 10+ tools để bắt đầu code.

**Pain points:**
- Overwhelmed ngày đầu: 20 việc cần làm, không biết ưu tiên gì
- Cần thông tin ngoài giờ hành chính (10PM đọc docs, có thắc mắc)
- Chờ IT setup accounts mất 2-3 ngày, trong khi không làm được gì

**Cần từ hệ thống:**
- Checklist rõ ràng: việc gì, deadline khi nào, ai hỗ trợ
- Bot hỏi 24/7 mà không ngại
- Biết mình đang ở đâu trong quá trình onboarding

### 2.3. Anh Hùng — Hiring Manager (Engineering Lead)

**Profile:** Quản lý team 8 người, nhận 2-3 NV mới mỗi năm. Bận project, dễ quên follow up NV mới.

**Pain points:**
- Quên schedule 1-on-1 tuần đầu
- Không biết NV đã setup xong tools chưa để assign task
- HR hỏi "NV mới thế nào?" — không có data để trả lời

**Cần từ hệ thống:**
- Nhận reminder khi có task cần làm (1-on-1, set goals)
- Weekly summary về progress NV mới
- Alert khi NV đang struggling

### 2.4. IT Admin

**Profile:** Quản lý provisioning accounts, thiết bị cho toàn công ty.

**Pain points:**
- Nhận yêu cầu qua email/Slack rời rạc, dễ miss
- Không biết NV mới start ngày nào, cần tools gì cho role gì

**Cần từ hệ thống:**
- Task tự động tạo trước start date, đầy đủ spec (role → cần tools gì)
- Confirm hoàn thành 1 chỗ → NV tự nhận notification

---

## 3. Kiến trúc hệ thống

### 3.1. Sơ đồ tổng thể

```
┌──────────────────── External Systems ────────────────────┐
│  ┌──────┐  ┌──────┐  ┌─────────┐  ┌────────┐  ┌──────┐ │
│  │ HRIS │  │ LMS  │  │ IT Ops  │  │ Slack  │  │ Doc  │ │
│  │      │  │      │  │ (Jira)  │  │ Teams  │  │Portal│ │
│  └──┬───┘  └──┬───┘  └────┬────┘  └───┬────┘  └──┬───┘ │
│     │         │           │            │          │     │
├─────┼─────────┼───────────┼────────────┼──────────┼─────┤
│     ▼         ▼           ▼            ▼          ▼     │
│  ┌──────────────────────────────────────────────────┐   │
│  │            Integration Layer (API Gateway)        │   │
│  │                                                    │   │
│  │  Webhooks In    REST API     Webhooks Out          │   │
│  │  (nhận events)  (query data) (gửi notifications)  │   │
│  └────────────────────────┬─────────────────────────┘   │
│                           │                             │
│  ┌────────────────────────▼─────────────────────────┐   │
│  │           AI Onboarding Core Module               │   │
│  │                                                    │   │
│  │  ┌──────────────┐  ┌──────────────────────────┐   │   │
│  │  │  RAG Engine  │  │  Checklist Engine         │   │   │
│  │  │  - Ingestion │  │  - AI Generate Plans      │   │   │
│  │  │  - Search    │  │  - Multi-stakeholder      │   │   │
│  │  │  - Citation  │  │  - Progress Tracking      │   │   │
│  │  └──────────────┘  └──────────────────────────┘   │   │
│  │                                                    │   │
│  │  ┌──────────────┐  ┌──────────────────────────┐   │   │
│  │  │  AI Agent    │  │  Analytics Engine         │   │   │
│  │  │  - Chat      │  │  - Bottleneck Detection   │   │   │
│  │  │  - Actions   │  │  - Content Gap Detection  │   │   │
│  │  │  - Context   │  │  - Sentiment Tracking     │   │   │
│  │  └──────────────┘  │  - Health Score           │   │   │
│  │                     └──────────────────────────┘   │   │
│  │  ┌────────────────────────────────────────────┐   │   │
│  │  │         Supabase                            │   │   │
│  │  │  Auth │ PostgreSQL │ pgvector │ Storage     │   │   │
│  │  └────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 3.2. Tech Stack

| Layer | Tech | Lý do |
|-------|------|-------|
| AI/LLM | Gemini API | Generate checklist, chat, tóm tắt, sentiment |
| Embedding | Gemini text-embedding-004 | Vector 768 chiều, hỗ trợ tiếng Việt |
| Database | Supabase (PostgreSQL + pgvector) | All-in-one: auth, DB, vector, storage, edge functions |
| Auth | Supabase Auth (Google OAuth) | RLS tự động theo role |
| Backend | Supabase Edge Functions / FastAPI | Webhook handlers, RAG pipeline |
| Chat Integration | Slack Bolt SDK + Teams Bot Framework | Chatbot 24/7 |
| Dashboard | Streamlit hoặc Next.js | HR dashboard |
| Scheduling | Supabase pg_cron | Reminders, sync, reports |
| File Storage | Supabase Storage | Documents, uploads |

---

## 4. Use Cases chi tiết

### Tổng quan 10 Use Cases

| UC | Tên | Tuần | Mô tả ngắn |
|----|-----|------|-------------|
| UC-09 | Đăng nhập & xác thực | 1 | Google OAuth, phân quyền RLS |
| UC-11 | Sync tài liệu | 1 | Confluence/Notion → Knowledge Base |
| UC-08 | RAG Pipeline | 2 | Chunk → Embed → Search theo role |
| UC-02 | AI Agent Chatbot | 3 | Chat + hành động qua Slack/Teams |
| UC-17 | Pre-onboarding & Documents | 3 | Thu thập giấy tờ trước ngày đầu |
| UC-03 | Tạo kế hoạch cá nhân hóa | 4 | AI generate → HR approve → Multi-stakeholder |
| UC-07 | Theo dõi tiến độ | 4 | Đánh dấu hoàn thành, tính progress |
| UC-05 | Nhắc nhở tự động | 5 | Escalation 3 tầng qua Slack |
| UC-16 | HR Dashboard + Copilot | 6 | Dashboard + AI tóm tắt + Action buttons |
| UC-18 | Content Gap Detection | 6 | Tự phát hiện knowledge base thiếu gì |

### UC-02: AI Agent Chatbot (nâng cấp từ chatbot thuần)

**Trước (UML cũ):** Chatbot nhận câu hỏi → RAG search → trả lời text.

**Sau (v2):** AI Agent nhận câu hỏi → hiểu intent → thực hiện hành động + trả lời.

**Các khả năng của Agent:**

Trả lời câu hỏi (giữ nguyên):
- NV hỏi "Chính sách nghỉ phép?" → RAG search → trả lời với citation

Context-aware từ checklist (mới):
- NV hỏi "Tôi cần làm gì?" → Agent query checklist → "Bạn còn 3 việc tuần này, ưu tiên nhất là Security Training (deadline ngày mai)"
- NV hỏi về VPN → Agent trả lời + nhận ra checklist có item "Setup VPN" chưa done → "Bạn muốn mình đánh dấu Setup VPN là hoàn thành luôn không?"

Thực hiện hành động (mới):
- NV nói "Tôi chưa có tài khoản Jira" → Agent tạo stakeholder task cho IT → gửi Slack cho IT Admin → update checklist
- NV nói "Đặt lịch gặp manager" → Agent check availability → suggest slot → tạo calendar event (nếu có Google Calendar integration)

Sentiment tracking ngầm (mới):
- Mỗi conversation kết thúc → Gemini classify sentiment → lưu vào sentiment_logs
- Không cần NV tự report — system tự biết

**Sequence diagram:**

```
NV → Slack: "Tôi chưa có tài khoản Jira, không setup dev env được"
Slack → Backend: webhook + user_id
Backend → DB: Lấy role + department + checklist hiện tại
DB → Backend: role=engineer, checklist có "Setup Jira" status=pending
Backend → RAG: Search "tài khoản Jira" trong knowledge base
RAG → Backend: Hướng dẫn: "Jira được IT provision, thường mất 1 ngày làm việc..."
Backend → Gemini: System prompt + context checklist + RAG results + câu hỏi
Gemini → Backend: {
  "answer": "Tài khoản Jira do IT cấp. Mình sẽ tạo yêu cầu cho IT ngay nhé.",
  "actions": [
    {"type": "create_stakeholder_task", "team": "it", "task": "Provision Jira account cho NV-2024-051"}
  ],
  "checklist_related": "CI-051-012"
}
Backend → DB: Tạo stakeholder_task cho IT
Backend → Slack: Gửi message cho IT channel: "Cần cấp Jira cho Nguyễn Văn An (Engineering)"
Backend → Slack: Reply NV: "Mình đã gửi yêu cầu cho IT. Thường sẽ xong trong 1 ngày. Bạn sẽ nhận thông báo khi tài khoản sẵn sàng."
Backend → DB: Lưu conversation + classify sentiment
```

### UC-17: Pre-onboarding & Document Collection (mới)

**Mô tả:** Trước ngày đầu tiên, NV nhận email với link đến portal → upload giấy tờ cần thiết → HR theo dõi ai đã nộp gì.

**Flow:**

```
HRIS webhook → Onboarding tạo record NV → Gửi email preboarding
↓
NV mở link → Thấy danh sách giấy tờ cần nộp:
  ☐ CMND/CCCD (mặt trước + mặt sau)
  ☐ Ảnh 3x4
  ☐ Số tài khoản ngân hàng
  ☐ Sổ BHXH (nếu có)
  ☐ Bằng cấp
↓
NV upload từng file → Supabase Storage lưu trữ
↓
HR Dashboard hiển thị: "5/8 NV đã nộp đủ, 3 NV còn thiếu"
↓
Hệ thống tự nhắc NV chưa nộp đủ (3 ngày trước start date)
```

**Database schema bổ sung:**

```sql
CREATE TABLE preboarding_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id UUID REFERENCES employees(id),
  document_type TEXT NOT NULL,
  filename TEXT,
  storage_path TEXT,
  status TEXT DEFAULT 'missing' CHECK (status IN ('missing', 'uploaded', 'verified', 'rejected')),
  verified_by UUID,
  rejected_reason TEXT,
  uploaded_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### UC-03: Tạo kế hoạch — Multi-stakeholder (nâng cấp)

**Trước (UML cũ):** Gemini generate checklist → HR approve → NV thấy danh sách việc cần làm.

**Sau (v2):** Gemini generate checklist cho NV + tạo task cho IT/Admin/Manager/Finance → HR approve tất cả → Mỗi stakeholder nhận task trên Slack.

**Task assignment khi HR approve plan:**

```
HR nhấn "Phê duyệt kế hoạch" cho NV Nguyễn Văn An (Software Engineer)
↓
Hệ thống tự động:
├── NV: 12 tasks (nộp giấy tờ, training, meet team...)
├── IT: 3 tasks
│   ├── "Chuẩn bị MacBook Pro M3" — deadline: 1 ngày trước start
│   ├── "Tạo email + Slack + Jira + GitHub" — deadline: start date
│   └── "Setup VPN access" — deadline: start date
├── Admin: 2 tasks
│   ├── "Chuẩn bị badge nhân viên" — deadline: start date
│   └── "Assign chỗ ngồi tầng 5 — Engineering" — deadline: start date
├── Manager (Trần Thị Bình): 3 tasks
│   ├── "Schedule 1-on-1 tuần đầu" — deadline: day 3
│   ├── "Set 30-60-90 day goals" — deadline: day 5
│   └── "Assign buddy" — deadline: day 1
└── Mỗi stakeholder nhận Slack notification với task list
```

### UC-18: Content Gap Detection (mới)

**Mô tả:** Hệ thống tự phát hiện những chủ đề mà NV hay hỏi nhưng knowledge base chưa có câu trả lời. Hiển thị trên HR Dashboard với đề xuất hành động.

**Cách hoạt động:**

```
Mỗi khi chatbot trả lời:
├── Confidence cao (>0.8) → trả lời bình thường
├── Confidence thấp (<0.5) → trả lời + flag "Liên hệ HR nếu chưa rõ"
│   └── Log vào bảng unanswered_questions
└── Không tìm thấy match → "Mình chưa có thông tin này, để chuyển cho HR"
    └── Log vào bảng unanswered_questions

Cuối mỗi tuần (pg_cron Sunday 9PM):
├── Lấy tất cả unanswered_questions trong tuần
├── Gửi cho Gemini: "Phân nhóm các câu hỏi sau thành 5-7 chủ đề"
├── Gemini trả về clusters + suggested_action
├── Lưu vào analytics
└── Hiển thị trên HR Dashboard tab "Content Gaps"

HR thấy:
┌──────────────────────────────────────────────────────┐
│ Content Gaps — Tuần 20/5 - 26/5                      │
├──────────────────────────────────────────────────────┤
│ 🔴 Quy trình claim bảo hiểm (4 câu hỏi)            │
│    → Đề xuất: Tạo doc "Hướng dẫn claim BHSK A-Z"   │
│    [Tạo task]                                        │
│                                                      │
│ 🟡 Tiêu chí đánh giá thử việc (3 câu hỏi)          │
│    → Đề xuất: Tạo doc "Quy trình đánh giá probation"│
│    [Tạo task]                                        │
└──────────────────────────────────────────────────────┘
```

### UC-16: HR Dashboard + Copilot (nâng cấp)

**Trước (UML cũ):** Dashboard hiện data + nút "Tóm tắt AI" cho report text.

**Sau (v2):** Dashboard + AI tóm tắt + **Action buttons** — từ insight đến hành động trong 1 click.

**Flow:**

```
HR mở Dashboard → thấy NV An health_score = đỏ
↓
HR nhấn "Tóm tắt AI"
↓
Gemini phân tích: "Nguyễn Văn An stuck vì:
  1. Chưa được assign buddy (manager chưa làm)
  2. IT chưa provision Jira (task IT quá hạn 3 ngày)
  3. Sentiment tiêu cực trong 2 cuộc chat gần nhất

  Đề xuất hành động:"
↓
[Assign buddy ngay] → click → Slack gửi cho Manager: "Vui lòng assign buddy cho An hôm nay"
[Escalate IT task]  → click → Slack gửi cho IT Lead: "Urgent: Jira cho An đã quá hạn 3 ngày"
[Schedule check-in] → click → Tạo reminder HR gặp An ngày mai
```

---

## 5. Data Model

### 5.1. Core Tables

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

-- Nhiệm vụ trong checklist
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

-- Task cho stakeholders (IT, Admin, Manager, Finance)
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
  source_type TEXT NOT NULL
    CHECK (source_type IN ('confluence', 'notion', 'manual_upload')),
  source_id TEXT,
  source_url TEXT,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  department_tags TEXT[],
  role_tags TEXT[],
  category TEXT,
  language TEXT DEFAULT 'vi',
  last_synced_at TIMESTAMPTZ DEFAULT now(),
  is_stale BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Vector chunks cho RAG
CREATE TABLE knowledge_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID REFERENCES knowledge_documents(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  token_count INTEGER,
  embedding VECTOR(768),
  department_tags TEXT[],
  role_tags TEXT[],
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Conversations chatbot
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

-- Messages trong conversation
CREATE TABLE chatbot_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID REFERENCES chatbot_conversations(id),
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content TEXT NOT NULL,
  sources JSONB,
  actions_taken JSONB,
  confidence_score FLOAT,
  feedback TEXT CHECK (feedback IN ('positive', 'negative', NULL)),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Câu hỏi chưa trả lời được
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
  rejected_reason TEXT,
  uploaded_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Nhắc nhở đã gửi
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
  response_body JSONB,
  success BOOLEAN,
  error_message TEXT,
  retry_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX idx_checklist_employee ON checklist_items(employee_id);
CREATE INDEX idx_checklist_status ON checklist_items(status);
CREATE INDEX idx_checklist_overdue ON checklist_items(deadline_date, status)
  WHERE status != 'hoan_thanh';
CREATE INDEX idx_stakeholder_team ON stakeholder_tasks(assigned_to_team, status);
CREATE INDEX idx_sentiment_employee ON sentiment_logs(employee_id, created_at);
CREATE INDEX idx_unanswered_reviewed ON unanswered_questions(reviewed, created_at);
CREATE INDEX idx_chunks_embedding ON knowledge_chunks
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

---

## 6. Integration Points

Xem chi tiết đầy đủ trong file **Webhook_API_Schema.md**

### 6.1. Tóm tắt

| Hệ thống | Hướng | Mục đích |
|-----------|-------|----------|
| HRIS | → Onboarding | Tự động tạo onboarding khi có NV mới |
| LMS | ↔ Onboarding | Auto-enroll khóa học + nhận completion |
| IT Ops | ↔ Onboarding | Tạo ticket provision + nhận completion |
| Slack/Teams | ↔ Onboarding | Chatbot + reminders + notifications |
| Doc Portal | → Onboarding | Nhận documents NV upload |

### 6.2. Demo Strategy

Không cần build HRIS/LMS thật. Tạo **Mock Control Panel**:

- Nút "HRIS: Tạo NV mới" → gọi webhook, trigger toàn bộ flow
- Nút "LMS: NV hoàn thành Security Training" → gọi webhook, checklist auto-update
- Nút "IT: Ticket đã resolved" → gọi webhook, NV nhận notification

Giám khảo thấy 2-3 hệ thống "nói chuyện" real-time — rất ấn tượng mà effort chỉ là 1 page HTML với vài nút.

---

## 7. Timeline — 6 tuần × 3 người

### Phân công team

| Người | Vai trò | Own |
|-------|---------|-----|
| A | Backend + AI | RAG pipeline, Gemini integration, AI Agent logic, webhook handlers |
| B | Integration + Chat | Slack bot, webhook in/out, stakeholder tasks, preboarding portal |
| C | Frontend + Data | Dashboard, mock control panel, data model, analytics queries |

### Tuần 1: Nền tảng

| Người | Tasks |
|-------|-------|
| A | Setup Supabase project, database schema, pgvector extension, Edge Functions skeleton |
| B | Slack Bot app setup, Google OAuth config, basic webhook endpoint structure |
| C | Dashboard skeleton (Streamlit/Next.js), mock control panel, employees_master seed data |
| Chung | Viết 30-40 docs tiếng Việt cho knowledge base |

**Deliverable:** Login works, DB schema deployed, Slack bot responds "Hello", mock panel sends webhook.

### Tuần 2: RAG Pipeline + Ingestion

| Người | Tasks |
|-------|-------|
| A | Ingestion pipeline: docs → chunk (300 token) → embed (Gemini) → pgvector. Search function với role-based filtering |
| B | Confluence/Notion API connector (hoặc manual upload fallback). Webhook handler cho HRIS new-employee |
| C | Dashboard: employee list view, manual add employee form |

**Deliverable:** Upload docs → search returns relevant chunks → filtered by role.

### Tuần 3: AI Agent Chatbot + Preboarding

| Người | Tasks |
|-------|-------|
| A | Chatbot RAG flow: Slack message → retrieve → Gemini generate → reply with citation. Agent actions: checklist context, create stakeholder tasks |
| B | Preboarding document upload portal (simple web form + Supabase Storage). Webhook cho documents.submitted |
| C | Dashboard: preboarding document tracking view. Mock HRIS panel functional |

**Deliverable:** Slack bot answers questions with sources, aware of checklist. NV can upload docs.

### Tuần 4: Checklist Engine + Multi-stakeholder

| Người | Tasks |
|-------|-------|
| A | Gemini generate checklist (JSON mode + template + few-shot). Draft → Approve flow |
| B | Stakeholder task creation on plan approval. Slack notifications to IT/Admin/Manager. Webhook handlers cho IT ticket resolved, LMS course completed |
| C | Dashboard: checklist management UI, stakeholder task view. Mock LMS + IT panels |

**Deliverable:** HR creates employee → AI generates plan → approve → IT/Admin/Manager get tasks on Slack → mock systems can send completion back.

### Tuần 5: Reminders + Analytics

| Người | Tasks |
|-------|-------|
| A | Sentiment analysis trên conversations (Gemini classify). Content gap detection (weekly clustering). Health score calculation |
| B | Reminder scheduler (pg_cron 8h sáng): 24h → NV, 48h → Manager, 72h → HR. Webhook out for overdue events |
| C | Dashboard: bottleneck heatmap, sentiment trend, content gap tab, health score per employee |

**Deliverable:** Auto-reminders working. Dashboard shows bottlenecks, sentiment, content gaps.

### Tuần 6: HR Copilot + Polish

| Người | Tasks |
|-------|-------|
| A | HR Copilot: AI tóm tắt + suggested actions. Action buttons (assign buddy, escalate IT, schedule check-in) |
| B | End-to-end testing toàn flow. Webhook retry logic. Error handling |
| C | Dashboard polish, export report, demo data preparation, backup video recording |
| Chung | Demo rehearsal (ít nhất 3 lần). Slide preparation |

**Deliverable:** Production-ready demo. Full flow works end-to-end.

---

## 8. Success Metrics

| Metric | Cách đo | Target v1 |
|--------|---------|-----------|
| Chatbot accuracy | Test 50 câu hỏi thực tế, đánh giá manual | ≥ 80% |
| Chatbot response time | Log timestamp | < 5 giây |
| End-to-end flow | HRIS webhook → onboarding complete | Chạy mượt trong demo |
| Stakeholder notification | Plan approve → Slack messages sent | < 30 giây |
| Bottleneck detection | Seed data 10 NV, 3 NV stuck cùng task | Hiện đúng trên dashboard |
| Content gap | Hỏi 10 câu không có trong KB → cluster đúng topics | ≥ 3 clusters chính xác |
| Sentiment accuracy | Test 20 conversations với sentiment rõ ràng | ≥ 75% |

---

## 9. Demo Script — 5 phút

### Phút 1: Mở đầu bằng pain point

"Chị Lan, HR Manager, mỗi tháng mất 3 ngày chỉ để trả lời cùng 200 câu hỏi. Bạn Minh, ngày đầu đi làm, overwhelmed không biết hỏi ai. Hệ thống này giải quyết cả hai."

### Phút 2: Demo flow tự động

Nhấn "HRIS: Tạo NV mới" trên mock panel → Show Slack: bot gửi welcome message + checklist xuất hiện. "Toàn bộ tự động — HR không cần làm gì."

### Phút 3: Demo AI Agent

Mở Slack, gõ hỏi bot: "Chính sách nghỉ phép thế nào?" → Bot trả lời với citation.

Gõ tiếp: "Tôi cần làm gì tiếp?" → Bot trả lời từ checklist: "Ưu tiên Security Training, deadline ngày mai."

Gõ: "Tôi chưa có Jira" → Bot tạo task IT + reply "Đã gửi yêu cầu cho IT."

### Phút 4: Demo HR Dashboard

Mở dashboard → Show overview batch → Chỉ NV đỏ → Click "Tóm tắt AI" → AI phân tích nguyên nhân + đề xuất → Click action button → Slack gửi notification.

Show content gap tab: "Hệ thống tự phát hiện thiếu docs về bảo hiểm — và tự cải thiện."

### Phút 5: Kiến trúc + tổng kết

Show architecture diagram: "Module này cắm vào HRIS, LMS, IT Ops hiện có — không thay thế, mà bổ sung intelligence."

Số liệu: "Test 50 câu hỏi, accuracy 82%. Ước tính tiết kiệm 15 giờ HR/batch."

---

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| RAG quality thấp cho tiếng Việt | Chatbot trả lời sai | Chunk 300 token (nhỏ hơn EN), test 50 câu hỏi, tune threshold |
| Gemini hallucination | NV nhận sai thông tin | Strict RAG-only mode, confidence threshold, fallback "Liên hệ HR" |
| Slack API rate limit | Bot chậm hoặc miss messages | Queue messages, batch notifications |
| Demo day API down | Không demo được | Record backup video toàn flow |
| Knowledge base quá ít | Bot không trả lời được nhiều câu | Viết 35-40 docs trước, cover top 50 câu hỏi phổ biến |
| Webhook integration phức tạp | Không kịp timeline | Mock panel thay thế, chỉ cần 3 nút simulate |

---

## 11. Những gì KHÔNG làm trong v1

- ❌ Microsoft Teams integration (chỉ Slack trước)
- ❌ HRIS/LMS thật (dùng mock panel)
- ❌ Adaptive learning path (checklist static sau khi approve)
- ❌ Gamification
- ❌ Multi-company / multi-tenant
- ❌ Mobile app
- ❌ E-signature thật (chỉ upload file)
- ❌ Knowledge graph
- ❌ Video transcript ingestion

---

## 12. Từ v1 đến v2 — Roadmap tương lai

| Phase | Timeline | Features |
|-------|----------|----------|
| v1.0 | 6 tuần | 10 UC core + mock integrations |
| v1.1 | +2 tuần | Teams integration, real Confluence sync |
| v2.0 | +4 tuần | Real HRIS integration, LMS auto-enroll, adaptive checklist |
| v3.0 | +6 tuần | Knowledge graph, video ingestion, multi-tenant, cross-batch analytics |
