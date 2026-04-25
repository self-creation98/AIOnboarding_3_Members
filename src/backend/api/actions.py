"""
Actions API — HR action buttons từ dashboard / AI Copilot.

Mỗi action = 1 hành động cụ thể HR nhấn sau khi xem AI tóm tắt.

Endpoints:
- POST /api/actions/assign-buddy      — Nhắc Manager assign buddy
- POST /api/actions/escalate-it       — Escalate IT task
- POST /api/actions/schedule-checkin   — Đặt lịch check-in
- POST /api/actions/send-reminder      — Gửi nhắc nhở NV
- GET  /api/actions/history            — Lịch sử actions
"""

import logging
from datetime import datetime, date, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.backend.database import get_supabase
from src.backend.api.deps import get_current_active_user
from src.backend.schemas import UserInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/actions", tags=["Actions"])


# ─── Schemas ───


class AssignBuddyRequest(BaseModel):
    """Body cho POST /api/actions/assign-buddy."""
    employee_id: str = Field(..., description="UUID of employee", examples=["550e8400-e29b-41d4-a716-446655440000"])


class EscalateItRequest(BaseModel):
    """Body cho POST /api/actions/escalate-it."""
    employee_id: str = Field(..., description="UUID of employee", examples=["550e8400-e29b-41d4-a716-446655440000"])


class ScheduleCheckinRequest(BaseModel):
    """Body cho POST /api/actions/schedule-checkin."""
    employee_id: str = Field(..., description="UUID of employee", examples=["550e8400-e29b-41d4-a716-446655440000"])
    note: str | None = Field(default=None, examples=["NV cần hỗ trợ setup dev environment"])


class SendReminderRequest(BaseModel):
    """Body cho POST /api/actions/send-reminder."""
    employee_id: str = Field(..., description="UUID of employee", examples=["550e8400-e29b-41d4-a716-446655440000"])
    custom_message: str | None = Field(default=None, examples=["Vui lòng hoàn thành Security Training hôm nay"])


# ─── Helpers ───


def _ok(data):
    """Standard success response."""
    return {"success": True, "data": data}


def _err(msg: str, status_code: int = 400):
    """Standard error response — returned as dict, caller sets status."""
    return {"success": False, "error": msg}


# ─── Endpoints ───


