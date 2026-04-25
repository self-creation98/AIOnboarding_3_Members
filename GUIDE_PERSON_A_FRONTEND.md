# 🎨 Guide cho Person A — Frontend Developer

> Tài liệu hướng dẫn sử dụng Backend API để build Frontend (Dashboard, Mock Panel, Preboarding Portal).

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

- Swagger UI (xem + test API): **http://localhost:8000/docs**
- Health check: `GET http://localhost:8000/api/health`

---

## 2. Response Format

**Tất cả** endpoints trả về format nhất quán:

```json
// Thành công
{ "success": true, "data": { ... } }

// Lỗi
{ "success": false, "error": "Mô tả lỗi" }
```

---

## 3. Authentication

### Login

```typescript
const API_BASE = "http://localhost:8000";

const login = async (email: string, password: string) => {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return res.json(); // { access_token, user, expires_at }
};
```

### Gọi API có auth

```typescript
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
  return res.json();
};
```

### Roles

| vai_tro | Ai dùng |
|---------|---------|
| `hr_admin` | HR — login chính cho Dashboard |
| `nhan_vien_moi` | Nhân viên mới — xem checklist + chat |
| `it_admin` / `quan_ly` | Không cần login — dùng magic link qua email |

---

## 4. Nhiệm vụ của bạn

1. **HR Dashboard** — Overview, employee list, bottleneck alerts, content gaps
2. **Mock Control Panel** — Trigger webhooks (tạo NV, IT resolve, LMS complete)
3. **Preboarding Portal** — Upload/verify giấy tờ
4. **Employee Checklist View** — NV xem tiến độ onboarding

---

## 5. API cho từng trang

### 5.1. Dashboard Overview

```typescript
const overview = await apiCall("/api/analytics/overview");
// data: { total_employees, in_progress, completed, health_distribution, ... }
```

### 5.2. Employee List

```typescript
// Tất cả NV đang onboarding
const employees = await apiCall("/api/employees?status=in_progress");

// Filter theo department
const engEmployees = await apiCall("/api/employees?department=Engineering");
```

### 5.3. Employee Detail + Analytics

```typescript
const employee = await apiCall(`/api/employees/${id}`);
const analytics = await apiCall(`/api/analytics/employee/${id}`);
const checklist = await apiCall(`/api/employees/${id}/checklist`);
```

### 5.4. Bottleneck Tab

```typescript
const bottlenecks = await apiCall("/api/analytics/bottlenecks");
// data: [{ task_title, stuck_count, avg_overdue_days, employees: [...] }]
```

### 5.5. Content Gaps

```typescript
const gaps = await apiCall("/api/analytics/content-gaps");
// data: [{ topic, question_count, sample_questions: [...] }]
```

### 5.6. HR Copilot (AI phân tích)

```typescript
const analysis = await apiCall("/api/analytics/copilot", {
  method: "POST",
  body: JSON.stringify({ employee_id: "uuid-here" }),
});
// data: { summary, risk_factors, suggestions }
```

### 5.7. Preboarding Portal

```typescript
// Xem documents NV
const docs = await apiCall(`/api/preboarding/${employeeId}`);

// Upload file (dùng FormData, KHÔNG dùng JSON)
const formData = new FormData();
formData.append("document_type", "cmnd");
formData.append("file", fileInput.files[0]);

const uploaded = await fetch(`${API_BASE}/api/preboarding/${employeeId}/upload`, {
  method: "POST",
  headers: { Authorization: `Bearer ${token}` },
  body: formData, // KHÔNG set Content-Type — browser tự set boundary
});

// HR xác nhận hợp lệ
await apiCall(`/api/preboarding/${employeeId}/verify/${docId}`, {
  method: "POST",
  body: JSON.stringify({ verified_by: "hr-user-id" }),
});
```

### 5.8. Stakeholder Tasks

```typescript
// Xem tasks theo team
const itTasks = await apiCall("/api/stakeholder-tasks?team=it");
const summary = await apiCall("/api/stakeholder-tasks/summary");
```

### 5.9. HR Actions

```typescript
// Gửi reminder
await apiCall("/api/actions/send-reminder", {
  method: "POST",
  body: JSON.stringify({ employee_id: "uuid", message: "..." }),
});

// Assign buddy
await apiCall("/api/actions/assign-buddy", {
  method: "POST",
  body: JSON.stringify({ employee_id: "uuid", buddy_id: "uuid" }),
});
```

---

## 6. Mock Control Panel — Webhook Triggers

> [!TIP]
> Các webhook endpoint **KHÔNG cần auth** — gọi thẳng không cần token.

### Nút "HRIS: Tạo NV mới"

```typescript
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
```

### Nút "IT: Resolve Ticket"

```typescript
await fetch(`${API_BASE}/api/webhooks/it/ticket-resolved`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    ticket_id: "IT-1234",
    employee_id: "uuid-here",  // lấy từ employee list
    task_type: "email_setup",
    resolved_by: "it_admin@company.com",
  }),
});
```

### Nút "LMS: Course Done"

```typescript
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

---

## 7. CORS

Backend đã cấu hình CORS cho `localhost:3000`. Nếu frontend chạy port khác, báo Person B sửa.

---

## 8. Full API Reference

Mở **http://localhost:8000/docs** (Swagger UI) để xem chi tiết tất cả 65 endpoints, request body, response schema.

| Nhóm | Endpoints |
|------|-----------|
| Auth | `POST /api/auth/login`, `GET /api/auth/me` |
| Employees | CRUD tại `/api/employees` |
| Checklist | `/api/checklist/generate`, `approve`, `complete` |
| Stakeholder | `/api/stakeholder-tasks` |
| Preboarding | `/api/preboarding/{emp_id}/upload`, `verify`, `reject` |
| Analytics | `/api/analytics/overview`, `bottlenecks`, `content-gaps`, `copilot` |
| Actions | `/api/actions/send-reminder`, `assign-buddy`, `escalate-it` |
| Webhooks | `/api/webhooks/hris/new-employee`, `it/ticket-resolved`, `lms/course-completed` |
