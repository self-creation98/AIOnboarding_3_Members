import { useState, useRef, useEffect, useCallback } from "react";

// ─── API Client Layer (maps to backend schemas.py + all routers) ───
// Backend URL - uses environment variable in production, fallback to local
const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

const apiClient = {
  token: null,
  setToken(t) { this.token = t; },
  async req(method, path, body) {
    const headers = { "Content-Type": "application/json" };
    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;
    try {
      const r = await fetch(`${API_BASE}${path}`, {
        method, headers, body: body ? JSON.stringify(body) : undefined,
      });
      return await r.json();
    } catch {
      return { success: false, error: "Network error — backend không phản hồi" };
    }
  },
  // auth.py — try backend first, fallback mock
  async login(email, password) {
    // 1. Try real backend auth (OAuth2 form-data)
    try {
      const formBody = new URLSearchParams();
      formBody.append("username", email);
      formBody.append("password", password);
      const r = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: formBody.toString(),
      });
      const res = await r.json();
      if (res.access_token) return res;
      // Backend responded but auth failed — return the real error
      if (r.status >= 400) return { detail: res.detail || "Đăng nhập thất bại" };
    } catch {
      // Backend offline — fall through to mock
    }
    // 2. Fallback mock (only when backend is offline)
    await new Promise(r => setTimeout(r, 400));
    const MOCK_ACCOUNTS = [
      { email: "admin@company.com", password: "password123", vai_tro: "hr_admin", full_name: "Lê Minh Châu", id: "u1", role: "HR Specialist", department: "HR" },
      { email: "manager@company.com", password: "password123", vai_tro: "quan_ly", full_name: "Trần Văn Manager", id: "u2", role: "Engineering Manager", department: "Engineering" },
      { email: "it@company.com", password: "password123", vai_tro: "it_admin", full_name: "Nguyễn IT Admin", id: "u3", role: "IT Administrator", department: "IT" },
      { email: "nv@company.com", password: "password123", vai_tro: "nhan_vien_moi", full_name: "Nguyễn Văn An", id: "u4", role: "Software Engineer", department: "Engineering" },
    ];
    const found = MOCK_ACCOUNTS.find(a => a.email === email && a.password === password);
    if (found) {
      const { password: _, ...user } = found;
      return { access_token: "mock-jwt-token-" + Date.now(), user };
    }
    return { detail: "Email hoặc mật khẩu không đúng. Vui lòng thử lại." };
  },
  async getMe() { return this.req("GET", "/api/auth/me"); },
  // employees.py
  async listEmployees(params = {}) {
    const q = new URLSearchParams(params).toString();
    return this.req("GET", `/api/employees${q ? "?" + q : ""}`);
  },
  async createEmployee(data) { return this.req("POST", "/api/employees", data); },
  async updateEmployee(id, data) { return this.req("PATCH", `/api/employees/${id}`, data); },
  async deleteEmployee(id) { return this.req("DELETE", `/api/employees/${id}`); },
  // checklist.py
  async generateChecklist(employee_id) { return this.req("POST", "/api/checklist/generate", { employee_id }); },
  async getPlan(plan_id) { return this.req("GET", `/api/checklist/${plan_id}`); },
  async approvePlan(plan_id, approved_by) { return this.req("POST", `/api/checklist/${plan_id}/approve`, { approved_by }); },
  async completeItem(item_id, completed_by) { return this.req("PATCH", `/api/checklist/items/${item_id}/complete`, { completed_by }); },
  async getEmployeeChecklist(employee_id) { return this.req("GET", `/api/employees/${employee_id}/checklist`); },
  // chat.py
  async sendChat(employee_id, message) { return this.req("POST", "/api/chat", { employee_id, message }); },
  async getChatHistory(employee_id) { return this.req("GET", `/api/chat/history/${employee_id}`); },
  async sendFeedback(message_id, feedback) { return this.req("POST", "/api/chat/feedback", { message_id, feedback }); },
  // preboarding.py
  async getPreboarding(employee_id) { return this.req("GET", `/api/preboarding/${employee_id}`); },
  async verifyDoc(employee_id, document_id, verified_by) {
    return this.req("POST", `/api/preboarding/${employee_id}/verify/${document_id}`, { verified_by });
  },
  async rejectDoc(employee_id, document_id, rejected_reason) {
    return this.req("POST", `/api/preboarding/${employee_id}/reject/${document_id}`, { rejected_reason });
  },
  // reminders.py
  async runReminders() { return this.req("POST", "/api/reminders/run"); },
  async getReminderStats() { return this.req("GET", "/api/reminders/stats"); },
  // actions.py
  async assignBuddy(employee_id) { return this.req("POST", "/api/actions/assign-buddy", { employee_id }); },
  async escalateIt(employee_id) { return this.req("POST", "/api/actions/escalate-it", { employee_id }); },
  async scheduleCheckin(employee_id, note) { return this.req("POST", "/api/actions/schedule-checkin", { employee_id, note }); },
  async sendReminder(employee_id, custom_message) { return this.req("POST", "/api/actions/send-reminder", { employee_id, custom_message }); },
  // analytics.py
  async getOverview() { return this.req("GET", "/api/analytics/overview"); },
  async getBottlenecks(min) { return this.req("GET", `/api/analytics/bottlenecks?min_affected=${min||2}`); },
  async getContentGaps() { return this.req("GET", "/api/analytics/content-gaps"); },
  async getChatbotStats() { return this.req("GET", "/api/analytics/chatbot-stats"); },
  async getEmployeeAnalytics(id) { return this.req("GET", `/api/analytics/employee/${id}`); },
  async getCopilot(employee_id) { return this.req("POST", "/api/analytics/copilot", { employee_id }); },
  async recalculateHealth() { return this.req("POST", "/api/analytics/recalculate-health", {}); },
  // documents.py
  async uploadDocument(data) { return this.req("POST", "/api/documents/upload", data); },
  async listKBDocuments() { return this.req("GET", "/api/documents"); },
  // webhooks — mock panel
  async triggerWebhook(endpoint, data) { return this.req("POST", `/api/webhooks/${endpoint}`, data); },
  // stakeholder
  async getStakeholderTasks(eid) { return this.req("GET", `/api/stakeholder-tasks/employee/${eid}`); },
};

// ─── Design tokens (navy-anchored) ───
const C = {
  navy: "#1a237e", navyDark: "#0d1459", navyMid: "#283593", navyLight: "#3949ab",
  navyGhost: "#e8eaf6", navyFaint: "#f3f4ff",
  accent: "#5c6bc0", accentSoft: "#c5cae9",
  white: "#ffffff", bg: "#f0f2fb", bgCard: "#ffffff",
  text: "#1a237e", textMid: "#455a64", textLight: "#90a4ae",
  border: "#dde1f0", borderLight: "#eef0fa",
  success: "#1b5e20", successMid: "#2e7d32", successBg: "#e8f5e9", successBorder: "#a5d6a7",
  warn: "#bf360c", warnBg: "#fff8e1", warnBorder: "#ffe082",
  danger: "#b71c1c", dangerBg: "#ffebee", dangerBorder: "#ef9a9a",
  info: "#01579b", infoBg: "#e1f5fe", infoBorder: "#81d4fa",
  orange: "#e65100", orangeBg: "#fff3e0",
};

const GS = `
  @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800&family=DM+Mono:wght@400;500&family=Playfair+Display:wght@700;800&display=swap');
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; font-family: 'Nunito', sans-serif; background: ${C.bg}; color: ${C.text}; -webkit-font-smoothing: antialiased; }
  ::-webkit-scrollbar { width: 5px; height: 5px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: ${C.accentSoft}; border-radius: 3px; }
  input, textarea, select { font-family: 'Nunito', sans-serif; font-size: 14px; border: 1.5px solid ${C.border}; border-radius: 8px; padding: 8px 12px; outline: none; background: ${C.white}; color: ${C.text}; transition: border-color .15s, box-shadow .15s; width: 100%; }
  input:focus, textarea:focus, select:focus { border-color: ${C.navy}; box-shadow: 0 0 0 3px rgba(26,35,126,.08); }
  button { font-family: 'Nunito', sans-serif; cursor: pointer; }
  @keyframes spin { to { transform: rotate(360deg); } }
  @keyframes fadeIn { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }
  @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.4; } }
  @keyframes bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-5px)} }
  @keyframes slideIn { from { transform:translateX(-8px); opacity:0; } to { transform:translateX(0); opacity:1; } }
  @keyframes loginFadeUp { from { opacity:0; transform:translateY(28px); } to { opacity:1; transform:translateY(0); } }
  @keyframes loginSlideLeft { from { opacity:0; transform:translateX(40px); } to { opacity:1; transform:translateX(0); } }
  @keyframes floatOrb { 0%,100% { transform:translate(0,0) scale(1); } 33% { transform:translate(30px,-20px) scale(1.05); } 66% { transform:translate(-20px,15px) scale(.96); } }
  @keyframes floatOrb2 { 0%,100% { transform:translate(0,0) scale(1); } 33% { transform:translate(-25px,20px) scale(1.08); } 66% { transform:translate(20px,-10px) scale(.93); } }
  @keyframes shimmer { from { background-position: -200% 0; } to { background-position: 200% 0; } }
  @keyframes gridFlow { from { opacity:0; } to { opacity:.07; } }
  .login-input { transition: border-color .2s, box-shadow .2s, background .2s !important; }
  .login-input:focus { border-color: rgba(255,255,255,.7) !important; box-shadow: 0 0 0 3px rgba(255,255,255,.12) !important; background: rgba(255,255,255,.18) !important; }
  .login-btn:hover { transform: translateY(-1px); box-shadow: 0 8px 32px rgba(0,0,0,.3) !important; }
  .login-btn:active { transform: translateY(0); }
  .login-btn { transition: all .2s ease !important; }
  .quick-acc:hover { background: rgba(255,255,255,.14) !important; border-color: rgba(255,255,255,.3) !important; }
  .quick-acc { transition: all .15s ease !important; }
`;

// ─── Primitives ───
const Spinner = ({ size = 16 }) => (
  <div style={{ width: size, height: size, border: `2px solid rgba(255,255,255,.3)`, borderTopColor: C.white, borderRadius: "50%", animation: "spin .7s linear infinite", flexShrink: 0 }} />
);

const Badge = ({ color = "navy", size = "sm", children }) => {
  const map = {
    navy: [C.navyGhost, C.navy], green: [C.successBg, C.successMid], orange: [C.orangeBg, C.orange],
    red: [C.dangerBg, C.danger], blue: [C.infoBg, C.info], gray: ["#eceff1", "#546e7a"],
    yellow: [C.warnBg, C.warn],
  };
  const [bg, text] = map[color] || map.navy;
  return (
    <span style={{ background: bg, color: text, fontSize: size === "xs" ? 10 : 11, fontWeight: 700, letterSpacing: 0.5, padding: size === "xs" ? "2px 6px" : "3px 9px", borderRadius: 20, whiteSpace: "nowrap", textTransform: "uppercase" }}>
      {children}
    </span>
  );
};

const statusColorMap = s => {
  const m = { completed: "green", hoan_thanh: "green", verified: "green", da_duyet: "green", in_progress: "blue", dang_lam: "blue", dang_thuc_hien: "blue", uploaded: "blue", pre_boarding: "orange", chua_bat_dau: "orange", missing: "orange", ban_thao: "yellow", rejected: "red", terminated: "red", red: "red", yellow: "yellow", green: "green", pending: "orange" };
  return m[s] || "gray";
};

const statusLabel = s => {
  const m = { pre_boarding: "Pre-boarding", in_progress: "Đang onboard", completed: "Hoàn thành", terminated: "Đã nghỉ", ban_thao: "Bản thảo", da_duyet: "Đã duyệt", hoan_thanh: "Hoàn thành", chua_bat_dau: "Chưa bắt đầu", dang_lam: "Đang làm", verified: "Hợp lệ", uploaded: "Đã nộp", missing: "Thiếu", rejected: "Từ chối", pending: "Chờ xử lý", green: "Tốt", yellow: "Chú ý", red: "Cần xử lý" };
  return m[s] || s?.replace(/_/g, " ");
};

const Btn = ({ children, onClick, variant = "primary", size = "md", loading, disabled, icon, style: sx = {} }) => {
  const sizes = { xs: { padding: "4px 10px", fontSize: 12, gap: 4 }, sm: { padding: "6px 13px", fontSize: 13, gap: 5 }, md: { padding: "9px 18px", fontSize: 14, gap: 6 }, lg: { padding: "11px 24px", fontSize: 15, gap: 7 } };
  const variants = {
    primary: { background: C.navy, color: C.white, border: "none" },
    secondary: { background: C.navyGhost, color: C.navy, border: "none" },
    ghost: { background: "transparent", color: C.textMid, border: `1.5px solid ${C.border}` },
    danger: { background: C.dangerBg, color: C.danger, border: `1px solid ${C.dangerBorder}` },
    success: { background: C.successBg, color: C.successMid, border: `1px solid ${C.successBorder}` },
    warning: { background: C.warnBg, color: C.warn, border: `1px solid ${C.warnBorder}` },
    info: { background: C.infoBg, color: C.info, border: `1px solid ${C.infoBorder}` },
  };
  return (
    <button onClick={onClick} disabled={disabled || loading} style={{
      ...variants[variant], ...sizes[size], borderRadius: 8, fontWeight: 600,
      cursor: disabled || loading ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1, display: "inline-flex", alignItems: "center",
      justifyContent: "center", gap: sizes[size].gap, transition: "all .15s",
      flexShrink: 0, ...sx,
    }}>
      {loading ? <Spinner size={14} /> : icon && <span style={{ fontSize: 14 }}>{icon}</span>}
      {children}
    </button>
  );
};

const Card = ({ children, style: sx = {}, onClick }) => (
  <div onClick={onClick} style={{ background: C.bgCard, borderRadius: 12, border: `1px solid ${C.border}`, padding: "20px 22px", animation: "fadeIn .2s ease", cursor: onClick ? "pointer" : "default", ...sx }}>
    {children}
  </div>
);

