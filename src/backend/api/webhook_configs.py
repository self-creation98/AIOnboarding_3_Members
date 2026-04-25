"""
Webhook Configs API — HR quản lý URL đăng ký nhận outgoing webhooks.

Endpoints:
- POST   /api/webhook-configs           — Đăng ký URL mới
- GET    /api/webhook-configs           — Danh sách configs
- GET    /api/webhook-configs/{id}      — Chi tiết 1 config
- PATCH  /api/webhook-configs/{id}      — Cập nhật config
- DELETE /api/webhook-configs/{id}      — Xóa config
- POST   /api/webhook-configs/{id}/test — Gửi test payload
"""

import logging
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.backend.database import get_supabase
from src.backend.api.deps import get_current_active_user
from src.backend.schemas import UserInfo
from src.backend.services.event_dispatcher import (
    VALID_EVENT_TYPES,
    send_test_webhook,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhook-configs", tags=["Webhook Configs"])


# ─── Schemas ───


class WebhookConfigCreate(BaseModel):
    """Body cho POST /api/webhook-configs."""
    name: str = Field(
        ...,
        description="Tên mô tả (VD: 'HRIS Production', 'Slack Notifications')",
        examples=["HRIS Production"],
    )
    url: str = Field(
        ...,
        description="URL nhận webhook (HTTPS recommended)",
        examples=["https://hris.company.com/webhooks/onboarding"],
    )
    events: list[str] = Field(
        ...,
        description="Danh sách event types muốn nhận",
        examples=[["employee.onboarding.started", "employee.onboarding.completed"]],
    )
    secret: str | None = Field(
        default=None,
        description="Secret để sign payload (auto-generate nếu không truyền)",
    )


class WebhookConfigUpdate(BaseModel):
    """Body cho PATCH /api/webhook-configs/{id}."""
    name: str | None = Field(default=None)
    url: str | None = Field(default=None)
    events: list[str] | None = Field(default=None)
    active: bool | None = Field(default=None)


# ─── Helpers ───


def _ok(data):
    """Standard success response."""
    return {"success": True, "data": data}


def _err(msg: str, status_code: int = 400):
    """Standard error response."""
    return {"success": False, "error": msg}


def _validate_events(events: list[str]) -> str | None:
    """Validate event types. Returns error message nếu không hợp lệ."""
    invalid = [e for e in events if e not in VALID_EVENT_TYPES]
    if invalid:
        return (
            f"Invalid event types: {invalid}. "
            f"Valid types: {VALID_EVENT_TYPES}"
        )
    return None


# ─── Endpoints ───


@router.post(
    "",
    summary="Dang ky webhook URL moi",
    description="Dang ky URL moi de nhan outgoing webhooks. "
                "Secret duoc auto-generate neu khong truyen.",
    status_code=201,
)
async def create_webhook_config(
    body: WebhookConfigCreate,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """POST /api/webhook-configs — dang ky URL moi."""
    try:
        # Validate events
        err = _validate_events(body.events)
        if err:
            return _err(err)

        supabase = get_supabase()

        # Auto-generate secret nếu không truyền
        secret = body.secret or secrets.token_urlsafe(32)

        insert_data = {
            "name": body.name,
            "url": body.url,
            "events": body.events,
            "secret": secret,
            "active": True,
            "created_by": current_user.user_id,
            "created_at": datetime.now().isoformat(),
        }

        result = supabase.table("webhook_configs").insert(insert_data).execute()

        if not result.data:
            return _err("Insert webhook config failed")

        config = result.data[0]

        return _ok({
            "id": config["id"],
            "name": config["name"],
            "url": config["url"],
            "events": config["events"],
            "secret": secret,  # Chỉ trả secret lần đầu tạo
            "active": config["active"],
            "message": "Webhook config đã đăng ký. Lưu secret — sẽ không hiển thị lại.",
        })

    except Exception as e:
        logger.error(f"Create webhook config error: {e}")
        return _err(str(e))


@router.get(
    "",
    summary="Danh sach webhook configs",
    description="Lay danh sach tat ca webhook configs. Secret duoc an di.",
)
async def list_webhook_configs(
    active_only: bool = Query(default=False, description="Chi lay configs dang active"),
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/webhook-configs — danh sach configs."""
    try:
        supabase = get_supabase()

        query = supabase.table("webhook_configs").select(
            "id, name, url, events, active, created_at, created_by"
        )

        if active_only:
            query = query.eq("active", True)

        result = query.order("created_at", desc=True).execute()

        return _ok(result.data or [])

    except Exception as e:
        logger.error(f"List webhook configs error: {e}")
        return _err(str(e))


@router.get(
    "/{config_id}",
    summary="Chi tiet webhook config",
    description="Lay chi tiet 1 webhook config. Secret duoc an di.",
)
async def get_webhook_config(
    config_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/webhook-configs/{config_id} — chi tiet config."""
    try:
        supabase = get_supabase()

        result = (
            supabase.table("webhook_configs")
            .select("id, name, url, events, active, created_at, created_by")
            .eq("id", config_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            return _err(f"Config {config_id} not found")

        # Lấy thêm delivery stats từ webhook_logs
        logs_result = (
            supabase.table("webhook_logs")
            .select("success, created_at")
            .eq("direction", "out")
            .eq("endpoint_url", result.data[0]["url"])
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )

        logs = logs_result.data or []
        total_deliveries = len(logs)
        successful = sum(1 for l in logs if l.get("success"))

        config = result.data[0]
        config["delivery_stats"] = {
            "recent_deliveries": total_deliveries,
            "successful": successful,
            "failed": total_deliveries - successful,
            "success_rate": round(successful / total_deliveries, 2) if total_deliveries > 0 else None,
        }

        return _ok(config)

    except Exception as e:
        logger.error(f"Get webhook config error: {e}")
        return _err(str(e))


@router.patch(
    "/{config_id}",
    summary="Cap nhat webhook config",
    description="Cap nhat thong tin webhook config (URL, events, active status).",
)
async def update_webhook_config(
    config_id: str,
    body: WebhookConfigUpdate,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """PATCH /api/webhook-configs/{config_id} — cap nhat config."""
    try:
        # Validate events nếu có
        if body.events is not None:
            err = _validate_events(body.events)
            if err:
                return _err(err)

        supabase = get_supabase()

        update_data = {"updated_at": datetime.now().isoformat()}

        if body.name is not None:
            update_data["name"] = body.name
        if body.url is not None:
            update_data["url"] = body.url
        if body.events is not None:
            update_data["events"] = body.events
        if body.active is not None:
            update_data["active"] = body.active

        result = (
            supabase.table("webhook_configs")
            .update(update_data)
            .eq("id", config_id)
            .execute()
        )

        if not result.data:
            return _err(f"Config {config_id} not found")

        return _ok({
            "id": config_id,
            "updated_fields": [k for k in update_data if k != "updated_at"],
            "message": "Webhook config đã cập nhật",
        })

    except Exception as e:
        logger.error(f"Update webhook config error: {e}")
        return _err(str(e))


@router.delete(
    "/{config_id}",
    summary="Xoa webhook config",
    description="Xoa webhook config. Webhook logs van giu lai.",
)
async def delete_webhook_config(
    config_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """DELETE /api/webhook-configs/{config_id} — xoa config."""
    try:
        supabase = get_supabase()

        result = (
            supabase.table("webhook_configs")
            .delete()
            .eq("id", config_id)
            .execute()
        )

        if not result.data:
            return _err(f"Config {config_id} not found")

        return _ok({
            "id": config_id,
            "message": "Webhook config đã xóa",
        })

    except Exception as e:
        logger.error(f"Delete webhook config error: {e}")
        return _err(str(e))


@router.post(
    "/{config_id}/test",
    summary="Test webhook URL",
    description="Gui test payload toi webhook URL de verify ket noi.",
)
async def test_webhook_config(
    config_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """POST /api/webhook-configs/{config_id}/test — gui test payload."""
    try:
        result = await send_test_webhook(config_id)

        if result.get("success"):
            return _ok({
                "config_id": config_id,
                "test_result": "success",
                "response_status": result.get("response_status"),
                "message": "Test webhook gửi thành công",
            })
        else:
            return _ok({
                "config_id": config_id,
                "test_result": "failed",
                "response_status": result.get("response_status"),
                "error": result.get("error_message"),
                "message": "Test webhook thất bại",
            })

    except Exception as e:
        logger.error(f"Test webhook config error: {e}")
        return _err(str(e))