@router.post(
    "/assign-buddy",
    summary="Nhac Manager assign buddy",
    description="HR nhac Manager assign buddy cho NV moi. "
                "Update stakeholder task va log reminder.",
)
async def assign_buddy(
    body: AssignBuddyRequest,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """POST /api/actions/assign-buddy — nhac manager assign buddy."""
    try:
        supabase = get_supabase()

        # (a) Lấy employee info
        emp_result = (
            supabase.table("employees")
            .select("id, full_name, manager_id")
            .eq("id", body.employee_id)
            .limit(1)
            .execute()
        )

        if not emp_result.data:
            return _err(f"Employee {body.employee_id} not found")

        employee = emp_result.data[0]

        # (b) Kiểm tra manager
        if not employee.get("manager_id"):
            return _err("NV chưa có manager được assign")

        # (c) Lấy manager info
        mgr_result = (
            supabase.table("employees")
            .select("id, full_name, email")
            .eq("id", employee["manager_id"])
            .limit(1)
            .execute()
        )

        if not mgr_result.data:
            return _err("Manager không tìm thấy trong hệ thống")

        manager = mgr_result.data[0]

        # (d) Update stakeholder_tasks (buddy task → in_progress)
        supabase.table("stakeholder_tasks").update({
            "status": "in_progress",
        }).eq("employee_id", body.employee_id).ilike(
            "title", "%buddy%"
        ).eq("status", "pending").execute()

        # (e) Log reminder
        message = (
            f"HR yêu cầu: Vui lòng assign buddy cho "
            f"{employee['full_name']} ngay hôm nay."
        )
        supabase.table("reminder_logs").insert({
            "employee_id": body.employee_id,
            "escalation_tier": 0,
            "sent_to": manager["email"],
            "sent_to_role": "manager",
            "message": message,
            "channel": "action_button",
            "sent_at": datetime.now().isoformat(),
        }).execute()

        # TODO: Gửi Slack DM cho manager khi tích hợp Slack
        # await slack_client.send_dm(manager.slack_id, message)

        return _ok({
            "action": "assign_buddy",
            "employee_name": employee["full_name"],
            "sent_to": f"{manager['full_name']} (Manager)",
            "message": "Đã gửi yêu cầu assign buddy cho Manager",
        })

    except Exception as e:
        logger.error(f"Assign buddy action error: {e}")
        return _err(str(e))


@router.post(
    "/escalate-it",
    summary="Escalate IT task",
    description="HR escalate IT tasks dang pending cho NV. "
                "Update tasks va gui thong bao cho IT.",
)
async def escalate_it(
    body: EscalateItRequest,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """POST /api/actions/escalate-it — escalate IT tasks."""
    try:
        supabase = get_supabase()

        # (a) Lấy employee info
        emp_result = (
            supabase.table("employees")
            .select("id, full_name")
            .eq("id", body.employee_id)
            .limit(1)
            .execute()
        )

        if not emp_result.data:
            return _err(f"Employee {body.employee_id} not found")

        employee = emp_result.data[0]

        # (b) Lấy pending IT tasks
        tasks_result = (
            supabase.table("stakeholder_tasks")
            .select("id, title")
            .eq("employee_id", body.employee_id)
            .eq("assigned_to_team", "it")
            .eq("status", "pending")
            .execute()
        )

        tasks = tasks_result.data or []

        if not tasks:
            return _err("Không có task IT cần escalate")

        # (c) Update tasks → in_progress
        task_ids = [t["id"] for t in tasks]
        for tid in task_ids:
            supabase.table("stakeholder_tasks").update({
                "status": "in_progress",
            }).eq("id", tid).execute()

        # (d) Log reminder
        message = (
            f"🚨 URGENT: Cần provision accounts cho "
            f"{employee['full_name']} gấp. Đã quá hạn. HR đã escalate."
        )
        supabase.table("reminder_logs").insert({
            "employee_id": body.employee_id,
            "escalation_tier": 0,
            "sent_to": "it_admin",
            "sent_to_role": "it",
            "message": message,
            "channel": "action_button",
            "sent_at": datetime.now().isoformat(),
        }).execute()

        # TODO: Gửi Slack cho #it-support khi tích hợp
        # await slack_client.send_channel("#it-support", message)

        return _ok({
            "action": "escalate_it",
            "employee_name": employee["full_name"],
            "tasks_escalated": len(tasks),
            "message": f"Đã escalate {len(tasks)} tasks cho IT",
        })

    except Exception as e:
        logger.error(f"Escalate IT action error: {e}")
        return _err(str(e))


@router.post(
    "/schedule-checkin",
    summary="Dat lich check-in",
    description="HR dat lich check-in voi NV. "
                "Tao reminder log va optional checklist item.",
)
async def schedule_checkin(
    body: ScheduleCheckinRequest,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """POST /api/actions/schedule-checkin — dat lich check-in."""
    try:
        supabase = get_supabase()

        # (a) Lấy employee info
        emp_result = (
            supabase.table("employees")
            .select("id, full_name, email")
            .eq("id", body.employee_id)
            .limit(1)
            .execute()
        )

        if not emp_result.data:
            return _err(f"Employee {body.employee_id} not found")

        employee = emp_result.data[0]

        # (b) Log reminder
        note_part = f" Ghi chú: {body.note}" if body.note else ""
        message = (
            f"📅 Check-in đã đặt: Gặp {employee['full_name']} "
            f"để hỗ trợ onboarding.{note_part}"
        )
        supabase.table("reminder_logs").insert({
            "employee_id": body.employee_id,
            "escalation_tier": 0,
            "sent_to": "hr_admin",
            "sent_to_role": "hr",
            "message": message,
            "channel": "action_button",
            "sent_at": datetime.now().isoformat(),
        }).execute()

        # (c) Tạo checklist_item check-in cho HR (nếu có plan)
        plan_result = (
            supabase.table("onboarding_plans")
            .select("id")
            .eq("employee_id", body.employee_id)
            .limit(1)
            .execute()
        )

        if plan_result.data:
            supabase.table("checklist_items").insert({
                "plan_id": plan_result.data[0]["id"],
                "employee_id": body.employee_id,
                "title": f"Check-in với {employee['full_name']}",
                "description": body.note or "HR check-in hỗ trợ onboarding",
                "category": "social",
                "owner": "hr",
                "week": 0,
                "deadline_day": 1,
                "deadline_date": (date.today() + timedelta(days=1)).isoformat(),
                "is_mandatory": False,
                "is_compliance": False,
                "status": "chua_bat_dau",
                "sort_order": 99,
            }).execute()

        # TODO: Tạo Google Calendar event khi tích hợp

        return _ok({
            "action": "schedule_checkin",
            "employee_name": employee["full_name"],
            "message": "Đã đặt lịch check-in với NV",
        })

    except Exception as e:
        logger.error(f"Schedule check-in action error: {e}")
        return _err(str(e))


@router.post(
    "/send-reminder",
    summary="Gui nhac nho NV",
    description="HR gui nhac nho cho NV co tasks qua han.",
)
async def send_reminder(
    body: SendReminderRequest,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """POST /api/actions/send-reminder — gui nhac nho NV."""
    try:
        supabase = get_supabase()

        # (a) Lấy employee info
        emp_result = (
            supabase.table("employees")
            .select("id, full_name, email")
            .eq("id", body.employee_id)
            .limit(1)
            .execute()
        )

        if not emp_result.data:
            return _err(f"Employee {body.employee_id} not found")

        employee = emp_result.data[0]

        # (b) Lấy overdue checklist items
        today = date.today()
        overdue_result = (
            supabase.table("checklist_items")
            .select("id, title, deadline_date")
            .eq("employee_id", body.employee_id)
            .in_("status", ["chua_bat_dau", "dang_lam"])
            .lt("deadline_date", today.isoformat())
            .order("deadline_date")
            .execute()
        )

        overdue_items = overdue_result.data or []

        if not overdue_items:
            return _err("NV không có task quá hạn")

        # (c) Build message
        if body.custom_message:
            message = body.custom_message
        else:
            first_item = overdue_items[0]
            try:
                item_deadline = date.fromisoformat(str(first_item["deadline_date"]))
                overdue_days = (today - item_deadline).days
            except (ValueError, TypeError):
                overdue_days = 0

            message = (
                f"Chào {employee['full_name']}, bạn còn {len(overdue_items)} "
                f"việc cần hoàn thành. Ưu tiên: {first_item['title']} "
                f"(quá hạn {overdue_days} ngày)."
            )

        # (d) Log reminder
        supabase.table("reminder_logs").insert({
            "employee_id": body.employee_id,
            "checklist_item_id": overdue_items[0]["id"],
            "escalation_tier": 1,
            "sent_to": employee["email"],
            "sent_to_role": "employee",
            "message": message,
            "channel": "action_button",
            "sent_at": datetime.now().isoformat(),
        }).execute()

        # TODO: Gửi Slack DM cho NV khi tích hợp
        # await slack_client.send_dm(employee.slack_id, message)

        return _ok({
            "action": "send_reminder",
            "employee_name": employee["full_name"],
            "overdue_count": len(overdue_items),
            "message": "Đã gửi nhắc nhở cho NV",
        })

    except Exception as e:
        logger.error(f"Send reminder action error: {e}")
        return _err(str(e))


@router.get(
    "/history",
    summary="Lich su actions",
    description="Xem lich su cac action da thuc hien tu dashboard. "
                "Lay tu reminder_logs WHERE channel = 'action_button'.",
)
async def get_action_history(
    employee_id: str | None = Query(default=None, description="Filter theo employee"),
    action_type: str | None = Query(default=None, description="Filter: assign_buddy, escalate_it, schedule_checkin, send_reminder"),
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/actions/history — lich su actions."""
    try:
        supabase = get_supabase()

        query = supabase.table("reminder_logs").select(
            "id, employee_id, escalation_tier, sent_to, "
            "sent_to_role, message, channel, sent_at"
        ).eq("channel", "action_button")

        if employee_id:
            query = query.eq("employee_id", employee_id)

        # Filter by action_type via message pattern
        if action_type == "assign_buddy":
            query = query.ilike("message", "%assign buddy%")
        elif action_type == "escalate_it":
            query = query.ilike("message", "%provision accounts%")
        elif action_type == "schedule_checkin":
            query = query.ilike("message", "%Check-in đã đặt%")
        elif action_type == "send_reminder":
            query = query.eq("sent_to_role", "employee")

        result = query.order("sent_at", desc=True).limit(50).execute()

        logs = result.data or []

        # Join employee full_name
        if logs:
            emp_ids = list({l["employee_id"] for l in logs if l.get("employee_id")})
            if emp_ids:
                emp_result = (
                    supabase.table("employees")
                    .select("id, full_name")
                    .in_("id", emp_ids)
                    .execute()
                )
                emp_map = {e["id"]: e["full_name"] for e in (emp_result.data or [])}
            else:
                emp_map = {}

            for log in logs:
                log["employee_name"] = emp_map.get(log.get("employee_id"), "")

        return _ok(logs)

    except Exception as e:
        logger.error(f"Action history error: {e}")
        return _err(str(e))