const Modal = ({ title, onClose, children, width = 520 }) => (
  <div style={{ position: "fixed", inset: 0, background: "rgba(8,15,70,.48)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 2000, padding: 16, backdropFilter: "blur(2px)" }}>
    <div style={{ background: C.white, borderRadius: 14, width: "100%", maxWidth: width, maxHeight: "88vh", overflow: "auto", boxShadow: "0 24px 80px rgba(26,35,126,.22)", animation: "fadeIn .18s ease" }}>
      <div style={{ padding: "18px 22px", borderBottom: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between", alignItems: "center", position: "sticky", top: 0, background: C.white, zIndex: 1 }}>
        <h3 style={{ fontSize: 16, fontWeight: 700 }}>{title}</h3>
        <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 22, color: C.textLight, cursor: "pointer", lineHeight: 1, padding: "0 4px" }}>×</button>
      </div>
      <div style={{ padding: "18px 22px" }}>{children}</div>
    </div>
  </div>
);

const Field = ({ label, required, children, hint }) => (
  <div style={{ marginBottom: 14 }}>
    <label style={{ display: "block", fontSize: 12, fontWeight: 700, color: C.textMid, marginBottom: 5, letterSpacing: 0.4, textTransform: "uppercase" }}>
      {label}{required && <span style={{ color: C.danger, marginLeft: 3 }}>*</span>}
    </label>
    {children}
    {hint && <p style={{ fontSize: 11, color: C.textLight, marginTop: 4 }}>{hint}</p>}
  </div>
);

const Avatar = ({ name, size = 34 }) => {
  const initials = (name || "?").split(" ").slice(0, 2).map(w => w[0]).join("").toUpperCase();
  const hue = (name || "").charCodeAt(0) * 17 % 360;
  return (
    <div style={{ width: size, height: size, borderRadius: "50%", background: `hsl(${hue},45%,88%)`, color: `hsl(${hue},45%,30%)`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: size * 0.36, fontWeight: 700, flexShrink: 0 }}>
      {initials}
    </div>
  );
};

const Toast = ({ message, type = "success", onClose }) => {
  useEffect(() => { const t = setTimeout(onClose, 3500); return () => clearTimeout(t); }, []);
  const colors = { success: [C.successBg, C.successMid, C.successBorder], error: [C.dangerBg, C.danger, C.dangerBorder], info: [C.infoBg, C.info, C.infoBorder], warn: [C.warnBg, C.warn, C.warnBorder] };
  const [bg, text, border] = colors[type] || colors.info;
  const icons = { success: "✓", error: "✕", info: "ℹ", warn: "⚠" };
  return (
    <div style={{ position: "fixed", top: 20, right: 20, zIndex: 9999, background: bg, color: text, border: `1px solid ${border}`, borderRadius: 10, padding: "12px 18px", maxWidth: 340, display: "flex", gap: 10, alignItems: "flex-start", boxShadow: "0 6px 24px rgba(0,0,0,.12)", animation: "fadeIn .2s ease" }}>
      <span style={{ fontWeight: 800, fontSize: 15, flexShrink: 0 }}>{icons[type]}</span>
      <p style={{ fontSize: 13, fontWeight: 600, lineHeight: 1.5 }}>{message}</p>
      <button onClick={onClose} style={{ background: "none", border: "none", color: text, cursor: "pointer", fontSize: 16, marginLeft: "auto", opacity: 0.6, flexShrink: 0 }}>×</button>
    </div>
  );
};

const InfoBox = ({ type = "info", children }) => {
  const colors = { info: [C.infoBg, C.info, C.infoBorder], warn: [C.warnBg, C.warn, C.warnBorder], success: [C.successBg, C.successMid, C.successBorder] };
  const [bg, text, border] = colors[type];
  const icons = { info: "ℹ️", warn: "⚠️", success: "✅" };
  return (
    <div style={{ background: bg, border: `1px solid ${border}`, borderRadius: 8, padding: "10px 14px", fontSize: 13, color: text, lineHeight: 1.5, display: "flex", gap: 8 }}>
      <span style={{ flexShrink: 0 }}>{icons[type]}</span>
      <div>{children}</div>
    </div>
  );
};

// ─── Auth Context ───
const useAuth = () => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const login = async (email, password) => {
    setLoading(true); setError("");
    const res = await apiClient.login(email, password);
    setLoading(false);
    if (res.access_token) {
      apiClient.setToken(res.access_token);
      setToken(res.access_token);
      setUser(res.user);
      return true;
    }
    setError(res.detail || "Đăng nhập thất bại");
    return false;
  };

  const logout = () => { apiClient.setToken(null); setToken(null); setUser(null); };
  return { user, token, loading, error, login, logout };
};

// ─── Login Page ───
const LoginPage = ({ onLogin, loading, error }) => {
  const [email, setEmail] = useState("admin@company.com");
  const [password, setPassword] = useState("password123");
  const [showPass, setShowPass] = useState(false);
  const [focused, setFocused] = useState(null);



  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: `linear-gradient(145deg, #0a0f3d 0%, #1a237e 45%, #1565c0 100%)`,
      position: "relative", overflow: "hidden",
    }}>
      {/* Animated background orbs */}
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "hidden" }}>
        <div style={{ position: "absolute", top: "-10%", left: "-5%", width: 500, height: 500, borderRadius: "50%", background: "radial-gradient(circle, rgba(63,81,181,.45) 0%, transparent 70%)", animation: "floatOrb 12s ease-in-out infinite" }} />
        <div style={{ position: "absolute", bottom: "-15%", right: "-8%", width: 600, height: 600, borderRadius: "50%", background: "radial-gradient(circle, rgba(21,101,192,.4) 0%, transparent 70%)", animation: "floatOrb2 15s ease-in-out infinite" }} />
        <div style={{ position: "absolute", top: "40%", right: "15%", width: 280, height: 280, borderRadius: "50%", background: "radial-gradient(circle, rgba(100,120,220,.25) 0%, transparent 70%)", animation: "floatOrb 18s ease-in-out infinite reverse" }} />
        {/* Subtle dot grid */}
        <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", animation: "gridFlow 1s ease forwards" }} xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="dots" x="0" y="0" width="32" height="32" patternUnits="userSpaceOnUse">
              <circle cx="1" cy="1" r="1" fill="rgba(255,255,255,.35)" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#dots)" />
        </svg>
      </div>

      {/* Main layout: two-column on wide screens, single on narrow */}
      <div style={{ position: "relative", zIndex: 1, display: "flex", alignItems: "center", gap: 64, padding: "32px 24px", maxWidth: 900, width: "100%" }}>

        {/* Left: branding */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 28, animation: "loginFadeUp .6s ease both" }}>
          {/* Logo */}
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{
              width: 52, height: 52, borderRadius: 16, border: "1.5px solid rgba(255,255,255,.25)",
              background: "rgba(255,255,255,.1)", backdropFilter: "blur(8px)",
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24,
            }}>🚀</div>
            <div>
              <p style={{ color: "rgba(255,255,255,.5)", fontSize: 11, fontWeight: 700, letterSpacing: 2, textTransform: "uppercase", marginBottom: 2 }}>Nền tảng</p>
              <p style={{ color: C.white, fontSize: 20, fontWeight: 800, letterSpacing: -0.3 }}>OnBoard AI</p>
            </div>
          </div>

          {/* Headline */}
          <div>
            <h1 style={{ fontFamily: "'Playfair Display', Georgia, serif", color: C.white, fontSize: 42, fontWeight: 800, lineHeight: 1.15, letterSpacing: -1 }}>
              Chào mừng<br />trở lại 👋
            </h1>
            <p style={{ color: "rgba(255,255,255,.55)", fontSize: 15, marginTop: 14, lineHeight: 1.7, maxWidth: 340 }}>
              Hệ thống quản lý onboarding thông minh — theo dõi tiến trình, phân công và tự động hóa toàn bộ quy trình.
            </p>
          </div>


        </div>

        {/* Right: login card */}
        <div style={{
          width: "100%", maxWidth: 400, flexShrink: 0,
          background: "rgba(255,255,255,.07)", border: "1px solid rgba(255,255,255,.14)",
          borderRadius: 24, backdropFilter: "blur(24px)",
          padding: "36px 32px 28px",
          boxShadow: "0 32px 80px rgba(0,0,0,.4), inset 0 1px 0 rgba(255,255,255,.12)",
          animation: "loginSlideLeft .65s ease both",
        }}>
          {/* Card header */}
          <div style={{ marginBottom: 28 }}>
            <h2 style={{ color: C.white, fontSize: 22, fontWeight: 800, letterSpacing: -0.3 }}>Đăng nhập</h2>
            <p style={{ color: "rgba(255,255,255,.45)", fontSize: 13, marginTop: 4 }}>Nhập thông tin tài khoản của bạn</p>
          </div>

          {/* Error */}
          {error && (
            <div style={{
              background: "rgba(183,28,28,.2)", border: "1px solid rgba(239,154,154,.3)",
              borderRadius: 10, padding: "10px 14px", fontSize: 13, color: "#ffcdd2",
              marginBottom: 20, fontWeight: 600, display: "flex", gap: 8, alignItems: "center",
              animation: "loginFadeUp .2s ease",
            }}>
              <span style={{ fontSize: 16 }}>⚠</span> {error}
            </div>
          )}

          {/* Email field */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,.55)", marginBottom: 7, letterSpacing: 0.8, textTransform: "uppercase" }}>
              Email <span style={{ color: "#ef9a9a" }}>*</span>
            </label>
            <div style={{ position: "relative" }}>
              <span style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", fontSize: 15, opacity: .5, pointerEvents: "none" }}>✉</span>
              <input
                className="login-input"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                onFocus={() => setFocused("email")}
                onBlur={() => setFocused(null)}
                placeholder="email@company.com"
                style={{
                  background: "rgba(255,255,255,.1)", border: `1.5px solid ${focused === "email" ? "rgba(255,255,255,.6)" : "rgba(255,255,255,.18)"}`,
                  color: C.white, borderRadius: 12, padding: "11px 14px 11px 40px",
                  fontSize: 14, width: "100%",
                }}
              />
            </div>
          </div>

          {/* Password field */}
          <div style={{ marginBottom: 8 }}>
            <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,.55)", marginBottom: 7, letterSpacing: 0.8, textTransform: "uppercase" }}>
              Mật khẩu <span style={{ color: "#ef9a9a" }}>*</span>
            </label>
            <div style={{ position: "relative" }}>
              <span style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)", fontSize: 15, opacity: .5, pointerEvents: "none" }}>🔒</span>
              <input
                className="login-input"
                type={showPass ? "text" : "password"}
                value={password}
                onChange={e => setPassword(e.target.value)}
                onFocus={() => setFocused("pass")}
                onBlur={() => setFocused(null)}
                onKeyDown={e => e.key === "Enter" && onLogin(email, password)}
                placeholder="••••••••"
                style={{
                  background: "rgba(255,255,255,.1)", border: `1.5px solid ${focused === "pass" ? "rgba(255,255,255,.6)" : "rgba(255,255,255,.18)"}`,
                  color: C.white, borderRadius: 12, padding: "11px 44px 11px 40px",
                  fontSize: 14, width: "100%",
                }}
              />
              <button
                onClick={() => setShowPass(p => !p)}
                style={{ position: "absolute", right: 14, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: "rgba(255,255,255,.45)", fontSize: 16, padding: 0, cursor: "pointer", lineHeight: 1 }}
              >
                {showPass ? "🙈" : "👁"}
              </button>
            </div>
          </div>

          {/* CTA */}
          <button
            className="login-btn"
            onClick={() => onLogin(email, password)}
            disabled={loading || !email || !password}
            style={{
              width: "100%", marginTop: 20, padding: "13px",
              background: loading || !email || !password
                ? "rgba(255,255,255,.15)"
                : "linear-gradient(135deg, #5c6bc0 0%, #3949ab 100%)",
              border: "none", borderRadius: 12, color: C.white,
              fontSize: 15, fontWeight: 800, letterSpacing: 0.2,
              cursor: loading || !email || !password ? "not-allowed" : "pointer",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              boxShadow: "0 4px 20px rgba(57,73,171,.5)",
            }}
          >
            {loading ? <Spinner size={16} /> : null}
            {loading ? "Đang đăng nhập..." : "Đăng nhập →"}
          </button>


        </div>
      </div>
    </div>
  );
};

// ─── Sidebar ───
const MENU = [
  { id: "welcome", icon: "🏠", label: "Trang chủ", roles: ["nhan_vien_moi"] },
  { id: "dashboard", icon: "📊", label: "Dashboard", roles: ["hr_admin", "quan_ly"] },
  { id: "employees", icon: "👥", label: "Nhân viên", roles: ["hr_admin", "quan_ly"] },
  { id: "checklist", icon: "✅", label: "Checklist", roles: ["hr_admin", "quan_ly", "nhan_vien_moi"] },
  { id: "preboarding", icon: "📄", label: "Giấy tờ", roles: ["hr_admin", "nhan_vien_moi"] },
  { id: "chat", icon: "💬", label: "AI Chatbot", roles: ["hr_admin", "quan_ly", "nhan_vien_moi", "it_admin"] },
  { id: "reminders", icon: "🔔", label: "Nhắc nhở", roles: ["hr_admin"] },
  { id: "mock_panel", icon: "🧪", label: "Mock Panel", roles: ["hr_admin"] },
];

