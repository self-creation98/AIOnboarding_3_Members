"""
Reminders API — Endpoints cho hệ thống nhắc nhở 3 tầng.

Endpoints:
- POST /api/reminders/run     — Trigger chạy reminder thủ công
- GET  /api/reminders/logs    — Xem lịch sử reminders
- GET  /api/reminders/stats   — Thống kê reminders theo tier
"""

import logging
from datetime import datetime, date, timedelta

from fastapi import APIRouter, Depends, Query

from src.backend.database import get_supabase
from src.backend.api.deps import get_current_active_user
from src.backend.schemas import UserInfo
from src.backend.services.reminder import run_daily_reminders

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reminders", tags=["Reminders"])


# ─── Helpers ───


def _ok(data):
    """Standard success response."""
    return {"success": True, "data": data}


def _err(msg: str, status_code: int = 400):
    """Standard error response — returned as dict, caller sets status."""
    return {"success": False, "error": msg}


# ─── Endpoints ───


@router.post(
    "/run",
    summary="Trigger chay reminder",
    description="Chay reminder thu cong. Kiem tra tat ca checklist items "
                "qua han va gui nhac nho theo 3 tang escalation.",
)
async def trigger_reminders(
    current_user: UserInfo = Depends(get_current_active_user),
):
    """POST /api/reminders/run — trigger daily reminders."""
    try:
        supabase = get_supabase()
        result = await run_daily_reminders(supabase)
        return _ok(result)

    except Exception as e:
        logger.error(f"Run reminders error: {e}")
        return _err(str(e))


@router.get(
    "/logs",
    summary="Lich su reminders",
    description="Xem lich su reminders da gui. Filter theo employee_id, "
                "escalation_tier, date range. Limit 100.",
)
async def get_reminder_logs(
    employee_id: str | None = Query(default=None, description="Filter theo employee"),
    escalation_tier: int | None = Query(default=None, description="Filter: 1, 2, hoặc 3"),
    date_from: str | None = Query(default=None, description="Filter từ ngày (YYYY-MM-DD)"),
    date_to: str | None = Query(default=None, description="Filter đến ngày (YYYY-MM-DD)"),
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/reminders/logs — lich su reminders."""
    try:
        supabase = get_supabase()

        query = supabase.table("reminder_logs").select(
            "id, employee_id, checklist_item_id, escalation_tier, "
            "sent_to, sent_to_role, message, channel, sent_at"
        )

        # Apply filters
        if employee_id:
            query = query.eq("employee_id", employee_id)
        if escalation_tier:
            query = query.eq("escalation_tier", escalation_tier)
        if date_from:
            query = query.gte("sent_at", f"{date_from}T00:00:00")
        if date_to:
            query = query.lte("sent_at", f"{date_to}T23:59:59")

        result = query.order("sent_at", desc=True).limit(100).execute()

        logs = result.data or []

        # Join employee full_name và checklist_item title
        if logs:
            emp_ids = list({l["employee_id"] for l in logs if l.get("employee_id")})
            item_ids = list({l["checklist_item_id"] for l in logs if l.get("checklist_item_id")})

            emp_map = {}
            if emp_ids:
                emp_result = (
                    supabase.table("employees")
                    .select("id, full_name")
                    .in_("id", emp_ids)
                    .execute()
                )
                emp_map = {e["id"]: e["full_name"] for e in (emp_result.data or [])}

            item_map = {}
            if item_ids:
                items_result = (
                    supabase.table("checklist_items")
                    .select("id, title")
                    .in_("id", item_ids)
                    .execute()
                )
                item_map = {i["id"]: i["title"] for i in (items_result.data or [])}

            for log in logs:
                log["employee_name"] = emp_map.get(log.get("employee_id"), "")
                log["checklist_item_title"] = item_map.get(log.get("checklist_item_id"), "")

        return _ok(logs)

    except Exception as e:
        logger.error(f"Get reminder logs error: {e}")
        return _err(str(e))


@router.get(
    "/stats",
    summary="Thong ke reminders",
    description="Thong ke so luong reminders theo tier: hom nay, tuan nay, tong cong.",
)
async def get_reminder_stats(
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/reminders/stats — thong ke reminders theo tier."""
    try:
        supabase = get_supabase()

        today = date.today()
        week_start = today - timedelta(days=today.weekday())  # Monday

        # Lấy tất cả reminder_logs
        result = (
            supabase.table("reminder_logs")
            .select("escalation_tier, sent_at")
            .execute()
        )

        logs = result.data or []

        # Đếm theo tier + time range
        today_stats = {"tier1": 0, "tier2": 0, "tier3": 0}
        week_stats = {"tier1": 0, "tier2": 0, "tier3": 0}
        total_stats = {"tier1": 0, "tier2": 0, "tier3": 0}

        for log in logs:
            tier_key = f"tier{log['escalation_tier']}"
            if tier_key not in total_stats:
                continue

            total_stats[tier_key] += 1

            # Parse sent_at date
            try:
                sent_date = date.fromisoformat(str(log["sent_at"])[:10])
            except (ValueError, TypeError):
                continue

            if sent_date == today:
                today_stats[tier_key] += 1

            if sent_date >= week_start:
                week_stats[tier_key] += 1

        return _ok({
            "today": today_stats,
            "this_week": week_stats,
            "total": total_stats,
        })

    except Exception as e:
        logger.error(f"Reminder stats error: {e}")
        return _err(str(e))
