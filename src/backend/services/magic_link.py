"""
Magic Link Service — Token generation & verification cho stakeholder task confirmation.

IT/Manager nhận email chứa magic link → click → confirm tasks → không cần login.

Token format: JWT signed với HMAC-SHA256
Payload: {
    "sub": task_id hoặc plan_id,
    "team": "it" | "admin" | "manager",
    "emp_id": employee_id,
    "type": "task_confirm" | "plan_confirm",
    "exp": expiry timestamp,
    "iat": issued at
}

Security:
- Token expire sau MAGIC_LINK_EXPIRY_HOURS (default: 7 ngày)
- Token chỉ valid cho đúng task/plan được chỉ định
- Sau khi dùng, task status = completed → token vẫn valid nhưng action idempotent
"""

import logging
from datetime import datetime, timedelta

from jose import jwt, JWTError

from src.config import MAGIC_LINK_SECRET, MAGIC_LINK_EXPIRY_HOURS, BACKEND_BASE_URL

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"


def generate_task_token(
    task_id: str,
    team: str,
    employee_id: str,
    expiry_hours: int | None = None,
) -> str:
    """
    Tạo magic link token cho 1 stakeholder task.

    Args:
        task_id: ID của stakeholder_task
        team: "it" | "admin" | "manager"
        employee_id: ID nhân viên mới (để context)
        expiry_hours: Override thời gian hết hạn (giờ)

    Returns:
        JWT token string
    """
    hours = expiry_hours or MAGIC_LINK_EXPIRY_HOURS

    payload = {
        "sub": task_id,
        "team": team,
        "emp_id": employee_id,
        "type": "task_confirm",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=hours),
    }

    return jwt.encode(payload, MAGIC_LINK_SECRET, algorithm=ALGORITHM)


def generate_team_token(
    plan_id: str,
    team: str,
    employee_id: str,
    expiry_hours: int | None = None,
) -> str:
    """
    Tạo magic link token cho TẤT CẢ tasks của 1 team trong 1 plan.

    Dùng khi gửi email cho IT team — họ click 1 link, thấy ALL IT tasks
    cho NV đó, tick từng cái rồi submit.

    Args:
        plan_id: ID của onboarding_plan
        team: "it" | "admin" | "manager"
        employee_id: ID nhân viên mới
        expiry_hours: Override thời gian hết hạn (giờ)

    Returns:
        JWT token string
    """
    hours = expiry_hours or MAGIC_LINK_EXPIRY_HOURS

    payload = {
        "sub": plan_id,
        "team": team,
        "emp_id": employee_id,
        "type": "team_confirm",
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=hours),
    }

    return jwt.encode(payload, MAGIC_LINK_SECRET, algorithm=ALGORITHM)


def verify_token(token: str) -> dict | None:
    """
    Verify và decode magic link token.

    Returns:
        Decoded payload dict nếu valid, None nếu invalid/expired
    """
    try:
        payload = jwt.decode(token, MAGIC_LINK_SECRET, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"Magic link token invalid: {e}")
        return None


def build_confirm_url(token: str) -> str:
    """Build full URL cho magic link confirmation page."""
    return f"{BACKEND_BASE_URL}/api/tasks/confirm/{token}"


def build_confirm_page_url(token: str) -> str:
    """
    Build URL cho frontend confirmation page.

    Frontend sẽ hiển thị task list đẹp + nút confirm.
    Nếu không có frontend → fallback về backend API trực tiếp.
    """
    from src.config import FRONTEND_BASE_URL
    return f"{FRONTEND_BASE_URL}/confirm-tasks?token={token}"