const Sidebar = ({ active, onNav, user, onLogout }) => {
  const allowed = MENU.filter(m => m.roles.includes(user?.vai_tro));
  const isNewHire = roleIs(user, "nhan_vien_moi");
  const roleLabel = { hr_admin: "HR Admin", quan_ly: "Quản lý", nhan_vien_moi: "Nhân viên mới", it_admin: "IT Admin" };

  // Mini progress for NV mới sidebar
  const nvDone = MOCK_CHECKLIST_ITEMS.filter(i => i.status === "hoan_thanh" && i.owner === "new_hire").length;
  const nvTotal = MOCK_CHECKLIST_ITEMS.filter(i => i.owner === "new_hire").length;
  const nvPct = Math.round((nvDone / nvTotal) * 100);

  return (
    <aside style={{ width: 260, background: C.navy, minHeight: "100vh", display: "flex", flexDirection: "column", flexShrink: 0, position: "sticky", top: 0, height: "100vh" }}>
      {/* Logo / brand */}
      <div style={{ padding: "28px 22px 18px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 40, height: 40, borderRadius: 12, background: "rgba(255,255,255,.15)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, flexShrink: 0 }}>🚀</div>
          <div>
            <p style={{ color: C.white, fontWeight: 800, fontSize: 16, lineHeight: 1.2 }}>OnBoard AI</p>
            <p style={{ color: "rgba(255,255,255,.45)", fontSize: 11, letterSpacing: 0.3 }}>
              {isNewHire ? "Hành trình của bạn" : "HR Management"}
            </p>
          </div>
        </div>

        {/* NV mới: mini progress bar trong sidebar */}
        {isNewHire && (
          <div style={{ marginTop: 16, padding: "12px 14px", background: "rgba(255,255,255,.08)", borderRadius: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 7 }}>
              <p style={{ fontSize: 11, color: "rgba(255,255,255,.7)", fontWeight: 700 }}>Checklist của tôi</p>
              <p style={{ fontSize: 12, fontWeight: 800, color: nvPct === 100 ? "#a5d6a7" : C.white }}>{nvPct}%</p>
            </div>
            <div style={{ height: 5, background: "rgba(255,255,255,.15)", borderRadius: 4 }}>
              <div style={{ width: `${nvPct}%`, height: "100%", background: nvPct === 100 ? "#a5d6a7" : "#90caf9", borderRadius: 4, transition: "width .5s ease" }} />
            </div>
            <p style={{ fontSize: 10, color: "rgba(255,255,255,.45)", marginTop: 5 }}>{nvDone}/{nvTotal} mục hoàn thành</p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, padding: "6px 12px", overflowY: "auto" }}>
        {/* Label section cho NV mới */}
        {isNewHire && (
          <p style={{ fontSize: 10, color: "rgba(255,255,255,.3)", fontWeight: 700, letterSpacing: 0.8, textTransform: "uppercase", padding: "6px 10px 4px" }}>Khu vực của bạn</p>
        )}
        {allowed.map(item => {
          const isActive = active === item.id;
          return (
            <button key={item.id} onClick={() => onNav(item.id)} style={{
              width: "100%", display: "flex", alignItems: "center", gap: 11, padding: "11px 13px", borderRadius: 9,
              border: "none", cursor: "pointer", background: isActive ? "rgba(255,255,255,.16)" : "transparent",
              color: isActive ? C.white : "rgba(255,255,255,.65)", fontWeight: isActive ? 700 : 500,
              fontSize: 14, marginBottom: 3, transition: "all .12s", textAlign: "left",
              borderLeft: `3px solid ${isActive ? "rgba(255,255,255,.65)" : "transparent"}`,
            }}>
              <span style={{ fontSize: 17 }}>{item.icon}</span> {item.label}
            </button>
          );
        })}
      </nav>

      {/* User info + logout */}
      <div style={{ padding: "16px 22px", borderTop: "1px solid rgba(255,255,255,.1)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
          <Avatar name={user?.full_name} size={32} />
          <div style={{ minWidth: 0 }}>
            <p style={{ color: C.white, fontSize: 13, fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{user?.full_name}</p>
            <p style={{ color: "rgba(255,255,255,.4)", fontSize: 11 }}>{roleLabel[user?.vai_tro] || user?.vai_tro}</p>
          </div>
        </div>
        <button onClick={onLogout} style={{ width: "100%", background: "rgba(255,255,255,.08)", border: "none", color: "rgba(255,255,255,.6)", fontSize: 13, fontWeight: 600, padding: "8px", borderRadius: 8, cursor: "pointer" }}>
          Đăng xuất
        </button>
      </div>
    </aside>
  );
};

// ─── Mock Data (used when API unavailable) ───
const MOCK_EMP = [
  { id: "e1", employee_code: "NV-2026-001", full_name: "Nguyễn Văn An", email: "an@company.com", role: "Software Engineer", department: "Engineering", seniority: "junior", start_date: "2026-04-20", vai_tro: "nhan_vien_moi", onboarding_status: "in_progress", health_score: "green", completion_percentage: 45 },
  { id: "e2", employee_code: "NV-2026-002", full_name: "Trần Thị Bình", email: "binh@company.com", role: "Product Manager", department: "Product", seniority: "mid", start_date: "2026-04-15", vai_tro: "nhan_vien_moi", onboarding_status: "in_progress", health_score: "yellow", completion_percentage: 72 },
  { id: "e3", employee_code: "NV-2026-003", full_name: "Lê Minh Châu", email: "chau@company.com", role: "HR Specialist", department: "HR", seniority: "senior", start_date: "2026-03-01", vai_tro: "hr_admin", onboarding_status: "completed", health_score: "green", completion_percentage: 100 },
  { id: "e4", employee_code: "NV-2026-004", full_name: "Phạm Đức Dũng", email: "dung@company.com", role: "DevOps Engineer", department: "Engineering", seniority: "mid", start_date: "2026-04-28", vai_tro: "nhan_vien_moi", onboarding_status: "pre_boarding", health_score: "red", completion_percentage: 10 },
];

const MOCK_CHECKLIST_ITEMS = [
  { id: "c1", title: "Chuẩn bị laptop + accounts", category: "tools", week: 0, owner: "it", is_mandatory: true, status: "hoan_thanh", deadline_date: "2026-04-19" },
  { id: "c2", title: "Assign buddy", category: "social", week: 0, owner: "manager", is_mandatory: true, status: "chua_bat_dau", deadline_date: "2026-04-20" },
  { id: "c3", title: "Nộp hồ sơ đầy đủ", category: "admin", week: 1, owner: "new_hire", is_mandatory: true, status: "hoan_thanh", deadline_date: "2026-04-22" },
  { id: "c4", title: "Đọc nội quy công ty", category: "compliance", week: 1, owner: "new_hire", is_mandatory: true, status: "dang_lam", deadline_date: "2026-04-22", is_compliance: true },
  { id: "c5", title: "Security Awareness Training", category: "compliance", week: 1, owner: "new_hire", is_mandatory: true, status: "chua_bat_dau", deadline_date: "2026-04-25", is_compliance: true },
  { id: "c6", title: "Setup dev environment", category: "tools", week: 1, owner: "new_hire", is_mandatory: true, status: "dang_lam", deadline_date: "2026-04-23" },
  { id: "c7", title: "1-on-1 với Manager tuần đầu", category: "role_specific", week: 1, owner: "manager", is_mandatory: true, status: "chua_bat_dau", deadline_date: "2026-04-23" },
  { id: "c8", title: "Set 30-60-90 day goals", category: "role_specific", week: 2, owner: "manager", is_mandatory: true, status: "chua_bat_dau", deadline_date: "2026-04-30" },
];

const MOCK_DOCS = [
  { id: "d1", document_type: "cmnd", document_label: "CMND/CCCD (mặt trước + mặt sau)", status: "verified", filename: "cmnd_nguyen_an.jpg", uploaded_at: "2026-04-18" },
  { id: "d2", document_type: "photo_3x4", document_label: "Ảnh thẻ 3x4", status: "uploaded", filename: "photo_3x4.jpg", uploaded_at: "2026-04-18" },
  { id: "d3", document_type: "so_bhxh", document_label: "Sổ BHXH (nếu có)", status: "missing", filename: null, uploaded_at: null },
  { id: "d4", document_type: "bang_cap", document_label: "Bằng đại học / cao đẳng", status: "rejected", filename: "degree.pdf", uploaded_at: "2026-04-17", rejected_reason: "File bị mờ, vui lòng scan lại rõ hơn" },
  { id: "d5", document_type: "so_tai_khoan", document_label: "Số tài khoản ngân hàng", status: "missing", filename: null, uploaded_at: null },
];

// ─── Role helpers ───
const roleIs = (user, ...roles) => roles.includes(user?.vai_tro);

// ─── Dashboard Page ───
const DashboardPage = ({ user, toast }) => {
  const isHR = roleIs(user, "hr_admin");
  const isManager = roleIs(user, "quan_ly");

  // Render phân vai trò
  if (isManager) return <ManagerDashboard user={user} toast={toast} />;
  return <HRDashboard user={user} toast={toast} />;
};

// ── HR Dashboard (full view) ──
const HRDashboard = ({ user, toast }) => {
  const [stats, setStats] = useState({ total: 4, in_progress: 2, pre_boarding: 1, completed: 1, red: 1 });
  const [reminderStats, setReminderStats] = useState({ today: { tier1: 3, tier2: 1, tier3: 0 }, total: { tier1: 24, tier2: 7, tier3: 2 } });
  const [runningReminder, setRunningReminder] = useState(false);
  const [bottlenecks, setBottlenecks] = useState([]);
  const [contentGaps, setContentGaps] = useState(null);
  const [copilotData, setCopilotData] = useState(null);
  const [copilotLoading, setCopilotLoading] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiClient.getOverview();
        if (res.success) {
          const d = res.data;
          setStats({ total: d.total_onboarding || 0, in_progress: d.total_onboarding - (d.at_risk_count || 0), pre_boarding: 0, completed: d.completed_this_month || 0, red: d.at_risk_count || 0, avg_completion: d.avg_completion || 0, overdue: d.overdue_count || 0, health: d.health_distribution || {} });
        }
      } catch {}
      try {
        const res = await apiClient.getBottlenecks();
        if (res.success) setBottlenecks(res.data || []);
      } catch {}
      try {
        const res = await apiClient.getContentGaps();
        if (res.success) setContentGaps(res.data);
      } catch {}
      try {
        const res = await apiClient.getReminderStats();
        if (res.success && res.data) setReminderStats(res.data);
      } catch {}
    })();
  }, []);

  const handleRunReminders = async () => {
    setRunningReminder(true);
    const res = await apiClient.runReminders();
    setRunningReminder(false);
    if (res.success) toast(`✅ Đã chạy reminders: ${res.data.reminders_sent} tin nhắn gửi đi`, "success");
    else toast("Chạy reminders (mock): 4 nhắc nhở đã gửi cho nhân viên/manager", "info");
  };

  const MetricCard = ({ label, value, color, sublabel }) => (
    <Card style={{ textAlign: "center", padding: "18px 14px" }}>
      <p style={{ fontSize: 28, fontWeight: 800, color: color || C.navy }}>{value}</p>
      <p style={{ fontSize: 13, fontWeight: 600, color: C.textMid, marginTop: 2 }}>{label}</p>
      {sublabel && <p style={{ fontSize: 11, color: C.textLight, marginTop: 3 }}>{sublabel}</p>}
    </Card>
  );

  return (
    <div style={{ animation: "fadeIn .2s ease" }}>
      <div style={{ padding: "24px 0 18px" }}>
        <h2 style={{ fontSize: 22, fontWeight: 800 }}>Dashboard HR</h2>
        <p style={{ color: C.textMid, fontSize: 13, marginTop: 3 }}>Xin chào {user.full_name} · {new Date().toLocaleDateString("vi-VN", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}</p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12, marginBottom: 22 }}>
        <MetricCard label="Tổng nhân viên" value={stats.total} sublabel="đang theo dõi" />
        <MetricCard label="Đang onboard" value={stats.in_progress} color={C.info} sublabel="in progress" />
        <MetricCard label="Pre-boarding" value={stats.pre_boarding} color={C.orange} sublabel="chờ bắt đầu" />
        <MetricCard label="Hoàn thành" value={stats.completed} color={C.successMid} sublabel="tháng này" />
        <MetricCard label="⚠ Cần can thiệp" value={stats.red} color={C.danger} sublabel="health = đỏ" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 22 }}>
        <Card>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <h3 style={{ fontSize: 14, fontWeight: 700 }}>🔔 Reminder System — 3 tầng escalation</h3>
            <Btn size="sm" variant="secondary" onClick={handleRunReminders} loading={runningReminder}>Chạy ngay</Btn>
          </div>
          <InfoBox type="info">
            <strong>Tier 1</strong> (&lt;48h): Nhắc nhân viên trực tiếp<br />
            <strong>Tier 2</strong> (48-72h): Nhắc Manager<br />
            <strong>Tier 3</strong> (&gt;72h): Alert HR + health_score → đỏ
          </InfoBox>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginTop: 12 }}>
            {[{ label: "Tier 1", today: reminderStats.today.tier1, total: reminderStats.total.tier1, c: C.info }, { label: "Tier 2", today: reminderStats.today.tier2, total: reminderStats.total.tier2, c: C.warn }, { label: "Tier 3", today: 0, total: reminderStats.total.tier3, c: C.danger }].map(r => (
              <div key={r.label} style={{ background: C.navyFaint, borderRadius: 8, padding: "10px 12px", textAlign: "center" }}>
                <p style={{ fontSize: 18, fontWeight: 800, color: r.c }}>{r.today}</p>
                <p style={{ fontSize: 10, color: C.textLight, fontWeight: 600 }}>{r.label} hôm nay</p>
                <p style={{ fontSize: 10, color: C.textLight }}>tổng: {r.total}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 14 }}>🔗 Luồng tự động hóa</h3>
          {[
            { icon: "1", label: "HRIS tạo NV mới", desc: "Webhook kích hoạt tự động", status: "auto" },
            { icon: "2", label: "Generate checklist (3 layer)", desc: "AI tạo kế hoạch cá nhân hóa", status: "auto" },
            { icon: "3", label: "HR duyệt plan", desc: "Tạo stakeholder tasks + gửi email magic link", status: "manual" },
            { icon: "4", label: "Stakeholders confirm", desc: "IT/Admin/Manager click magic link", status: "external" },
            { icon: "5", label: "NV hoàn thành checklist", desc: "Webhook fired → HRIS cập nhật", status: "auto" },
          ].map((step, i) => (
            <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start", marginBottom: 10 }}>
              <div style={{ width: 22, height: 22, borderRadius: "50%", background: step.status === "auto" ? C.navyGhost : step.status === "manual" ? C.warnBg : C.infoBg, color: step.status === "auto" ? C.navy : step.status === "manual" ? C.warn : C.info, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 800, flexShrink: 0, marginTop: 1 }}>{step.icon}</div>
              <div>
                <p style={{ fontSize: 13, fontWeight: 600 }}>{step.label}</p>
                <p style={{ fontSize: 11, color: C.textLight }}>{step.desc}</p>
              </div>
              <Badge size="xs" color={step.status === "auto" ? "navy" : step.status === "manual" ? "yellow" : "blue"}>{step.status}</Badge>
            </div>
          ))}
        </Card>
      </div>

      <Card>
        <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 14 }}>👥 Nhân viên cần chú ý</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {MOCK_EMP.filter(e => e.health_score !== "green").map(emp => (
            <div key={emp.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 14px", background: emp.health_score === "red" ? C.dangerBg : C.warnBg, borderRadius: 8, border: `1px solid ${emp.health_score === "red" ? C.dangerBorder : C.warnBorder}` }}>
              <Avatar name={emp.full_name} size={30} />
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: 13, fontWeight: 700 }}>{emp.full_name}</p>
                <p style={{ fontSize: 11, color: C.textMid }}>{emp.role} · {emp.department} · Tiến độ: {emp.completion_percentage}%</p>
              </div>
              <Badge color={statusColorMap(emp.health_score)}>{statusLabel(emp.health_score)}</Badge>
            </div>
          ))}
        </div>
      </Card>

      {/* ── Bottleneck Detection ── */}
      {bottlenecks.length > 0 && (
        <Card style={{ marginTop: 18 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 14 }}>🚧 Bottleneck Detection</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {bottlenecks.map((b, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 14px", background: C.dangerBg, borderRadius: 8, border: `1px solid ${C.dangerBorder}` }}>
                <div style={{ flex: 1 }}>
                  <p style={{ fontSize: 13, fontWeight: 700 }}>{b.task_name || b.checklist_title}</p>
                  <p style={{ fontSize: 11, color: C.textMid }}>{b.affected_count || b.affected_employees} NV bị kẹt · Trung bình quá hạn {b.avg_overdue_days} ngày</p>
                </div>
                <Badge color="red">{b.category || "bottleneck"}</Badge>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── Content Gap Detection ── */}
      {contentGaps && (
        <Card style={{ marginTop: 18 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 14 }}>📊 Content Gap Detection</h3>
          {contentGaps.clusters?.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {contentGaps.clusters.map((cl, i) => (
                <div key={i} style={{ padding: "10px 14px", background: C.warnBg, borderRadius: 8, border: `1px solid ${C.warnBorder}` }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <p style={{ fontSize: 13, fontWeight: 700 }}>{cl.topic || cl.topic_cluster}</p>
                    <Badge color="orange">{cl.question_count || cl.count} câu hỏi</Badge>
                  </div>
                  {cl.sample_questions && <p style={{ fontSize: 11, color: C.textMid, marginTop: 4 }}>{cl.sample_questions.slice(0,2).join(" · ")}</p>}
                </div>
              ))}
            </div>
          ) : (
            <p style={{ fontSize: 13, color: C.textMid }}>{contentGaps.total_unanswered || 0} câu hỏi chưa trả lời — chưa đủ data để cluster.</p>
          )}
        </Card>
      )}

      {/* ── AI Copilot ── */}
      <Card style={{ marginTop: 18 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 14 }}>🤖 AI Copilot — Phân tích nhân viên</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
          {MOCK_EMP.filter(e => e.vai_tro === "nhan_vien_moi").map(emp => (
            <Btn key={emp.id} size="sm" variant={copilotData?.employee_id === emp.id ? "primary" : "secondary"}
              loading={copilotLoading === emp.id}
              onClick={async () => {
                setCopilotLoading(emp.id);
                const res = await apiClient.getCopilot(emp.id);
                setCopilotLoading(null);
                if (res.success) setCopilotData(res.data);
                else setCopilotData({ employee_id: emp.id, employee_name: emp.full_name, summary: `NV ${emp.full_name} — chạy copilot cần backend online`, risk_factors: [], suggested_actions: [], priority: "low", data_source: "mock" });
              }}>{emp.full_name}</Btn>
          ))}
        </div>
        {copilotData && (
          <div style={{ padding: "14px 16px", background: copilotData.priority === "high" ? C.dangerBg : copilotData.priority === "medium" ? C.warnBg : C.successBg, borderRadius: 10, border: `1px solid ${copilotData.priority === "high" ? C.dangerBorder : copilotData.priority === "medium" ? C.warnBorder : C.successBorder}` }}>
            <p style={{ fontSize: 14, fontWeight: 700, marginBottom: 6 }}>{copilotData.employee_name} <Badge color={copilotData.priority === "high" ? "red" : copilotData.priority === "medium" ? "orange" : "green"} size="xs">{copilotData.priority}</Badge></p>
            <p style={{ fontSize: 13, lineHeight: 1.6 }}>{copilotData.summary}</p>
            {copilotData.suggested_actions?.length > 0 && (
              <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
                {copilotData.suggested_actions.map((a, i) => (
                  <Btn key={i} size="xs" variant="secondary" onClick={async () => {
                    if (a.type === "assign_buddy") await apiClient.assignBuddy(copilotData.employee_id);
                    else if (a.type === "escalate_it") await apiClient.escalateIt(copilotData.employee_id);
                    else if (a.type === "schedule_checkin") await apiClient.scheduleCheckin(copilotData.employee_id);
                    else if (a.type === "send_reminder") await apiClient.sendReminder(copilotData.employee_id);
                    toast(`✅ ${a.label} — đã thực hiện`, "success");
                  }}>{a.label}</Btn>
                ))}
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
};

// ── Manager Dashboard (focused view — không có automation flow) ──
const ManagerDashboard = ({ user, toast }) => {
  // Nhân viên Manager phụ trách (mock: tất cả nhan_vien_moi)
  const myEmployees = MOCK_EMP.filter(e => e.vai_tro === "nhan_vien_moi");
  const total = myEmployees.length;
  const inProgress = myEmployees.filter(e => e.onboarding_status === "in_progress").length;
  const needAttention = myEmployees.filter(e => e.health_score !== "green").length;
  const completed = myEmployees.filter(e => e.onboarding_status === "completed").length;

  // Reminder logs liên quan đến NV của manager (mock: tier 2 = gửi cho manager)
  const managerReminders = [
    { id: "r1", employee_name: "Trần Thị Bình", item: "1-on-1 với Manager tuần đầu", tier: 2, message: "📋 Trần Thị Bình chưa hoàn thành '1-on-1 với Manager tuần đầu' (quá hạn 2 ngày).", sent_at: "2026-04-18T14:00:00" },
    { id: "r2", employee_name: "Phạm Đức Dũng", item: "Set 30-60-90 day goals", tier: 2, message: "📋 Phạm Đức Dũng chưa hoàn thành 'Set 30-60-90 day goals'.", sent_at: "2026-04-19T09:00:00" },
  ];

  const MetricCard = ({ label, value, color, sublabel }) => (
    <Card style={{ textAlign: "center", padding: "18px 14px" }}>
      <p style={{ fontSize: 28, fontWeight: 800, color: color || C.navy }}>{value}</p>
      <p style={{ fontSize: 13, fontWeight: 600, color: C.textMid, marginTop: 2 }}>{label}</p>
      {sublabel && <p style={{ fontSize: 11, color: C.textLight, marginTop: 3 }}>{sublabel}</p>}
    </Card>
  );

  return (
    <div style={{ animation: "fadeIn .2s ease" }}>
      <div style={{ padding: "24px 0 18px" }}>
        <h2 style={{ fontSize: 22, fontWeight: 800 }}>Dashboard Quản lý</h2>
        <p style={{ color: C.textMid, fontSize: 13, marginTop: 3 }}>Xin chào {user.full_name} · {new Date().toLocaleDateString("vi-VN", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}</p>
      </div>

      {/* Thống kê tổng quan nhân viên của mình */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, marginBottom: 22 }}>
        <MetricCard label="NV đang phụ trách" value={total} sublabel="trong team" />
        <MetricCard label="Đang onboard" value={inProgress} color={C.info} sublabel="in progress" />
        <MetricCard label="Hoàn thành" value={completed} color={C.successMid} sublabel="tháng này" />
        <MetricCard label="⚠ Cần can thiệp" value={needAttention} color={needAttention > 0 ? C.danger : C.successMid} sublabel="cần chú ý" />
      </div>

      {/* Danh sách nhân viên đang phụ trách */}
      <Card style={{ marginBottom: 18 }}>
        <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 14 }}>👥 Nhân viên đang onboarding</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {myEmployees.map(emp => {
            const healthBg = { green: C.successBg, yellow: C.warnBg, red: C.dangerBg }[emp.health_score] || C.navyFaint;
            const healthBorder = { green: C.successBorder, yellow: C.warnBorder, red: C.dangerBorder }[emp.health_score] || C.border;
            return (
              <div key={emp.id} style={{ display: "flex", alignItems: "center", gap: 13, padding: "13px 16px", background: healthBg, borderRadius: 10, border: `1px solid ${healthBorder}`, borderLeft: `3px solid ${healthBorder}` }}>
                <Avatar name={emp.full_name} size={36} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                    <p style={{ fontSize: 14, fontWeight: 700 }}>{emp.full_name}</p>
                    <Badge color={statusColorMap(emp.onboarding_status)} size="xs">{statusLabel(emp.onboarding_status)}</Badge>
                    <Badge color={statusColorMap(emp.health_score)} size="xs">{statusLabel(emp.health_score)}</Badge>
                  </div>
                  <p style={{ fontSize: 12, color: C.textMid, marginTop: 3 }}>{emp.role} · {emp.department} · Bắt đầu: {emp.start_date}</p>
                  {/* Progress bar nhỏ */}
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 7 }}>
                    <div style={{ flex: 1, height: 5, background: "rgba(0,0,0,.08)", borderRadius: 3 }}>
                      <div style={{ width: `${emp.completion_percentage}%`, height: "100%", background: emp.completion_percentage === 100 ? C.successMid : C.navy, borderRadius: 3 }} />
                    </div>
                    <span style={{ fontSize: 11, fontWeight: 700, color: C.textMid, whiteSpace: "nowrap" }}>{emp.completion_percentage}%</span>
                  </div>
                </div>
              </div>
            );
          })}
          {myEmployees.length === 0 && (
            <p style={{ fontSize: 13, color: C.textLight, textAlign: "center", padding: "20px 0" }}>Không có nhân viên nào đang onboarding.</p>
          )}
        </div>
      </Card>

      {/* Checklist items cần Manager xác nhận */}
      <Card style={{ marginBottom: 18 }}>
        <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 6 }}>✅ Mục checklist chờ bạn xác nhận</h3>
        <p style={{ fontSize: 12, color: C.textMid, marginBottom: 14 }}>Các mục có nhãn <strong>👔 Manager</strong> cần bạn tick hoàn thành.</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {MOCK_CHECKLIST_ITEMS.filter(i => i.owner === "manager").map(item => {
            const isDone = item.status === "hoan_thanh";
            const isOverdue = !isDone && item.deadline_date && new Date(item.deadline_date) < new Date();
            return (
              <div key={item.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 14px", background: isDone ? "#fafffe" : isOverdue ? C.dangerBg : C.navyFaint, borderRadius: 9, border: `1px solid ${isDone ? C.successBorder : isOverdue ? C.dangerBorder : C.border}`, borderLeft: `3px solid ${isDone ? C.successMid : isOverdue ? C.danger : C.navy}` }}>
                <div style={{ width: 20, height: 20, borderRadius: 5, border: `2px solid ${isDone ? C.successMid : isOverdue ? C.danger : C.border}`, background: isDone ? C.successMid : "transparent", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: C.white, flexShrink: 0 }}>
                  {isDone ? "✓" : ""}
                </div>
                <div style={{ flex: 1 }}>
                  <p style={{ fontSize: 13, fontWeight: 600, textDecoration: isDone ? "line-through" : "none", color: isDone ? C.textLight : C.text }}>{item.title}</p>
                  {item.deadline_date && <p style={{ fontSize: 11, color: isOverdue ? C.danger : C.textLight, marginTop: 2 }}>📅 Hạn: {item.deadline_date}{isOverdue ? " — Quá hạn!" : ""}</p>}
                </div>
                <Badge size="xs" color={isDone ? "green" : isOverdue ? "red" : "navy"}>{isDone ? "Xong" : isOverdue ? "Quá hạn" : "Chờ"}</Badge>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Reminder nhận được (Tier 2 — gửi cho Manager) */}
      <Card>
        <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 14 }}>🔔 Nhắc nhở gần đây</h3>
        {managerReminders.length === 0 ? (
          <p style={{ fontSize: 13, color: C.textLight }}>Không có nhắc nhở mới.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
            {managerReminders.map(r => (
              <div key={r.id} style={{ display: "flex", gap: 12, padding: "11px 14px", background: C.warnBg, borderRadius: 9, borderLeft: `3px solid ${C.warn}` }}>
                <div style={{ flex: 1 }}>
                  <p style={{ fontSize: 13, fontWeight: 700 }}>{r.employee_name} <span style={{ fontWeight: 400, color: C.textMid }}>— {r.item}</span></p>
                  <p style={{ fontSize: 12, color: C.textMid, marginTop: 2 }}>{r.message}</p>
                  <p style={{ fontSize: 11, color: C.textLight, marginTop: 2 }}>{new Date(r.sent_at).toLocaleString("vi-VN")}</p>
                </div>
                <Badge size="xs" color="yellow">Tier 2</Badge>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};

// ─── Employees Page ───
const EmployeesPage = ({ user, toast }) => {
  const isHR = roleIs(user, "hr_admin");
  const isManager = roleIs(user, "quan_ly");
  const [employees, setEmployees] = useState(MOCK_EMP);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [showDetail, setShowDetail] = useState(null);
  const [form, setForm] = useState({ seniority: "junior", department: "Engineering" });
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [actionLoading, setActionLoading] = useState({});

  useEffect(() => {
    (async () => {
      setLoading(true);
      const res = await apiClient.listEmployees();
      if (res.success) setEmployees(res.data);
      setLoading(false);
    })();
  }, []);

  const create = async () => {
    const res = await apiClient.createEmployee(form);
    if (res.success) {
      toast(`✅ Đã tạo nhân viên ${form.full_name} — mã ${res.data.employee_code}`, "success");
      setEmployees(p => [...p, { ...form, id: res.data.id || `e${Date.now()}`, employee_code: res.data.employee_code, vai_tro: "nhan_vien_moi", onboarding_status: "pre_boarding", health_score: "green", completion_percentage: 0 }]);
    } else {
      toast("Tạo nhân viên (mock mode) — backend offline", "info");
      setEmployees(p => [...p, { ...form, id: `e${Date.now()}`, employee_code: `NV-2026-00${p.length + 1}`, vai_tro: "nhan_vien_moi", onboarding_status: "pre_boarding", health_score: "green", completion_percentage: 0 }]);
    }
    setShowCreate(false);
  };

  const doAction = async (empId, action) => {
    setActionLoading(p => ({ ...p, [`${empId}_${action}`]: true }));
    let res;
    if (action === "buddy") res = await apiClient.assignBuddy(empId);
    else if (action === "it") res = await apiClient.escalateIt(empId);
    else if (action === "checkin") res = await apiClient.scheduleCheckin(empId);
    else if (action === "reminder") res = await apiClient.sendReminder(empId);
    setActionLoading(p => ({ ...p, [`${empId}_${action}`]: false }));
    const emp = employees.find(e => e.id === empId);
    const msgs = { buddy: "📮 Đã gửi yêu cầu assign buddy cho Manager", it: "🚨 Đã escalate IT tasks — stakeholders thông báo qua email", checkin: "📅 Đã đặt lịch check-in và tạo checklist item", reminder: "📲 Đã gửi nhắc nhở trực tiếp cho nhân viên" };
    toast(res?.success ? (res.data.message || msgs[action]) : msgs[action], "info");
  };

  const filtered = employees.filter(e =>
    (!search || `${e.full_name} ${e.email}`.toLowerCase().includes(search.toLowerCase())) &&
    (!filterStatus || e.onboarding_status === filterStatus)
  );

  const healthDot = h => ({ green: C.successMid, yellow: C.orange, red: C.danger }[h] || C.textLight);

  return (
    <div style={{ animation: "fadeIn .2s ease" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", padding: "24px 0 18px", flexWrap: "wrap", gap: 10 }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 800 }}>Quản lý nhân viên</h2>
          <p style={{ color: C.textMid, fontSize: 13, marginTop: 3 }}>{employees.length} nhân viên · {isHR ? "Quản lý checklist & trạng thái onboarding" : "Xem tiến độ nhân viên"}</p>
        </div>
        {/* Chỉ HR mới được tạo nhân viên */}
        {isHR && <Btn onClick={() => setShowCreate(true)} icon="➕">Thêm nhân viên</Btn>}
      </div>

      <div style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Tìm tên, email..." style={{ maxWidth: 260 }} />
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} style={{ maxWidth: 200 }}>
          <option value="">Tất cả trạng thái</option>
          <option value="pre_boarding">Pre-boarding</option>
          <option value="in_progress">Đang onboard</option>
          <option value="completed">Hoàn thành</option>
        </select>
      </div>

      <Card style={{ padding: 0, overflow: "hidden" }}>
        {loading ? <div style={{ padding: 40, textAlign: "center", color: C.textLight }}>Đang tải...</div> : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: C.navyFaint, borderBottom: `1px solid ${C.border}` }}>
                {["Nhân viên", "Role / Dept", "Ngày bắt đầu", "Trạng thái", "Tiến độ", "Sức khỏe", "Hành động nhanh"].map(h => (
                  <th key={h} style={{ padding: "10px 14px", textAlign: "left", color: C.textMid, fontWeight: 700, fontSize: 11, letterSpacing: 0.5, textTransform: "uppercase", whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((emp, i) => (
                <tr key={emp.id} style={{ borderBottom: `1px solid ${C.borderLight}`, background: i % 2 ? "#fafbff" : "transparent", cursor: "pointer", transition: "background .1s" }}
                  onMouseEnter={e => e.currentTarget.style.background = C.navyFaint}
                  onMouseLeave={e => e.currentTarget.style.background = i % 2 ? "#fafbff" : "transparent"}>
                  <td style={{ padding: "11px 14px" }} onClick={() => setShowDetail(emp)}>
                    <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                      <Avatar name={emp.full_name} size={30} />
                      <div>
                        <p style={{ fontWeight: 700, fontSize: 13 }}>{emp.full_name}</p>
                        <p style={{ fontSize: 11, color: C.textLight }}>{emp.employee_code}</p>
                      </div>
                    </div>
                  </td>
                  <td style={{ padding: "11px 14px" }} onClick={() => setShowDetail(emp)}>
                    <p style={{ fontSize: 13 }}>{emp.role}</p>
                    <p style={{ fontSize: 11, color: C.textLight }}>{emp.department} · {emp.seniority}</p>
                  </td>
                  <td style={{ padding: "11px 14px", fontSize: 12, color: C.textMid }} onClick={() => setShowDetail(emp)}>{emp.start_date}</td>
                  <td style={{ padding: "11px 14px" }} onClick={() => setShowDetail(emp)}><Badge color={statusColorMap(emp.onboarding_status)}>{statusLabel(emp.onboarding_status)}</Badge></td>
                  <td style={{ padding: "11px 14px", minWidth: 110 }} onClick={() => setShowDetail(emp)}>
                    <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                      <div style={{ flex: 1, height: 5, background: C.border, borderRadius: 4 }}>
                        <div style={{ width: `${emp.completion_percentage}%`, height: "100%", background: emp.completion_percentage === 100 ? C.successMid : C.navy, borderRadius: 4, transition: "width .4s" }} />
                      </div>
                      <span style={{ fontSize: 11, color: C.textMid, minWidth: 28, fontWeight: 700 }}>{emp.completion_percentage}%</span>
                    </div>
                  </td>
                  <td style={{ padding: "11px 14px" }} onClick={() => setShowDetail(emp)}>
                    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                      <div style={{ width: 8, height: 8, borderRadius: "50%", background: healthDot(emp.health_score), flexShrink: 0 }} />
                      <span style={{ fontSize: 11, color: C.textMid }}>{statusLabel(emp.health_score)}</span>
                    </div>
                  </td>
                  <td style={{ padding: "11px 10px" }}>
                    <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                      {/* Chỉ HR mới thấy và dùng được các action button */}
                      {isHR ? (
                        <>
                          <Btn size="xs" variant="secondary" loading={actionLoading[`${emp.id}_buddy`]} onClick={() => doAction(emp.id, "buddy")} title="Nhắc assign buddy">🤝</Btn>
                          <Btn size="xs" variant="warning" loading={actionLoading[`${emp.id}_it`]} onClick={() => doAction(emp.id, "it")} title="Escalate IT">⚡</Btn>
                          <Btn size="xs" variant="info" loading={actionLoading[`${emp.id}_checkin`]} onClick={() => doAction(emp.id, "checkin")} title="Đặt lịch check-in">📅</Btn>
                          <Btn size="xs" variant="ghost" loading={actionLoading[`${emp.id}_reminder`]} onClick={() => doAction(emp.id, "reminder")} title="Gửi nhắc nhở">🔔</Btn>
                        </>
                      ) : (
                        <span style={{ fontSize: 11, color: C.textLight, fontStyle: "italic" }}>—</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && filtered.length === 0 && <p style={{ textAlign: "center", padding: 32, color: C.textLight }}>Không tìm thấy nhân viên nào</p>}
      </Card>

      {/* Create Employee Modal — chỉ HR mới có quyền */}
      {isHR && showCreate && (
        <Modal title="Thêm nhân viên mới" onClose={() => setShowCreate(false)}>
          <InfoBox type="info" children={<span>Sau khi tạo, hệ thống sẽ tự tạo <strong>preboarding documents checklist</strong> và sẵn sàng để generate checklist onboarding.</span>} />
          <div style={{ height: 16 }} />
          <Field label="Họ và tên" required>
            <input value={form.full_name || ""} onChange={e => setForm(p => ({ ...p, full_name: e.target.value }))} />
          </Field>
          <Field label="Email công ty" required hint="Phải đúng domain @company.com">
            <input type="email" value={form.email || ""} onChange={e => setForm(p => ({ ...p, email: e.target.value }))} placeholder="ten.nv@company.com" />
          </Field>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Field label="Vị trí" required><input value={form.role || ""} onChange={e => setForm(p => ({ ...p, role: e.target.value }))} /></Field>
            <Field label="Phòng ban" required><input value={form.department || ""} onChange={e => setForm(p => ({ ...p, department: e.target.value }))} /></Field>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <Field label="Cấp bậc">
              <select value={form.seniority || "junior"} onChange={e => setForm(p => ({ ...p, seniority: e.target.value }))}>
                <option value="intern">Intern</option>
                <option value="junior">Junior</option>
                <option value="mid">Mid</option>
                <option value="senior">Senior</option>
                <option value="lead">Lead/Manager</option>
              </select>
            </Field>
            <Field label="Ngày bắt đầu" required><input type="date" value={form.start_date || ""} onChange={e => setForm(p => ({ ...p, start_date: e.target.value }))} /></Field>
          </div>
          <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 6 }}>
            <Btn variant="ghost" onClick={() => setShowCreate(false)}>Hủy</Btn>
            <Btn onClick={create} disabled={!form.full_name || !form.email || !form.role}>Tạo nhân viên</Btn>
          </div>
        </Modal>
      )}

      {/* Detail Modal */}
      {showDetail && (
        <Modal title={`Chi tiết — ${showDetail.full_name}`} onClose={() => setShowDetail(null)} width={560}>
          <div style={{ display: "flex", gap: 14, alignItems: "center", marginBottom: 18, padding: "14px", background: C.navyFaint, borderRadius: 10 }}>
            <Avatar name={showDetail.full_name} size={48} />
            <div>
              <p style={{ fontWeight: 800, fontSize: 16 }}>{showDetail.full_name}</p>
              <p style={{ fontSize: 13, color: C.textMid }}>{showDetail.role} · {showDetail.department}</p>
              <p style={{ fontSize: 12, color: C.textLight }}>{showDetail.email} · {showDetail.employee_code}</p>
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 16 }}>
            {[["Trạng thái", <Badge color={statusColorMap(showDetail.onboarding_status)}>{statusLabel(showDetail.onboarding_status)}</Badge>],
              ["Sức khỏe", <Badge color={statusColorMap(showDetail.health_score)}>{statusLabel(showDetail.health_score)}</Badge>],
              ["Ngày bắt đầu", showDetail.start_date],
              ["Tiến độ", `${showDetail.completion_percentage}%`],
              ["Cấp bậc", showDetail.seniority],
              ["Role hệ thống", showDetail.vai_tro]
            ].map(([k, v]) => (
              <div key={k} style={{ background: C.bg, borderRadius: 8, padding: "9px 12px" }}>
                <p style={{ fontSize: 10, color: C.textLight, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.4 }}>{k}</p>
                <div style={{ marginTop: 4, fontSize: 13, fontWeight: 600 }}>{v}</div>
              </div>
            ))}
          </div>
          <h4 style={{ fontSize: 13, fontWeight: 700, marginBottom: 10 }}>Hành động nhanh (AI Copilot Actions)</h4>
          {isHR ? (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {[
              { action: "buddy", icon: "🤝", label: "Nhắc assign buddy", desc: "Gửi yêu cầu cho Manager", variant: "secondary" },
              { action: "it", icon: "⚡", label: "Escalate IT tasks", desc: "Đánh dấu urgent + notify IT", variant: "warning" },
              { action: "checkin", icon: "📅", label: "Đặt lịch check-in", desc: "Tạo reminder + calendar", variant: "info" },
              { action: "reminder", icon: "🔔", label: "Gửi nhắc nhở", desc: "Slack DM cho nhân viên", variant: "ghost" },
            ].map(item => (
              <button key={item.action} onClick={() => { doAction(showDetail.id, item.action); setShowDetail(null); }}
                style={{ background: C.navyFaint, border: `1px solid ${C.border}`, borderRadius: 10, padding: "12px", cursor: "pointer", textAlign: "left", transition: "all .12s" }}
                onMouseEnter={e => e.currentTarget.style.background = C.accentSoft}
                onMouseLeave={e => e.currentTarget.style.background = C.navyFaint}>
                <p style={{ fontSize: 17, marginBottom: 4 }}>{item.icon}</p>
                <p style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{item.label}</p>
                <p style={{ fontSize: 11, color: C.textMid }}>{item.desc}</p>
              </button>
            ))}
          </div>
          ) : (
            <div style={{ padding: "12px 14px", background: C.navyFaint, borderRadius: 8, fontSize: 13, color: C.textMid }}>
              🔒 Chỉ HR Admin mới có quyền thực hiện các hành động này.
            </div>
          )}
        </Modal>
      )}
    </div>
  );
};

// ─── Role helpers ───
// ─── Checklist Page ───
const ChecklistPage = ({ user, toast }) => {
  // Phân quyền rõ ràng
  const isHR = roleIs(user, "hr_admin");
  const isManager = roleIs(user, "quan_ly");
  const isNewHire = roleIs(user, "nhan_vien_moi");

  // HR thấy tất cả nhân viên; Manager thấy danh sách nhân viên mình quản lý (mock: tất cả ngoại trừ bản thân); NV mới chỉ thấy của mình
  const visibleEmps = isHR
    ? MOCK_EMP
    : isManager
      ? MOCK_EMP.filter(e => e.vai_tro === "nhan_vien_moi")
      : MOCK_EMP.filter(e => e.id === (MOCK_EMP.find(m => m.vai_tro === user?.vai_tro)?.id || "e1"));

  const defaultEmp = isNewHire
    ? (MOCK_EMP.find(e => e.vai_tro === "nhan_vien_moi") || MOCK_EMP[0])
    : visibleEmps[0] || MOCK_EMP[0];

  const [selectedEmp, setSelectedEmp] = useState(defaultEmp);
  const [planStatus, setPlanStatus] = useState("da_duyet");
  const [items, setItems] = useState(MOCK_CHECKLIST_ITEMS);
  const [generating, setGenerating] = useState(false);
  const [approving, setApproving] = useState(false);
  const [approveResult, setApproveResult] = useState(null);

  // Fetch real checklist from backend
  useEffect(() => {
    (async () => {
      try {
        const res = await apiClient.getEmployeeChecklist(selectedEmp.id);
        if (res.success && res.data?.items?.length > 0) {
          setItems(res.data.items.map(i => ({ ...i, deadline_date: i.deadline_date || i.due_date })));
          if (res.data.plan_status) setPlanStatus(res.data.plan_status);
        }
      } catch {}
    })();
  }, [selectedEmp.id]);

  // HR-only actions
  const generate = async () => {
    setGenerating(true);
    const res = await apiClient.generateChecklist(selectedEmp.id);
    setGenerating(false);
    toast(res.success
      ? `✅ Đã tạo ${res.data.items_count} checklist items`
      : "Generated checklist (mock): 13 items — Layer 1 bắt buộc + Layer 2 role-specific", "info");
    setPlanStatus("ban_thao");
  };

  const approve = async () => {
    setApproving(true);
    const res = await apiClient.approvePlan("mock-plan-id", user.id);
    setApproving(false);
    setApproveResult(res.success ? res.data : { stakeholder_tasks_created: { it: 1, admin: 1, manager: 2 } });
    setPlanStatus("da_duyet");
    toast("✅ Plan đã duyệt — email magic link đã gửi cho IT, Admin, Manager", "success");
  };

  const completeItem = async (itemId) => {
    const newItems = items.map(c => c.id === itemId ? { ...c, status: "hoan_thanh" } : c);
    setItems(newItems);
    await apiClient.completeItem(itemId, user.id);
    const newDone = newItems.filter(i => i.status === "hoan_thanh").length;
    const newPct = Math.round(newDone / newItems.length * 100);
    toast(`Đã hoàn thành! Tiến độ: ${newPct}%`, "success");
  };

  // Derived data
  const done = items.filter(i => i.status === "hoan_thanh").length;
  const pct = Math.round((done / items.length) * 100);
  const overdue = items.filter(i => i.status !== "hoan_thanh" && i.deadline_date && new Date(i.deadline_date) < new Date()).length;
  const grouped = items.reduce((a, item) => {
    const k = item.week === 0 ? "Pre-boarding" : `Tuần ${item.week}`;
    if (!a[k]) a[k] = [];
    a[k].push(item); return a;
  }, {});
  const catIcons = { tools: "🔧", compliance: "⚖️", admin: "📋", social: "👋", role_specific: "🎯", training: "📚" };

  // Status pill (inline, no Badge component — cleaner)
  const StatusPill = ({ status }) => {
    const map = {
      hoan_thanh: { bg: C.successBg, color: C.successMid, label: "Hoàn thành" },
      dang_lam:   { bg: C.infoBg,    color: C.info,       label: "Đang làm" },
      chua_bat_dau: { bg: "#f5f5f5", color: C.textLight,  label: "Chưa bắt đầu" },
    };
    const s = map[status] || { bg: "#f5f5f5", color: C.textLight, label: status };
    return (
      <span style={{ fontSize: 11, fontWeight: 600, padding: "3px 9px", borderRadius: 20, background: s.bg, color: s.color, whiteSpace: "nowrap" }}>
        {s.label}
      </span>
    );
  };

  return (
    <div style={{ animation: "fadeIn .2s ease", maxWidth: 820 }}>

      {/* ── Header ── */}
      <div style={{ padding: "24px 0 20px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h2 style={{ fontSize: 22, fontWeight: 800 }}>Checklist Onboarding</h2>
            {isHR
              ? <p style={{ color: C.textMid, fontSize: 13, marginTop: 3 }}>Quản lý kế hoạch onboarding · Phân quyền theo vai trò</p>
              : isManager
              ? <p style={{ color: C.textMid, fontSize: 13, marginTop: 3 }}>Xem tiến độ nhân viên · Xác nhận các mục của bạn</p>
              : <p style={{ color: C.textMid, fontSize: 13, marginTop: 3 }}>Xin chào <strong>{user?.full_name}</strong> — đây là kế hoạch onboarding của bạn</p>
            }
          </div>
          {/* HR hoặc Manager: employee selector */}
          {(isHR || isManager) && (
            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              <select value={selectedEmp.id} onChange={e => setSelectedEmp(visibleEmps.find(m => m.id === e.target.value))} style={{ width: 230 }}>
                {visibleEmps.map(emp => <option key={emp.id} value={emp.id}>{emp.full_name} — {emp.role}</option>)}
              </select>
              {/* Chỉ HR mới có nút generate/approve */}
              {isHR && planStatus === null && (
                <Btn onClick={generate} loading={generating} icon="🤖" size="sm">Generate</Btn>
              )}
              {isHR && planStatus === "ban_thao" && (
                <>
                  <Btn variant="ghost" onClick={generate} loading={generating} icon="🔄" size="sm">Tái generate</Btn>
                  <Btn variant="success" onClick={approve} loading={approving} icon="✅" size="sm">Duyệt & Notify</Btn>
                </>
              )}
              {planStatus === "da_duyet" && <Badge color="green">Đã duyệt</Badge>}
            </div>
          )}
        </div>
      </div>

      {/* ── HR: approve result notice ── */}
      {isHR && planStatus === "da_duyet" && approveResult && (
        <div style={{ marginBottom: 16 }}>
          <InfoBox type="success">
            <strong>Plan đã duyệt!</strong> Đã tạo stakeholder tasks cho IT ({approveResult.stakeholder_tasks_created?.it || 1}), Admin ({approveResult.stakeholder_tasks_created?.admin || 1}), Manager ({approveResult.stakeholder_tasks_created?.manager || 2}). Email magic link đã gửi.
          </InfoBox>
        </div>
      )}

      {/* ── Progress summary card ── */}
      <Card style={{ marginBottom: 20, padding: "20px 22px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap" }}>
          {/* Avatar + name */}
          <Avatar name={selectedEmp.full_name} size={42} />
          <div style={{ flex: 1, minWidth: 160 }}>
            <p style={{ fontWeight: 800, fontSize: 15 }}>{selectedEmp.full_name}</p>
            <p style={{ fontSize: 12, color: C.textMid, marginTop: 1 }}>{selectedEmp.role} · {selectedEmp.department}</p>
          </div>
          {/* Mini stats */}
          <div style={{ display: "flex", gap: 20, alignItems: "center", flexWrap: "wrap" }}>
            {[
              { val: done, label: "Hoàn thành", color: C.successMid },
              { val: items.filter(i => i.status === "dang_lam").length, label: "Đang làm", color: C.info },
              { val: items.filter(i => i.status === "chua_bat_dau").length, label: "Chưa bắt đầu", color: C.textLight },
              ...(overdue > 0 ? [{ val: overdue, label: "Quá hạn", color: C.danger }] : []),
            ].map(s => (
              <div key={s.label} style={{ textAlign: "center" }}>
                <p style={{ fontSize: 20, fontWeight: 800, color: s.color, lineHeight: 1 }}>{s.val}</p>
                <p style={{ fontSize: 11, color: C.textLight, marginTop: 2 }}>{s.label}</p>
              </div>
            ))}
          </div>
        </div>
        {/* Progress bar */}
        <div style={{ marginTop: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: C.textMid }}>Tiến độ tổng thể</span>
            <span style={{ fontSize: 13, fontWeight: 800, color: pct === 100 ? C.successMid : C.navy }}>{pct}%</span>
          </div>
          <div style={{ height: 8, background: C.border, borderRadius: 6 }}>
            <div style={{ width: `${pct}%`, height: "100%", background: pct === 100 ? C.successMid : `linear-gradient(90deg, ${C.navy}, ${C.navyLight})`, borderRadius: 6, transition: "width .5s ease" }} />
          </div>
          <p style={{ fontSize: 11, color: C.textLight, marginTop: 5 }}>
            {done}/{items.length} mục · {items.filter(i => i.is_mandatory && i.status !== "hoan_thanh").length} bắt buộc còn lại
            {overdue > 0 && <span style={{ color: C.danger, fontWeight: 700 }}> · {overdue} quá hạn</span>}
          </p>
        </div>
      </Card>

      {/* ── New hire: plan not yet approved notice ── */}
      {isNewHire && planStatus !== "da_duyet" && (
        <div style={{ marginBottom: 16 }}>
          <InfoBox type="warn">Kế hoạch onboarding đang chờ HR duyệt. Bạn sẽ nhận email thông báo khi có thể bắt đầu.</InfoBox>
        </div>
      )}

      {/* ── Manager: hướng dẫn quyền hạn ── */}
      {isManager && (
        <div style={{ marginBottom: 16 }}>
          <InfoBox type="info">
            Bạn đang xem với vai trò <strong>Quản lý</strong>. Bạn chỉ có thể xác nhận các mục mang nhãn <strong>👔 Manager</strong> (ví dụ: Assign buddy, 1-on-1...). Các mục của nhân viên hoặc IT sẽ hiển thị 🔒.
          </InfoBox>
        </div>
      )}

      {/* ── NV mới: hướng dẫn quyền hạn ── */}
      {isNewHire && planStatus === "da_duyet" && (
        <div style={{ marginBottom: 16 }}>
          <InfoBox type="info">
            Bạn chỉ có thể tick hoàn thành các mục mang nhãn <strong>👤 NV</strong>. Các mục của Manager hoặc IT sẽ hiển thị 🔒.
          </InfoBox>
        </div>
      )}

      {/* ── Checklist items grouped by week ── */}
      {Object.entries(grouped).map(([week, weekItems]) => {
        const weekDone = weekItems.filter(i => i.status === "hoan_thanh").length;
        const allDone = weekDone === weekItems.length;
        return (
          <div key={week} style={{ marginBottom: 22 }}>
            {/* Week header */}
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: allDone ? C.successMid : C.navy, flexShrink: 0 }} />
              <h4 style={{ fontSize: 12, color: allDone ? C.successMid : C.textMid, fontWeight: 700, letterSpacing: 0.6, textTransform: "uppercase" }}>{week}</h4>
              <div style={{ flex: 1, height: 1, background: C.borderLight }} />
              <span style={{ fontSize: 11, color: allDone ? C.successMid : C.textLight, fontWeight: allDone ? 700 : 400 }}>
                {weekDone}/{weekItems.length} {allDone ? "✓" : ""}
              </span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {weekItems.map(item => {
                const isDone = item.status === "hoan_thanh";
                const isOverdue = !isDone && item.deadline_date && new Date(item.deadline_date) < new Date();
                // Phân quyền tick checklist:
                // - HR: tick tất cả
                // - Manager: chỉ tick mục owner = "manager"
                // - NV mới: chỉ tick mục owner = "new_hire"
                const canComplete = !isDone && planStatus === "da_duyet" && (
                  isHR ||
                  (isManager && item.owner === "manager") ||
                  (isNewHire && item.owner === "new_hire")
                );
                const noPermissionReason = isDone ? "Đã hoàn thành"
                  : isNewHire && item.owner !== "new_hire" ? "Mục này thuộc quyền HR/Manager"
                  : isManager && item.owner !== "manager" ? "Mục này không thuộc quyền của bạn"
                  : planStatus !== "da_duyet" ? "Kế hoạch chưa được duyệt"
                  : "Không thể thao tác";
                return (
                  <div key={item.id} style={{
                    display: "flex", alignItems: "center", gap: 12,
                    padding: "13px 16px",
                    background: isDone ? "#fafffe" : C.white,
                    border: `1px solid ${isDone ? C.successBorder : isOverdue ? C.dangerBorder : C.border}`,
                    borderLeft: `3px solid ${isDone ? C.successMid : isOverdue ? C.danger : C.navy}`,
                    borderRadius: 10,
                    transition: "all .15s",
                    opacity: isDone ? 0.75 : 1,
                  }}>
                    {/* Checkbox */}
                    <div
                      onClick={() => canComplete && completeItem(item.id)}
                      style={{
                        width: 22, height: 22, borderRadius: 6,
                        border: `2px solid ${isDone ? C.successMid : isOverdue ? C.danger : C.border}`,
                        background: isDone ? C.successMid : "transparent",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        cursor: canComplete ? "pointer" : "default",
                        flexShrink: 0, fontSize: 12, color: C.white,
                        transition: "all .15s",
                      }}
                      title={canComplete ? "Đánh dấu hoàn thành" : noPermissionReason}
                    >
                      {isDone ? "✓" : ""}
                    </div>

                    {/* Content */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ fontSize: 14, flexShrink: 0 }}>{catIcons[item.category] || "📌"}</span>
                        <p style={{
                          fontWeight: 600, fontSize: 13,
                          textDecoration: isDone ? "line-through" : "none",
                          color: isDone ? C.textLight : C.text,
                          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                        }}>
                          {item.title}
                        </p>
                        {/* Compliance flag */}
                        {item.is_compliance && (
                          <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 20, background: C.orangeBg, color: C.orange, whiteSpace: "nowrap", flexShrink: 0 }}>
                            Compliance
                          </span>
                        )}
                        {/* Owner badge: hiển thị cho HR và Manager để biết mục thuộc ai */}
                        {(isHR || isManager) && (
                          <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 20, background: item.owner === "new_hire" ? C.infoBg : item.owner === "manager" ? C.navyGhost : "#f3e5f5", color: item.owner === "new_hire" ? C.info : item.owner === "manager" ? C.navy : "#7b1fa2", whiteSpace: "nowrap", flexShrink: 0 }}>
                            {item.owner === "new_hire" ? "👤 NV" : item.owner === "manager" ? "👔 Manager" : "🔧 " + item.owner}
                          </span>
                        )}
                        {/* Lock icon: khi user không có quyền tác động */}
                        {!canComplete && !isDone && (
                          <span style={{ fontSize: 12, color: C.textLight, flexShrink: 0 }} title={noPermissionReason}>🔒</span>
                        )}
                      </div>
                      {/* Deadline */}
                      <p style={{ fontSize: 11, marginTop: 3, color: isOverdue ? C.danger : C.textLight, fontWeight: isOverdue ? 700 : 400 }}>
                        📅 Hạn: {item.deadline_date}
                        {isOverdue && <span> · ⚠ Quá hạn</span>}
                      </p>
                    </div>

                    {/* Status pill */}
                    <StatusPill status={item.status} />
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {/* ── Completion celebration ── */}
      {pct === 100 && (
        <Card style={{ textAlign: "center", padding: "28px 22px", background: C.successBg, border: `1px solid ${C.successBorder}` }}>
          <p style={{ fontSize: 28, marginBottom: 8 }}>🎉</p>
          <p style={{ fontSize: 16, fontWeight: 800, color: C.successMid }}>Bạn đã hoàn thành toàn bộ checklist onboarding!</p>
          <p style={{ fontSize: 13, color: C.successMid, marginTop: 4 }}>Chúc mừng — hãy báo HR để được xác nhận và nhận badge nhân viên chính thức.</p>
        </Card>
      )}
    </div>
  );
};

// ─── Preboarding Page ───
const PreboardingPage = ({ user, toast }) => {
  const isHR = roleIs(user, "hr_admin");
  const isNewHire = roleIs(user, "nhan_vien_moi");

  // NV mới chỉ thấy giấy tờ của chính mình (mock: employee e1 = Nguyễn Văn An = nhan_vien_moi)
  const ownEmp = MOCK_EMP.find(e => e.vai_tro === "nhan_vien_moi") || MOCK_EMP[0];
  const [selectedEmp, setSelectedEmp] = useState(isNewHire ? ownEmp : MOCK_EMP[3]);
  const [docs, setDocs] = useState(MOCK_DOCS);
  const [rejectModal, setRejectModal] = useState(null);
  const [rejectReason, setRejectReason] = useState("");
  const [actionLoading, setActionLoading] = useState({});
  const fileRefs = useRef({});

  // Fetch real preboarding docs from backend
  useEffect(() => {
    (async () => {
      try {
        const res = await apiClient.getPreboarding(selectedEmp.id);
        if (res.success && res.data?.documents?.length > 0) {
          setDocs(res.data.documents);
        }
      } catch {}
    })();
  }, [selectedEmp.id]);

  const verify = async (doc) => {
    setActionLoading(p => ({ ...p, [doc.id]: "verifying" }));
    const res = await apiClient.verifyDoc(selectedEmp.id, doc.id, user.id);
    setActionLoading(p => ({ ...p, [doc.id]: null }));
    setDocs(p => p.map(d => d.id === doc.id ? { ...d, status: "verified" } : d));
    toast(`✅ Đã xác nhận hợp lệ: ${doc.document_label}`, "success");
  };

  const reject = async () => {
    const doc = docs.find(d => d.id === rejectModal);
    setActionLoading(p => ({ ...p, [rejectModal]: "rejecting" }));
    const res = await apiClient.rejectDoc(selectedEmp.id, rejectModal, rejectReason);
    setActionLoading(p => ({ ...p, [rejectModal]: null }));
    setDocs(p => p.map(d => d.id === rejectModal ? { ...d, status: "rejected", rejected_reason: rejectReason } : d));
    setRejectModal(null); setRejectReason("");
    toast(`Đã từ chối — nhân viên sẽ được yêu cầu nộp lại: ${doc?.document_label}`, "warn");
  };

  const handleUpload = (docId, e) => {
    const file = e.target.files[0];
    if (!file) return;
    setDocs(p => p.map(d => d.id === docId ? { ...d, status: "uploaded", filename: file.name, uploaded_at: new Date().toISOString().slice(0, 10) } : d));
    toast(`📎 Đã upload: ${file.name} — chờ HR xác nhận`, "info");
  };

  const total = docs.length, verified = docs.filter(d => d.status === "verified").length, uploaded = docs.filter(d => d.status === "uploaded").length, missing = docs.filter(d => d.status === "missing" || d.status === "rejected").length;
  const pct = Math.round((verified / total) * 100);

  const docIcons = { cmnd: "🪪", photo_3x4: "🖼", so_bhxh: "📘", bang_cap: "🎓", so_tai_khoan: "🏦" };
  const stateIcon = { missing: "○", uploaded: "◑", verified: "●", rejected: "✕" };
  const stateColor = { missing: C.textLight, uploaded: C.info, verified: C.successMid, rejected: C.danger };

  return (
    <div style={{ animation: "fadeIn .2s ease" }}>
      <div style={{ padding: "24px 0 18px" }}>
        <h2 style={{ fontSize: 22, fontWeight: 800 }}>Giấy tờ Preboarding</h2>
        <p style={{ color: C.textMid, fontSize: 13, marginTop: 3 }}>
          {isNewHire ? "Upload và theo dõi giấy tờ của bạn" : "Upload, xác nhận và quản lý hồ sơ nhân viên mới"}
        </p>
      </div>

      {/* Thông báo phân quyền cho NV mới */}
      {isNewHire && (
        <div style={{ marginBottom: 14 }}>
          <InfoBox type="info">
            Bạn chỉ có thể upload giấy tờ của chính mình. Việc xác nhận hợp lệ sẽ do <strong>HR</strong> thực hiện.
          </InfoBox>
        </div>
      )}

      <div style={{ display: "flex", gap: 14, marginBottom: 18, flexWrap: "wrap", alignItems: "flex-end" }}>
        {/* Chỉ HR mới thấy dropdown chọn nhân viên */}
        {isHR && (
        <div>
          <label style={{ display: "block", fontSize: 11, fontWeight: 700, color: C.textMid, marginBottom: 5, textTransform: "uppercase", letterSpacing: 0.4 }}>Nhân viên</label>
          <select value={selectedEmp.id} onChange={e => { setSelectedEmp(MOCK_EMP.find(m => m.id === e.target.value)); setDocs(MOCK_DOCS); }} style={{ minWidth: 260 }}>
            {MOCK_EMP.map(emp => <option key={emp.id} value={emp.id}>{emp.full_name} — {emp.department}</option>)}
          </select>
        </div>
        )}
        {/* NV mới thấy tên của mình */}
        {isNewHire && (
          <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "8px 14px", background: C.navyFaint, borderRadius: 8 }}>
            <Avatar name={selectedEmp.full_name} size={28} />
            <div>
              <p style={{ fontSize: 13, fontWeight: 700 }}>{selectedEmp.full_name}</p>
              <p style={{ fontSize: 11, color: C.textMid }}>{selectedEmp.role} · {selectedEmp.department}</p>
            </div>
          </div>
        )}
        <div style={{ display: "flex", gap: 10 }}>
          {[{ label: "Hợp lệ", val: verified, bg: C.successBg, tc: C.successMid }, { label: "Chờ duyệt", val: uploaded, bg: C.infoBg, tc: C.info }, { label: "Thiếu/Từ chối", val: missing, bg: C.dangerBg, tc: C.danger }].map(s => (
            <div key={s.label} style={{ background: s.bg, borderRadius: 8, padding: "10px 16px", textAlign: "center", minWidth: 90 }}>
              <p style={{ fontSize: 20, fontWeight: 800, color: s.tc }}>{s.val}</p>
              <p style={{ fontSize: 11, color: s.tc, fontWeight: 600 }}>{s.label}</p>
            </div>
          ))}
        </div>
        <div style={{ marginLeft: "auto" }}>
          <p style={{ fontSize: 11, color: C.textMid, marginBottom: 3, fontWeight: 700 }}>Hoàn chỉnh hồ sơ</p>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 120, height: 7, background: C.border, borderRadius: 4 }}>
              <div style={{ width: `${pct}%`, height: "100%", background: pct === 100 ? C.successMid : C.navy, borderRadius: 4 }} />
            </div>
            <span style={{ fontSize: 13, fontWeight: 800, color: pct === 100 ? C.successMid : C.navy }}>{pct}%</span>
          </div>
        </div>
      </div>

      {isHR && uploaded > 0 && (
        <InfoBox type="info">
          <strong>{uploaded} giấy tờ đang chờ HR xác nhận.</strong> Kiểm tra kỹ trước khi duyệt — sau khi duyệt nhân viên sẽ nhận thông báo.
        </InfoBox>
      )}
      <div style={{ height: 12 }} />

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {docs.map(doc => {
          const borderColor = { missing: C.border, uploaded: C.info, verified: C.successMid, rejected: C.danger }[doc.status];
          const isLoading = actionLoading[doc.id];
          return (
            <Card key={doc.id} style={{ borderLeft: `3px solid ${borderColor}`, padding: "14px 18px" }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 13 }}>
                <div style={{ fontSize: 24, flexShrink: 0, marginTop: 2 }}>{docIcons[doc.document_type] || "📄"}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 4 }}>
                    <p style={{ fontWeight: 700, fontSize: 14 }}>{doc.document_label}</p>
                    <span style={{ fontSize: 14, color: stateColor[doc.status], fontWeight: 800 }}>{stateIcon[doc.status]}</span>
                    <Badge color={statusColorMap(doc.status)}>{statusLabel(doc.status)}</Badge>
                  </div>
                  {doc.filename && <p style={{ fontSize: 12, color: C.textMid }}>📎 {doc.filename}{doc.uploaded_at ? ` · ${doc.uploaded_at}` : ""}</p>}
                  {doc.rejected_reason && (
                    <div style={{ marginTop: 6, background: C.dangerBg, border: `1px solid ${C.dangerBorder}`, borderRadius: 6, padding: "6px 10px", fontSize: 12, color: C.danger }}>
                      ⚠️ Lý do từ chối: {doc.rejected_reason}
                    </div>
                  )}
                </div>
                <div style={{ display: "flex", gap: 7, flexShrink: 0, flexWrap: "wrap", justifyContent: "flex-end" }}>
                  {/* Upload: chỉ NV mới upload giấy tờ của mình, hoặc HR upload hộ (không cho) */}
                  {isNewHire && (doc.status === "missing" || doc.status === "rejected") && (
                    <>
                      <input ref={el => fileRefs.current[doc.id] = el} type="file" onChange={e => handleUpload(doc.id, e)} style={{ display: "none" }} accept=".jpg,.jpeg,.png,.pdf" />
                      <Btn size="sm" variant="secondary" onClick={() => fileRefs.current[doc.id]?.click()} icon="📎">Upload</Btn>
                    </>
                  )}
                  {/* HR: xác nhận và từ chối */}
                  {isHR && doc.status === "uploaded" && (
                    <>
                      <Btn size="sm" variant="success" loading={isLoading === "verifying"} onClick={() => verify(doc)}>✓ Xác nhận</Btn>
                      <Btn size="sm" variant="danger" loading={isLoading === "rejecting"} onClick={() => { setRejectModal(doc.id); setRejectReason(""); }}>✕ Từ chối</Btn>
                    </>
                  )}
                  {/* NV mới: thấy trạng thái chờ duyệt nếu đã upload */}
                  {isNewHire && doc.status === "uploaded" && (
                    <span style={{ fontSize: 12, color: C.info, fontWeight: 700, padding: "5px 0" }}>⏳ Chờ HR xác nhận</span>
                  )}
                  {doc.status === "verified" && <span style={{ fontSize: 12, color: C.successMid, fontWeight: 700, padding: "5px 0" }}>✅ Đã xác nhận</span>}
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {rejectModal && (
        <Modal title="Từ chối giấy tờ" onClose={() => setRejectModal(null)}>
          <InfoBox type="warn">Nhân viên sẽ nhận thông báo và được yêu cầu nộp lại. Vui lòng ghi rõ lý do.</InfoBox>
          <div style={{ height: 14 }} />
          <Field label="Lý do từ chối" required>
            <textarea value={rejectReason} onChange={e => setRejectReason(e.target.value)} rows={3} style={{ resize: "vertical" }} placeholder="Ví dụ: Ảnh bị mờ, vui lòng chụp lại rõ hơn..." />
          </Field>
          <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 6 }}>
            <Btn variant="ghost" onClick={() => setRejectModal(null)}>Hủy</Btn>
            <Btn variant="danger" onClick={reject} disabled={!rejectReason.trim()}>Xác nhận từ chối</Btn>
          </div>
        </Modal>
      )}
    </div>
  );
};

// ─── NewHire Welcome Banner (shown at top of Chat for nhan_vien_moi) ───
// ─── NewHire Dashboard Page (trang riêng — menu "Trang chủ") ───
const NewHireDashboardPage = ({ user, onNav }) => {
  const emp = MOCK_EMP.find(e => e.vai_tro === "nhan_vien_moi") || MOCK_EMP[0];

  // Checklist progress (chỉ các mục của NV mới)
  const myItems = MOCK_CHECKLIST_ITEMS.filter(i => i.owner === "new_hire");
  const done = myItems.filter(i => i.status === "hoan_thanh").length;
  const inProgress = myItems.filter(i => i.status === "dang_lam").length;
  const pct = Math.round((done / myItems.length) * 100);

  // Docs progress
  const docsVerified = MOCK_DOCS.filter(d => d.status === "verified").length;
  const docsUploaded = MOCK_DOCS.filter(d => d.status === "uploaded").length;
  const docsMissing = MOCK_DOCS.filter(d => d.status === "missing" || d.status === "rejected").length;
  const docsTotal = MOCK_DOCS.length;
  const docsPct = Math.round((docsVerified / docsTotal) * 100);

  const daysUntilStart = Math.ceil((new Date(emp.start_date) - new Date()) / 86400000);
  const startLabel = daysUntilStart > 0
    ? `Còn ${daysUntilStart} ngày đến ngày bắt đầu (${emp.start_date})`
    : daysUntilStart === 0 ? "Hôm nay là ngày đầu tiên! 🎉"
    : "Đang trong quá trình onboarding";

  // Next pending checklist item
  const nextItem = myItems.find(i => i.status !== "hoan_thanh");

  return (
    <div style={{ maxWidth: 680, margin: "0 auto", animation: "fadeIn .2s ease", paddingBottom: 32 }}>

      {/* ── Hero greeting ── */}
      <div style={{
        background: `linear-gradient(135deg, ${C.navyDark} 0%, ${C.navyLight} 100%)`,
        borderRadius: 16, padding: "28px 28px 24px", marginTop: 24, marginBottom: 22,
        color: C.white, position: "relative", overflow: "hidden",
      }}>
        <div style={{ position: "absolute", right: -20, top: -20, width: 160, height: 160, borderRadius: "50%", background: "rgba(255,255,255,.05)", pointerEvents: "none" }} />
        <div style={{ position: "absolute", right: 50, bottom: -60, width: 120, height: 120, borderRadius: "50%", background: "rgba(255,255,255,.04)", pointerEvents: "none" }} />

        <div style={{ display: "flex", alignItems: "center", gap: 14, position: "relative" }}>
          <div style={{ width: 50, height: 50, borderRadius: 14, background: "rgba(255,255,255,.15)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24, flexShrink: 0 }}>👋</div>
          <div>
            <p style={{ fontSize: 20, fontWeight: 800, lineHeight: 1.3 }}>
              Chào mừng, {user?.full_name}!
            </p>
            <p style={{ fontSize: 13, color: "rgba(255,255,255,.75)", marginTop: 4 }}>{startLabel}</p>
          </div>
        </div>

        <p style={{ fontSize: 13, color: "rgba(255,255,255,.65)", marginTop: 18, lineHeight: 1.7, position: "relative" }}>
          Chúng tôi rất vui khi có bạn trong đội ngũ. Hãy bắt đầu bằng cách hoàn thành checklist onboarding và nộp đầy đủ giấy tờ.
          Nếu cần hỗ trợ, <strong style={{ color: "rgba(255,255,255,.9)" }}>AI Chatbot</strong> luôn sẵn sàng giải đáp 24/7.
        </p>
      </div>

      {/* ── Checklist tiến độ ── */}
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 18 }}>✅</span>
            <h3 style={{ fontSize: 15, fontWeight: 700 }}>Checklist onboarding của tôi</h3>
          </div>
          <Btn size="sm" variant="secondary" onClick={() => onNav("checklist")}>Xem chi tiết →</Btn>
        </div>

        {/* Progress bar */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span style={{ fontSize: 12, color: C.textMid, fontWeight: 600 }}>Tiến độ</span>
            <span style={{ fontSize: 14, fontWeight: 800, color: pct === 100 ? C.successMid : C.navy }}>{pct}%</span>
          </div>
          <div style={{ height: 8, background: C.borderLight, borderRadius: 6 }}>
            <div style={{ width: `${pct}%`, height: "100%", background: pct === 100 ? C.successMid : `linear-gradient(90deg, ${C.navy}, ${C.navyLight})`, borderRadius: 6, transition: "width .5s ease" }} />
          </div>
        </div>

        {/* Stats row */}
        <div style={{ display: "flex", gap: 10 }}>
          {[
            { val: done, label: "Hoàn thành", bg: C.successBg, color: C.successMid },
            { val: inProgress, label: "Đang làm", bg: C.infoBg, color: C.info },
            { val: myItems.length - done - inProgress, label: "Chưa bắt đầu", bg: C.navyFaint, color: C.textMid },
          ].map(s => (
            <div key={s.label} style={{ flex: 1, background: s.bg, borderRadius: 8, padding: "10px 12px", textAlign: "center" }}>
              <p style={{ fontSize: 20, fontWeight: 800, color: s.color }}>{s.val}</p>
              <p style={{ fontSize: 11, color: s.color, fontWeight: 600, marginTop: 2 }}>{s.label}</p>
            </div>
          ))}
        </div>

        {/* Next task hint */}
        {nextItem && (
          <div style={{ marginTop: 12, padding: "10px 14px", background: C.navyFaint, borderRadius: 8, display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 14 }}>👉</span>
            <div>
              <p style={{ fontSize: 12, color: C.textMid, fontWeight: 600 }}>Mục tiếp theo cần làm:</p>
              <p style={{ fontSize: 13, fontWeight: 700, color: C.text, marginTop: 2 }}>{nextItem.title}</p>
              {nextItem.deadline_date && <p style={{ fontSize: 11, color: C.textLight, marginTop: 1 }}>📅 Hạn: {nextItem.deadline_date}</p>}
            </div>
          </div>
        )}
      </Card>

      {/* ── Giấy tờ preboarding ── */}
      <Card style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 18 }}>📄</span>
            <h3 style={{ fontSize: 15, fontWeight: 700 }}>Hồ sơ giấy tờ</h3>
          </div>
          <Btn size="sm" variant="secondary" onClick={() => onNav("preboarding")}>Nộp giấy tờ →</Btn>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
          <span style={{ fontSize: 12, color: C.textMid, fontWeight: 600 }}>Đã xác nhận</span>
          <span style={{ fontSize: 14, fontWeight: 800, color: docsPct === 100 ? C.successMid : C.navy }}>{docsPct}%</span>
        </div>
        <div style={{ height: 8, background: C.borderLight, borderRadius: 6, marginBottom: 12 }}>
          <div style={{ width: `${docsPct}%`, height: "100%", background: docsPct === 100 ? C.successMid : C.orange, borderRadius: 6, transition: "width .5s ease" }} />
        </div>

        <div style={{ display: "flex", gap: 10 }}>
          {[
            { val: docsVerified, label: "Hợp lệ", bg: C.successBg, color: C.successMid },
            { val: docsUploaded, label: "Chờ duyệt", bg: C.infoBg, color: C.info },
            { val: docsMissing, label: "Cần nộp", bg: C.dangerBg, color: C.danger },
          ].map(s => (
            <div key={s.label} style={{ flex: 1, background: s.bg, borderRadius: 8, padding: "10px 12px", textAlign: "center" }}>
              <p style={{ fontSize: 20, fontWeight: 800, color: s.color }}>{s.val}</p>
              <p style={{ fontSize: 11, color: s.color, fontWeight: 600, marginTop: 2 }}>{s.label}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* ── Hướng dẫn nhanh ── */}
      <Card>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
          <span style={{ fontSize: 18 }}>💡</span>
          <h3 style={{ fontSize: 15, fontWeight: 700 }}>Bắt đầu từ đâu?</h3>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {[
            { icon: "✅", text: "Hoàn thành checklist onboarding — tick từng mục khi xong.", action: "checklist", btn: "Mở Checklist" },
            { icon: "📄", text: "Nộp đầy đủ giấy tờ để HR có thể xác nhận hồ sơ của bạn.", action: "preboarding", btn: "Nộp giấy tờ" },
            { icon: "💬", text: "Có câu hỏi về chính sách, quy trình, tools? Hỏi AI Chatbot ngay.", action: "chat", btn: "Mở Chatbot" },
          ].map(g => (
            <div key={g.icon} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", background: C.navyFaint, borderRadius: 10 }}>
              <span style={{ fontSize: 20, flexShrink: 0 }}>{g.icon}</span>
              <p style={{ flex: 1, fontSize: 13, color: C.text, lineHeight: 1.5 }}>{g.text}</p>
              <Btn size="xs" variant="secondary" onClick={() => onNav(g.action)}>{g.btn}</Btn>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};

// ─── Smart Fallback for ChatPage (khi API không khả dụng) ───
const getSmartFallback = (question, user = {}) => {
  const q = question.toLowerCase();
  const roleLabel = { hr_admin: "HR Admin", quan_ly: "Quản lý / Manager", nhan_vien_moi: "Nhân viên mới", it_admin: "IT Admin" };

  // Lời chào
  if (q.match(/^(xin chào|chào|hello|hi|hey|helo|alo|chào bạn|xin chào bạn)[!,.\s]*$/) || q === "xin chào" || q === "chào" || q === "hello" || q === "hi") {
    const name = user.full_name || "bạn";
    let greeting = "";
    if (user.vai_tro === "nhan_vien_moi") {
      greeting = `Xin chào ${name}! 👋 Rất vui được đồng hành cùng bạn trong hành trình onboarding. Nếu cần hỗ trợ gì — về chính sách, quy trình, hay bất kỳ thắc mắc nào — hãy cứ hỏi tôi nhé!`;
    } else if (user.vai_tro === "quan_ly") {
      greeting = `Xin chào ${name}! 👔 Rất vui được hỗ trợ bạn hôm nay. Tôi có thể giúp bạn tra cứu chính sách, quy trình nội bộ, hay bất kỳ câu hỏi nào về team — cứ hỏi thoải mái nhé!`;
    } else if (user.vai_tro === "hr_admin") {
      greeting = `Xin chào ${name}! 🧑‍💼 Rất vui được hỗ trợ bạn. Tôi sẵn sàng giúp bạn tra cứu thông tin, giải đáp thắc mắc về onboarding, hoặc bất kỳ vấn đề nào bạn cần!`;
    } else {
      greeting = `Xin chào ${name}! 😊 Rất vui được gặp bạn! Nếu cần hỗ trợ gì, hãy cho tôi biết nhé!`;
    }
    return { text: greeting, sources: [] };
  }

  // Câu hỏi về danh tính bản thân
  if (q.includes("tôi là ai") || q.includes("tên tôi") || q.includes("vai trò của tôi") || q.includes("thông tin của tôi") || q.includes("tài khoản của tôi")) {
    // Lấy trực tiếp từ user object (đã được enrich từ login/MOCK_ACCOUNTS)
    const name = user.full_name || "bạn";
    const jobTitle = user.role || null;          // vd: "Software Engineer"
    const dept = user.department || null;        // vd: "Engineering"

    // Tạo câu chào tự nhiên, đầy đủ thông tin, không máy móc
    const titlePart = jobTitle ? `**${jobTitle}**` : null;
    const deptPart = dept ? `phòng **${dept}**` : null;
    const infoLine = [titlePart, deptPart].filter(Boolean).join(", ");

    let greeting = "";
    if (user.vai_tro === "nhan_vien_moi") {
      greeting = `Xin chào **${name}**! 👋 ${infoLine ? `Bạn đang là ${infoLine}.` : ""} Rất vui được đồng hành cùng bạn trong hành trình onboarding — nếu có bất cứ câu hỏi nào, cứ hỏi tôi nhé!`;
    } else if (user.vai_tro === "quan_ly") {
      greeting = `Xin chào **${name}**! 👔 ${infoLine ? `Bạn là ${infoLine}.` : ""} Nếu cần hỗ trợ gì về team hay quy trình nội bộ, hãy cứ hỏi tôi nhé!`;
    } else if (user.vai_tro === "hr_admin") {
      greeting = `Xin chào **${name}**! 🧑‍💼 ${infoLine ? `Bạn là ${infoLine}.` : ""} Tôi sẵn sàng hỗ trợ bạn quản lý onboarding và giải đáp mọi thắc mắc!`;
    } else {
      greeting = `Xin chào **${name}**! 😊 ${infoLine ? `Bạn là ${infoLine}.` : ""} Hãy cho tôi biết nếu bạn cần hỗ trợ gì nhé!`;
    }

    greeting += `\n\nNếu cần hỗ trợ gì trong quá trình làm việc, đừng ngại hỏi tôi nhé! 😊`;

    return { text: greeting, sources: [] };
  }

  // Nghỉ phép
  if (q.includes("nghỉ phép") || q.includes("phép năm") || q.includes("ngày phép") || q.includes("xin nghỉ")) {
    return {
      text: `Theo **[DOC-001] Chính sách Nghỉ phép**:\n\n• **Nghỉ phép năm:** 12 ngày/năm, được hưởng sau 6 tháng thử việc. Tích lũy 1 ngày/tháng.\n• **Nghỉ ốm:** 5 ngày/năm có lương (cần giấy bác sĩ nếu nghỉ ≥ 2 ngày liên tiếp).\n• **Nghỉ thai sản:** Nữ 6 tháng, nam 10 ngày khi vợ sinh.\n• **Nghỉ lễ:** 11 ngày nhà nước + 2 ngày công ty.\n\n**Quy trình xin nghỉ:**\n1. Nộp đơn qua HR Portal: hr.company.com\n2. Tối thiểu 3 ngày làm việc trước\n3. Cần Manager approve\n4. Nghỉ đột xuất: nhắn Slack #leave-requests + gọi trực tiếp cho Manager`,
      sources: ["DOC-001"],
    };
  }

  // Lương thưởng
  if (q.includes("lương") || q.includes("thưởng") || q.includes("kpi") || q.includes("phúc lợi") || q.includes("bhxh") || q.includes("wfh") || q.includes("ăn trưa")) {
    return {
      text: `Theo **[DOC-002] Chính sách Lương & Phúc lợi**:\n\n• **Ngày trả lương:** 25 hàng tháng qua chuyển khoản.\n• **Thưởng KPI:** 0–30% lương tháng, đánh giá hàng quý.\n• **Thưởng Tết (tháng 13):** Áp dụng nhân viên đủ 1 năm, trả trước Tết Nguyên Đán.\n• **BHXH/BHYT/BHTN:** Đóng đầy đủ theo quy định. Đăng ký thẻ BHYT tại HR trong tuần đầu.\n• **Phụ cấp ăn trưa:** 30.000đ/ngày làm thực tế (không áp dụng WFH).\n• **WFH:** Tối đa 2 ngày/tuần sau thử việc. Tuần đầu onboarding yêu cầu đi làm full.`,
      sources: ["DOC-002"],
    };
  }

  // IT / Setup / Công cụ
  if (q.includes("laptop") || q.includes("vpn") || q.includes("email") || q.includes("tài khoản") || q.includes("slack") || q.includes("jira") || q.includes("password") || q.includes("mật khẩu") || q.includes("it") || q.includes("setup") || q.includes("tool") || q.includes("công cụ")) {
    return {
      text: `Theo **[DOC-003] IT Setup & Công cụ**:\n\n• **Laptop:** Nhận tại IT room (tầng 3) ngày đầu tiên. Ký biên bản bàn giao.\n• **VPN:** Cài GlobalProtect, server vpn.company.com, đăng nhập bằng email công ty.\n• **Email & accounts:** IT setup trong 24h đầu. Nếu chưa có → Slack #it-support hoặc tạo ticket tại it.company.com.\n• **Công cụ chính:** Slack (chat), Jira (tasks), Confluence (docs), GitHub/GitLab (code), Figma (design).\n• **Password:** Tối thiểu 12 ký tự, thay đổi mỗi 90 ngày, bắt buộc bật 2FA.\n• **Quên mật khẩu:** self-service tại accounts.company.com hoặc liên hệ IT.\n\n💡 Bạn muốn tôi tạo IT ticket hỗ trợ không?`,
      sources: ["DOC-003"],
    };
  }

  // Văn hóa / giờ làm việc
  if (q.includes("giờ làm") || q.includes("check-in") || q.includes("dress code") || q.includes("văn hóa") || q.includes("meeting") || q.includes("all-hands") || q.includes("1-on-1") || q.includes("đi muộn")) {
    return {
      text: `Theo **[DOC-004] Văn hóa & Quy trình Công ty**:\n\n• **Giờ làm việc:** 8:30–17:30, nghỉ trưa 12:00–13:00. Flexible ±30 phút nếu đủ 8h/ngày.\n• **Check-in/out:** Quẹt thẻ hoặc app HRM. Đi muộn >15 phút cần báo Manager.\n• **Dress code:** Smart casual. Thứ 6 là Casual Friday (không shorts/dép tông).\n• **All-hands meeting:** Thứ 2 đầu tháng, 9:00–10:00.\n• **1-on-1 với Manager:** Hàng tuần, 30 phút.\n• **Code of conduct:** Tôn trọng, không phân biệt đối xử. Báo cáo vi phạm: hr@company.com.`,
      sources: ["DOC-004"],
    };
  }

  // Onboarding / tuần đầu
  if (q.includes("tuần đầu") || q.includes("ngày đầu") || q.includes("onboarding") || q.includes("buddy") || q.includes("30-60-90") || q.includes("orientation") || q.includes("bắt đầu")) {
    return {
      text: `Theo **[DOC-005] Hướng dẫn Onboarding**:\n\n**Ngày 1:**\n• Nhận laptop + badge tại IT room (tầng 3)\n• HR Orientation lúc 9:00 tại phòng họp A3\n• Lunch với team\n\n**Tuần 1:**\n• Setup toàn bộ công cụ (xem DOC-003)\n• Đọc tài liệu nội bộ trên Confluence\n• 1-on-1 đầu tiên với Manager\n\n**Tuần 2–4:**\n• Shadow đồng nghiệp\n• Hoàn thành training bắt buộc (Security, Data Privacy)\n\n**Milestone quan trọng:**\n• 30 ngày: Set goals với Manager\n• 60 ngày: Mid-point review\n• 90 ngày: Formal review chính thức\n\n• **Buddy Program:** Bạn sẽ được assign 1 buddy từ team khác để hỗ trợ culture fit.`,
      sources: ["DOC-005"],
    };
  }

  // Đào tạo / phát triển
  if (q.includes("đào tạo") || q.includes("học") || q.includes("chứng chỉ") || q.includes("ngân sách") || q.includes("thăng tiến") || q.includes("training") || q.includes("phát triển")) {
    return {
      text: `Theo **[DOC-006] Chính sách Đào tạo & Phát triển**:\n\n• **Ngân sách đào tạo:** 5.000.000đ/người/năm cho khóa học, sách, hội thảo.\n• **Chứng chỉ:** Công ty hỗ trợ 100% phí thi chứng chỉ liên quan công việc (AWS, Google, PMP...).\n• **Internal training:** Thứ 4 hàng tuần, 17:00–18:00, chia sẻ kiến thức nội bộ.\n• **Lộ trình thăng tiến:** Review 6 tháng/lần. Junior → Mid → Senior → Lead.`,
      sources: ["DOC-006"],
    };
  }

  // Checklist
  if (q.includes("checklist") || q.includes("deadline") || q.includes("hoàn thành") || q.includes("việc cần làm") || q.includes("tick")) {
    return {
      text: `Về **Checklist Onboarding** của bạn:\n\nBạn có thể xem và tick hoàn thành các mục trong menu **Checklist** bên trái.\n\nCác mục ưu tiên theo tuần:\n• **Tuần 1:** Nộp hồ sơ đầy đủ, đọc nội quy, setup dev environment, Security Training\n• **Tuần 2:** 1-on-1 với Manager, Set 30-60-90 day goals\n\n💡 **Lưu ý:** Bạn chỉ tick được các mục có nhãn 👤 NV. Các mục của Manager hoặc IT sẽ có 🔒.\n\nNếu kế hoạch chưa được HR duyệt, bạn sẽ nhận email thông báo khi có thể bắt đầu.`,
      sources: ["DOC-005"],
    };
  }

  // Giấy tờ
  if (q.includes("giấy tờ") || q.includes("hồ sơ") || q.includes("cmnd") || q.includes("cccd") || q.includes("bằng cấp") || q.includes("nộp")) {
    return {
      text: `Về **Hồ sơ Preboarding**:\n\nBạn cần nộp các giấy tờ sau tại mục **Giấy tờ** trong menu:\n• 🪪 CMND/CCCD (mặt trước + mặt sau)\n• 🖼 Ảnh thẻ 3x4\n• 📘 Sổ BHXH (nếu có)\n• 🎓 Bằng đại học / cao đẳng\n• 🏦 Số tài khoản ngân hàng\n\n**Quy trình:**\n1. Upload file tại mục Giấy tờ\n2. HR sẽ xem xét và xác nhận\n3. Nếu bị từ chối → bạn sẽ nhận lý do và cần nộp lại\n\n💡 Nộp càng sớm càng tốt để không ảnh hưởng đến tiến độ onboarding!`,
      sources: [],
    };
  }

  // IT Ticket
  if (q.includes("it ticket") || q.includes("tạo ticket") || q.includes("escalate")) {
    return {
      text: `Để **tạo IT ticket**, bạn có 2 cách:\n\n1. **Tự tạo:** Truy cập it.company.com → Đăng nhập → New Ticket\n2. **Slack:** Nhắn vào channel **#it-support** mô tả vấn đề\n\n💡 Tôi có thể giúp bạn escalate IT ticket trực tiếp từ đây. Bạn có muốn tôi thực hiện không?`,
      sources: ["DOC-003"],
    };
  }

  // Default: câu hỏi không rõ hoặc không có trong KB
  return {
    text: `Tôi đã tìm kiếm trong knowledge base nhưng chưa có thông tin chính xác về câu hỏi này.\n\nBạn có thể hỏi tôi về:\n• 📋 **Chính sách nghỉ phép** (số ngày, quy trình xin nghỉ)\n• 💰 **Lương & phúc lợi** (ngày trả lương, thưởng KPI, WFH)\n• 💻 **IT Setup** (laptop, VPN, tài khoản, công cụ)\n• 🏢 **Văn hóa công ty** (giờ làm, dress code, meeting)\n• 🗓 **Onboarding tuần đầu** (lịch trình, buddy, mục tiêu 30-60-90)\n• 📚 **Đào tạo & phát triển** (ngân sách, chứng chỉ, thăng tiến)\n\nHoặc liên hệ HR trực tiếp qua: **hr@company.com** 📧`,
    sources: [],
  };
};

// ─── Chat Page ───
const ChatPage = ({ user, toast }) => {
  const isHR = roleIs(user, "hr_admin");
  const isManager = roleIs(user, "quan_ly");
  const isNewHire = roleIs(user, "nhan_vien_moi");

  // selfEmp: thông tin profile của chính user đang đăng nhập
  // Ưu tiên dùng user.id thật (UUID từ Supabase) — chỉ fallback mock nếu chưa có
  const selfEmp = {
    id: user.id,
    full_name: user.full_name,
    email: user.email,
    role: user.role || "Nhân viên",
    department: user.department || "N/A",
    vai_tro: user.vai_tro,
    seniority: user.seniority || "junior",
    start_date: user.start_date || "2026-01-01",
  };

  // HR có thể xem/tra cứu nhân viên khác; Manager & NV mới chỉ chat với context bản thân
  const [selectedEmp, setSelectedEmp] = useState(selfEmp);
  const [realEmps, setRealEmps] = useState([]);

  // Fetch real employees for HR dropdown
  useEffect(() => {
    if (isHR) {
      (async () => {
        try {
          const res = await apiClient.listEmployees();
          if (res.success && res.data?.length > 0) setRealEmps(res.data);
        } catch {}
      })();
    }
  }, [isHR]);

  // Greeting động theo vai trò
  const roleGreeting = isManager
    ? `Xin chào **${user?.full_name || "bạn"}**! 👋\n\nTôi là **AI Onboarding Assistant**. Với vai trò Quản lý, tôi có thể giúp bạn:\n• Tra cứu chính sách, quy trình nội bộ\n• Hỏi về checklist và deadline của nhân viên\n• Hướng dẫn quy trình duyệt/xác nhận\n• Giải đáp bất kỳ câu hỏi về công ty`
    : isNewHire
    ? `Xin chào **${user?.full_name || "bạn"}**! 👋 Rất vui được đồng hành cùng bạn trong hành trình onboarding!\n\nTôi là **AI Onboarding Assistant** — sẵn sàng hỗ trợ bạn:\n• Trả lời câu hỏi về chính sách, quy trình\n• Hướng dẫn setup tools, accounts\n• Giải thích checklist và deadline\n• Thực hiện các hành động (tạo IT ticket, update checklist)\n\nHãy cứ hỏi thoải mái nhé! 😊`
    : `Xin chào **${user?.full_name || "bạn"}**! 👋\n\nTôi là **AI Onboarding Assistant** — sẵn sàng hỗ trợ bạn:\n• Trả lời câu hỏi về chính sách, quy trình\n• Hướng dẫn setup tools, accounts\n• Giải thích checklist và deadline\n• Thực hiện các hành động (tạo IT ticket, update checklist)`;

  const [messages, setMessages] = useState([
    { id: "m0", role: "assistant", content: roleGreeting, created_at: new Date().toISOString(), feedback: null },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);



  const send = async () => {
    if (!input.trim()) return;
    const userMsg = { id: `m${Date.now()}`, role: "user", content: input, created_at: new Date().toISOString() };
    setMessages(p => [...p, userMsg]);
    const currentInput = input;
    setInput("");
    setLoading(true);

    try {
      // Call backend API
      const res = await apiClient.sendChat(selectedEmp.id, currentInput);
      
      if (!res.success) {
        throw new Error(res.error || "Lỗi khi gọi chatbot");
      }
      
      const { answer, sources, confidence, conversation_id } = res.data;

      setMessages(p => [...p, {
        id: `m${Date.now()}`,
        role: "assistant",
        content: answer,
        sources: sources || [],
        confidence: confidence || 0.9,
        created_at: new Date().toISOString(),
        feedback: null,
      }]);
    } catch (err) {
      console.error(err);
      // Smart fallback: answer from embedded knowledge base
      const fallbackAnswer = getSmartFallback(currentInput, user);
      setMessages(p => [...p, {
        id: `m${Date.now()}`,
        role: "assistant",
        content: fallbackAnswer.text,
        sources: fallbackAnswer.sources,
        confidence: 0.80,
        created_at: new Date().toISOString(),
        feedback: null,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const giveFeedback = async (id, fb) => {
    await apiClient.sendFeedback(id, fb);
    setMessages(p => p.map(m => m.id === id ? { ...m, feedback: fb } : m));
    toast(fb === "positive" ? "Cảm ơn phản hồi tích cực!" : "Ghi nhận — câu hỏi sẽ được chuyển cho HR xem xét", fb === "positive" ? "success" : "warn");
  };

  const SUGGESTIONS = isManager
    ? ["Tôi là ai?", "Chính sách nghỉ phép?", "Quy trình duyệt checklist?", "Nhân viên cần làm gì tuần đầu?"]
    : ["Chính sách nghỉ phép?", "Setup VPN thế nào?", "Quy trình xin lương thưởng?", "Tôi cần làm gì tuần đầu?"];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 60px)", maxWidth: 800, margin: "0 auto", animation: "fadeIn .2s ease" }}>

      <div style={{ padding: "20px 0 12px", flexShrink: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h2 style={{ fontSize: 22, fontWeight: 800 }}>AI Onboarding Chatbot</h2>
          </div>
          {/* HR: chọn nhân viên để tra cứu. Manager & NV mới: chỉ hiện tên + vai trò bản thân */}
          {isHR ? (
            <div style={{ minWidth: 200 }}>
              <select value={selectedEmp.id} onChange={e => {
                const empList = realEmps.length > 0 ? realEmps : MOCK_EMP;
                const found = empList.find(m => m.id === e.target.value);
                if (found) setSelectedEmp(found);
              }}>
                {(realEmps.length > 0 ? realEmps : MOCK_EMP).map(emp => <option key={emp.id} value={emp.id}>{emp.full_name}</option>)}
              </select>
            </div>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 12px", background: C.navyFaint, borderRadius: 8, border: `1px solid ${C.border}` }}>
              <Avatar name={user?.full_name} size={24} />
              <div>
                <span style={{ fontSize: 13, fontWeight: 700, color: C.text, display: "block" }}>{user?.full_name}</span>
                <span style={{ fontSize: 10, color: C.textMid }}>{{ quan_ly: "Quản lý", nhan_vien_moi: "Nhân viên mới", it_admin: "IT Admin" }[user?.vai_tro] || user?.vai_tro}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      <Card style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", padding: 0, minHeight: 0 }}>
        <div style={{ flex: 1, overflowY: "auto", padding: "18px 20px", display: "flex", flexDirection: "column", gap: 14 }}>
          {messages.map(msg => (
            <div key={msg.id} style={{ display: "flex", flexDirection: "column", alignItems: msg.role === "user" ? "flex-end" : "flex-start", gap: 5, animation: "slideIn .15s ease" }}>
              {msg.role === "assistant" && (
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 11, color: C.textLight, fontWeight: 600 }}>AI Assistant</span>
                </div>
              )}
              <div style={{ maxWidth: "80%", padding: "10px 14px", borderRadius: msg.role === "user" ? "14px 14px 4px 14px" : "4px 14px 14px 14px", background: msg.role === "user" ? C.navy : C.navyFaint, color: msg.role === "user" ? C.white : C.text, fontSize: 14, lineHeight: 1.65, whiteSpace: "pre-wrap" }}>
                {msg.content.replace(/\*\*(.*?)\*\*/g, "$1")}
              </div>
              {msg.role === "assistant" && msg.sources?.length > 0 && (() => {
                const DOC_NAMES = { "DOC-001": "Chính sách Nghỉ phép", "DOC-002": "Lương & Phúc lợi", "DOC-003": "IT Setup", "DOC-004": "Văn hóa Công ty", "DOC-005": "Onboarding Guide", "DOC-006": "Đào tạo & Phát triển" };
                return (
                  <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                    {msg.sources.map((s, i) => <Badge key={i} size="xs" color="navy">📖 {DOC_NAMES[s] || s}</Badge>)}
                  </div>
                );
              })()}
              {msg.role === "assistant" && msg.feedback === null && (
                <div style={{ display: "flex", gap: 6 }}>
                  <button onClick={() => giveFeedback(msg.id, "positive")} style={{ background: "none", border: `1px solid ${C.border}`, borderRadius: 6, padding: "3px 9px", cursor: "pointer", fontSize: 12, color: C.textMid, fontFamily: "Nunito, sans-serif" }}>👍 Hữu ích</button>
                  <button onClick={() => giveFeedback(msg.id, "negative")} style={{ background: "none", border: `1px solid ${C.border}`, borderRadius: 6, padding: "3px 9px", cursor: "pointer", fontSize: 12, color: C.textMid, fontFamily: "Nunito, sans-serif" }}>👎 Chưa đúng</button>
                </div>
              )}
              {msg.feedback && <span style={{ fontSize: 11, color: msg.feedback === "positive" ? C.successMid : C.warn, fontWeight: 600 }}>{msg.feedback === "positive" ? "✓ Đã ghi nhận phản hồi tích cực" : "✓ Câu hỏi chuyển HR xem xét · Sẽ cải thiện knowledge base"}</span>}
            </div>
          ))}
          {loading && (
            <div style={{ display: "flex", gap: 4, padding: "10px 14px", background: C.navyFaint, borderRadius: "4px 14px 14px 14px", width: "fit-content" }}>
              {[0, 1, 2].map(i => <div key={i} style={{ width: 6, height: 6, borderRadius: "50%", background: C.accent, animation: "bounce 1.2s infinite", animationDelay: `${i * 0.2}s` }} />)}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div style={{ padding: "10px 16px 8px", borderTop: `1px solid ${C.border}`, flexShrink: 0 }}>
          <div style={{ display: "flex", gap: 6, marginBottom: 8, flexWrap: "wrap" }}>
            {SUGGESTIONS.map(s => (
              <button key={s} onClick={() => setInput(s)} style={{ background: C.navyFaint, border: `1px solid ${C.border}`, borderRadius: 20, padding: "4px 11px", fontSize: 12, color: C.navy, fontWeight: 600, cursor: "pointer", fontFamily: "Nunito, sans-serif" }}>{s}</button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 9 }}>
            <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()} placeholder="Nhập câu hỏi... (Enter để gửi)" style={{ flex: 1 }} />
            <Btn onClick={send} disabled={!input.trim() || loading}>Gửi</Btn>
          </div>
        </div>
      </Card>
    </div>
  );
};

// ─── Reminders Page ───
const RemindersPage = ({ user, toast }) => {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [logs] = useState([
    { id: "r1", employee_name: "Phạm Đức Dũng", checklist_item_title: "Security Awareness Training", escalation_tier: 3, sent_to: "hr_admin", sent_to_role: "hr", message: "🚨 Cần xử lý: Phạm Đức Dũng bị kẹt tại 'Security Awareness Training' (quá hạn 3 ngày).", sent_at: "2026-04-19T08:00:00" },
    { id: "r2", employee_name: "Nguyễn Văn An", checklist_item_title: "Đọc nội quy công ty", escalation_tier: 1, sent_to: "an@company.com", sent_to_role: "employee", message: "⏰ Nhắc nhở: 'Đọc nội quy công ty' đã đến hạn.", sent_at: "2026-04-19T08:01:00" },
    { id: "r3", employee_name: "Trần Thị Bình", checklist_item_title: "1-on-1 với Manager tuần đầu", escalation_tier: 2, sent_to: "manager@company.com", sent_to_role: "manager", message: "📋 Trần Thị Bình chưa hoàn thành '1-on-1 với Manager tuần đầu' (quá hạn 2 ngày).", sent_at: "2026-04-18T14:00:00" },
  ]);

  const runReminders = async () => {
    setRunning(true);
    const res = await apiClient.runReminders();
    setRunning(false);
    if (res.success) {
      setResult(res.data);
      toast(`✅ Đã chạy reminders: ${res.data.reminders_sent} gửi — T1:${res.data.tier1_employee} T2:${res.data.tier2_manager} T3:${res.data.tier3_hr}`, "success");
    } else {
      const mock = { reminders_sent: 4, tier1_employee: 2, tier2_manager: 1, tier3_hr: 1, skipped_already_reminded: 0, date: new Date().toISOString().slice(0, 10) };
      setResult(mock);
      toast("Reminders chạy (mock): 4 gửi — 2 NV, 1 Manager, 1 HR", "info");
    }
  };

  const tierColor = t => ({ 1: "blue", 2: "yellow", 3: "red" })[t] || "gray";
  const tierLabel = t => ({ 1: "Tier 1 · Nhân viên", 2: "Tier 2 · Manager", 3: "Tier 3 · HR Alert" })[t];

  return (
    <div style={{ animation: "fadeIn .2s ease" }}>
      <div style={{ padding: "24px 0 18px", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 800 }}>Hệ thống Nhắc nhở</h2>
          <p style={{ color: C.textMid, fontSize: 13, marginTop: 3 }}>3-tier escalation · Tự động theo overdue hours</p>
        </div>
        <Btn onClick={runReminders} loading={running} icon="▶">Chạy reminder ngay</Btn>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 18 }}>
        {[{ tier: 1, label: "Tier 1 — Nhân viên", desc: "< 48h quá hạn", color: C.info, bg: C.infoBg }, { tier: 2, label: "Tier 2 — Manager", desc: "48–72h quá hạn", color: C.warn, bg: C.warnBg }, { tier: 3, label: "Tier 3 — HR + Đỏ", desc: "> 72h · health → đỏ", color: C.danger, bg: C.dangerBg }].map(t => (
          <Card key={t.tier} style={{ borderTop: `3px solid ${t.color}`, padding: "16px 18px" }}>
            <p style={{ fontSize: 14, fontWeight: 800, color: t.color }}>{t.label}</p>
            <p style={{ fontSize: 12, color: C.textMid, marginTop: 3 }}>{t.desc}</p>
            <p style={{ fontSize: 22, fontWeight: 800, color: t.color, marginTop: 10 }}>
              {result ? [result.tier1_employee, result.tier2_manager, result.tier3_hr][t.tier - 1] : logs.filter(l => l.escalation_tier === t.tier).length}
            </p>
            <p style={{ fontSize: 11, color: C.textLight }}>{result ? "lần chạy vừa rồi" : "trong logs"}</p>
          </Card>
        ))}
      </div>

      {result && (
        <InfoBox type="success">
          <strong>Kết quả lần chạy {result.date}:</strong> Tổng {result.reminders_sent} nhắc nhở gửi đi. Bỏ qua {result.skipped_already_reminded} (đã nhắc hôm nay). Tier 3 → health_score tự động chuyển đỏ + webhook <code style={{ fontFamily: "DM Mono, monospace", fontSize: 11, background: C.navyGhost, padding: "1px 5px", borderRadius: 4 }}>employee.risk.detected</code> fired.
        </InfoBox>
      )}
      <div style={{ height: 16 }} />

      <Card>
        <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 14 }}>📋 Lịch sử nhắc nhở gần nhất</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
          {logs.map(log => (
            <div key={log.id} style={{ display: "flex", gap: 12, padding: "11px 14px", background: C.navyFaint, borderRadius: 9, borderLeft: `3px solid ${({ 1: C.info, 2: C.warn, 3: C.danger })[log.escalation_tier]}` }}>
              <div style={{ flexShrink: 0, width: 80 }}>
                <Badge color={tierColor(log.escalation_tier)} size="xs">{`Tier ${log.escalation_tier}`}</Badge>
              </div>
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: 13, fontWeight: 700 }}>{log.employee_name} <span style={{ fontWeight: 400, color: C.textMid }}>— {log.checklist_item_title}</span></p>
                <p style={{ fontSize: 12, color: C.textMid, marginTop: 2 }}>{log.message}</p>
                <p style={{ fontSize: 11, color: C.textLight, marginTop: 2 }}>Gửi tới: {log.sent_to} · {new Date(log.sent_at).toLocaleString("vi-VN")}</p>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};

// ─── Mock Control Panel (PRD 7.4 — demo webhooks) ───
const MockPanelPage = ({ user, toast }) => {
  const [results, setResults] = useState({});
  const [loading, setLoading] = useState({});

  const triggers = [
    { id: "hris", icon: "🏢", label: "HRIS: Tạo NV mới", desc: "Webhook employee.created — tạo NV + generate checklist", endpoint: "employee.created", payload: { employee_code: `NV-2026-${String(Date.now()).slice(-3)}`, full_name: "Demo Nhân Viên", email: `demo${Date.now()}@company.com`, role: "Software Engineer", department: "Engineering", seniority: "junior", start_date: new Date(Date.now() + 7*86400000).toISOString().slice(0,10) } },
    { id: "lms", icon: "📚", label: "LMS: Hoàn thành training", desc: "Webhook training.completed — tick compliance checklist", endpoint: "training.completed", payload: { employee_code: "NV-2026-001", course_name: "Security Awareness Training", completion_date: new Date().toISOString().slice(0,10), score: 95 } },
    { id: "it", icon: "🔧", label: "IT: Ticket resolved", desc: "Webhook it.ticket.resolved — tick IT setup items", endpoint: "it.ticket.resolved", payload: { employee_code: "NV-2026-001", ticket_id: "IT-001", resolution: "Laptop đã setup xong, VPN configured" } },
    { id: "payroll", icon: "💰", label: "Payroll: Onboard xong", desc: "Webhook payroll.onboarded — xác nhận BHXH/tài khoản", endpoint: "payroll.onboarded", payload: { employee_code: "NV-2026-001", bank_verified: true, bhxh_registered: true } },
    { id: "email", icon: "✉️", label: "Email: Verify tài khoản", desc: "Webhook email.verified — xác nhận email công ty", endpoint: "email.verified", payload: { employee_code: "NV-2026-001", email: "nv@company.com", verified: true } },
  ];

  const fire = async (trigger) => {
    setLoading(p => ({ ...p, [trigger.id]: true }));
    const res = await apiClient.triggerWebhook(trigger.endpoint, trigger.payload);
    setLoading(p => ({ ...p, [trigger.id]: false }));
    setResults(p => ({ ...p, [trigger.id]: res }));
    toast(res.success ? `✅ Webhook ${trigger.endpoint} — thành công` : `⚠️ Webhook ${trigger.endpoint} — ${res.error || "backend offline, dùng mock"}`, res.success ? "success" : "warn");
  };

  return (
    <div style={{ animation: "fadeIn .2s ease", maxWidth: 780 }}>
      <div style={{ padding: "24px 0 18px" }}>
        <h2 style={{ fontSize: 22, fontWeight: 800 }}>🧪 Mock Control Panel</h2>
        <p style={{ color: C.textMid, fontSize: 13, marginTop: 3 }}>Giả lập webhook từ hệ thống bên ngoài — dùng để demo full flow</p>
      </div>

      <InfoBox type="info">
        Panel này mô phỏng các sự kiện từ HRIS, LMS, IT Ticketing, Payroll. Click từng nút để trigger webhook tương ứng qua backend API.
      </InfoBox>
      <div style={{ height: 16 }} />

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {triggers.map(t => (
          <Card key={t.id} style={{ borderLeft: `3px solid ${results[t.id]?.success ? C.successMid : C.navy}` }}>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <span style={{ fontSize: 28, flexShrink: 0 }}>{t.icon}</span>
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: 14, fontWeight: 700 }}>{t.label}</p>
                <p style={{ fontSize: 12, color: C.textMid, marginTop: 2 }}>{t.desc}</p>
                {results[t.id] && (
                  <div style={{ marginTop: 8, padding: "8px 10px", background: results[t.id].success ? C.successBg : C.warnBg, borderRadius: 6, fontSize: 12 }}>
                    <pre style={{ fontFamily: "DM Mono, monospace", fontSize: 11, whiteSpace: "pre-wrap", wordBreak: "break-all", margin: 0 }}>
                      {JSON.stringify(results[t.id].data || results[t.id], null, 2)}
                    </pre>
                  </div>
                )}
              </div>
              <Btn onClick={() => fire(t)} loading={loading[t.id]} variant={results[t.id]?.success ? "success" : "primary"} icon={results[t.id]?.success ? "✓" : "▶"}>
                {results[t.id]?.success ? "Đã chạy" : "Fire"}
              </Btn>
            </div>
          </Card>
        ))}
      </div>

      <Card style={{ marginTop: 20 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>📋 Demo Script gợi ý</h3>
        <div style={{ fontSize: 13, lineHeight: 1.8, color: C.textMid }}>
          <p><strong>1.</strong> Click <Badge color="navy" size="xs">HRIS: Tạo NV mới</Badge> → Hệ thống tạo NV + generate checklist tự động</p>
          <p><strong>2.</strong> Chuyển qua <strong>Checklist</strong> → Duyệt plan → Stakeholder tasks được tạo</p>
          <p><strong>3.</strong> Click <Badge color="navy" size="xs">LMS: Hoàn thành training</Badge> → Compliance items auto-tick</p>
          <p><strong>4.</strong> Click <Badge color="navy" size="xs">IT: Ticket resolved</Badge> → IT items auto-tick</p>
          <p><strong>5.</strong> Mở <strong>AI Chatbot</strong> → Hỏi "chính sách nghỉ phép" → RAG trả lời</p>
          <p><strong>6.</strong> Chuyển <strong>Dashboard</strong> → Xem analytics + AI Copilot tóm tắt</p>
        </div>
      </Card>
    </div>
  );
};

// ─── Root App ───
export default function App() {
  const auth = useAuth();

  // Trang mặc định tuỳ theo vai trò: NV mới → welcome (Trang chủ); HR/Manager → dashboard
  const defaultPage = (vai_tro) => {
    if (vai_tro === "nhan_vien_moi") return "welcome";
    return "dashboard";
  };

  const [page, setPage] = useState("dashboard"); // sẽ được ghi đè ngay sau login
  const [toasts, setToasts] = useState([]);

  // Khi user thay đổi (login/logout), reset về trang mặc định theo role
  useEffect(() => {
    if (auth.user) setPage(defaultPage(auth.user.vai_tro));
  }, [auth.user?.id]);

  const toast = useCallback((message, type = "success") => {
    const id = Date.now();
    setToasts(p => [...p, { id, message, type }]);
  }, []);

  const removeToast = useCallback((id) => setToasts(p => p.filter(t => t.id !== id)), []);

  if (!auth.user) {
    return (
      <>
        <style>{GS}</style>
        <LoginPage onLogin={auth.login} loading={auth.loading} error={auth.error} />
      </>
    );
  }

  const isNewHire = roleIs(auth.user, "nhan_vien_moi");

  // Guard: NV mới không được vào dashboard hay employees dù navigate trực tiếp
  const safePage = (p) => {
    if (isNewHire && (p === "dashboard" || p === "employees" || p === "reminders" || p === "mock_panel")) {
      return "welcome";
    }
    return p;
  };

  const navigate = (p) => setPage(safePage(p));

  const PAGES = {
    welcome: <NewHireDashboardPage user={auth.user} onNav={navigate} />,
    dashboard: <DashboardPage user={auth.user} toast={toast} />,
    employees: <EmployeesPage user={auth.user} toast={toast} />,
    checklist: <ChecklistPage user={auth.user} toast={toast} />,
    preboarding: <PreboardingPage user={auth.user} toast={toast} />,
    chat: <ChatPage user={auth.user} toast={toast} />,
    reminders: <RemindersPage user={auth.user} toast={toast} />,
    mock_panel: <MockPanelPage user={auth.user} toast={toast} />,
  };

  const currentPage = safePage(page);

  return (
    <>
      <style>{GS}</style>
      <div style={{ display: "flex", minHeight: "100vh" }}>
        <Sidebar active={currentPage} onNav={navigate} user={auth.user} onLogout={auth.logout} />
        <main style={{ flex: 1, padding: "0 26px 26px", maxHeight: "100vh", overflowY: "auto" }}>
          {PAGES[currentPage] || PAGES[defaultPage(auth.user.vai_tro)]}
        </main>
      </div>
      {toasts.map(t => <Toast key={t.id} message={t.message} type={t.type} onClose={() => removeToast(t.id)} />)}
    </>
  );
}
