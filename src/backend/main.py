"""
FastAPI Application — AI Onboarding Backend.

Run with:
    uvicorn src.backend.main:app --reload --port 8000

Swagger UI:
    http://localhost:8000/docs
"""

import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from src.config import LOG_LEVEL
from src.backend.api.auth import router as auth_router
from src.backend.api.employees import router as employees_router
from src.backend.api.documents import router as documents_router
from src.backend.api.chat import router as chat_router
from src.backend.api.checklist import router as checklist_router
from src.backend.api.stakeholder import router as stakeholder_router
from src.backend.api.preboarding import router as preboarding_router
from src.backend.api.webhooks import router as webhooks_router
from src.backend.api.reminders import router as reminders_router
from src.backend.api.actions import router as actions_router
from src.backend.api.analytics import router as analytics_router
from src.backend.api.webhook_configs import router as webhook_configs_router
from src.backend.api.task_confirm import router as task_confirm_router
from src.backend.api.deps import get_current_active_user
from src.backend.schemas import UserInfo, HelloResponse



logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🚀 AI Onboarding Backend starting...")
    yield
    logger.info("👋 AI Onboarding Backend shutting down...")


app = FastAPI(
    title="AI Onboarding API",
    description="""
## AI Onboarding Module — Backend API

Hệ thống quản lý onboarding nhân viên mới với AI.

### Xác thực (Authentication)
1. Gọi `POST /api/auth/login` với email công ty (@company.com) và password
2. Copy `access_token` từ response
3. Nhấn nút 🔒 **Authorize** ở trên → dán token → nhấn **Authorize**
4. Tất cả API có 🔒 sẽ tự gửi token

### Roles (vai_tro)
- `nhan_vien_moi` — Nhân viên mới
- `quan_ly` — Quản lý
- `hr_admin` — HR Admin
- `it_admin` — IT Admin
""",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — cho phép frontend connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ───
app.include_router(auth_router)
app.include_router(employees_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(checklist_router)
app.include_router(stakeholder_router)
app.include_router(preboarding_router)
app.include_router(webhooks_router)
app.include_router(reminders_router)
app.include_router(actions_router)
app.include_router(analytics_router)
app.include_router(webhook_configs_router)
app.include_router(task_confirm_router)


# ─── Protected Hello World ───
@app.get(
    "/api/hello",
    response_model=HelloResponse,
    tags=["Test"],
    summary="Hello World (Protected)",
    description="Endpoint test có bảo mật. Yêu cầu Bearer token hợp lệ.",
)
async def hello_world(
    current_user: UserInfo = Depends(get_current_active_user),
):
    """
    Endpoint để test auth đã hoạt động.
    Trả về greeting kèm thông tin user.
    """
    return HelloResponse(
        message=f"Xin chào {current_user.full_name}! Bạn đang đăng nhập với vai trò: {current_user.vai_tro}",
        user=current_user,
        timestamp=datetime.now(),
    )


# ─── Health Check (Public) ───
@app.get(
    "/api/health",
    tags=["System"],
    summary="Health Check",
)
async def health_check():
    """Public endpoint — kiểm tra server đang chạy."""
    return {
        "status": "healthy",
        "service": "AI Onboarding Backend",
        "version": "0.1.0",
    }
