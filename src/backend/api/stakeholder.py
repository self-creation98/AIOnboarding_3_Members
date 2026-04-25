"""
Stakeholder Tasks API — Endpoints cho quản lý tasks giao cho các bộ phận.

Endpoints:
- GET   /api/stakeholder-tasks              — Danh sách tasks (có filter)
- GET   /api/stakeholder-tasks/summary      — Thống kê theo team + status
- GET   /api/stakeholder-tasks/{task_id}    — Chi tiết 1 task
- PATCH /api/stakeholder-tasks/{task_id}/complete — Hoàn thành task
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.backend.database import get_supabase
from src.backend.api.deps import get_current_active_user
from src.backend.schemas import UserInfo
from src.backend.services.event_dispatcher import fire_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stakeholder-tasks", tags=["Stakeholder Tasks"])


# ─── Schemas ───


class CompleteTaskRequest(BaseModel):
    """Body cho PATCH /api/stakeholder-tasks/{task_id}/complete."""
    completed_by: str = Field(..., description="Tên người hoàn thành", examples=["Nguyen Van A"])


# ─── Helpers ───


def _ok(data):
    """Standard success response."""
    return {"success": True, "data": data}


def _err(msg: str, status_code: int = 400):
    """Standard error response — returned as dict, caller sets status."""
    return {"success": False, "error": msg}


# ─── Endpoints ───


@router.get(
    "/summary",
    summary="Thong ke tasks theo team",
    description="Dem so luong tasks theo assigned_to_team va status.",
)
async def tasks_summary(
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/stakeholder-tasks/summary — thong ke theo team + status."""
    try:
        supabase = get_supabase()

        result = (
            supabase.table("stakeholder_tasks")
            .select("assigned_to_team, status")
            .execute()
        )

        tasks = result.data or []

        # Đếm theo team + status
        summary = {}
        for task in tasks:
            team = task["assigned_to_team"]
            status = task["status"]
            if team not in summary:
                summary[team] = {}
            summary[team][status] = summary[team].get(status, 0) + 1

        return _ok(summary)

    except Exception as e:
        logger.error(f"Tasks summary error: {e}")
        return _err(str(e))


@router.get(
    "",
    summary="Danh sach stakeholder tasks",
    description="Lay danh sach tasks co filter theo assigned_to_team, status, employee_id. "
                "Join voi employees de lay full_name.",
)
async def list_tasks(
    assigned_to_team: str | None = Query(default=None, description="Filter: it | admin | finance | manager"),
    status: str | None = Query(default=None, description="Filter: pending | in_progress | completed | cancelled"),
    employee_id: str | None = Query(default=None, description="Filter theo employee được onboard"),
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/stakeholder-tasks — danh sach co filter."""
    try:
        supabase = get_supabase()

        query = supabase.table("stakeholder_tasks").select(
            "id, employee_id, title, description, assigned_to_team, "
            "assigned_to_user_id, status, deadline, details, "
            "created_at, completed_at, completed_by"
        )

        # Apply filters
        if assigned_to_team:
            query = query.eq("assigned_to_team", assigned_to_team)
        if status:
            query = query.eq("status", status)
        if employee_id:
            query = query.eq("employee_id", employee_id)

        result = query.order("deadline").order("created_at").execute()

        tasks = result.data or []

        # Join employee full_name
        if tasks:
            emp_ids = list({t["employee_id"] for t in tasks if t.get("employee_id")})
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

            for task in tasks:
                task["employee_name"] = emp_map.get(task.get("employee_id"), "")

        return _ok(tasks)

    except Exception as e:
        logger.error(f"List tasks error: {e}")
        return _err(str(e))


@router.get(
    "/{task_id}",
    summary="Chi tiet 1 task",
    description="Lay thong tin chi tiet cua 1 stakeholder task.",
)
async def get_task(
    task_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/stakeholder-tasks/{task_id} — chi tiet task."""
    try:
        supabase = get_supabase()

        result = (
            supabase.table("stakeholder_tasks")
            .select("*")
            .eq("id", task_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            return _err(f"Task {task_id} not found")

        task = result.data[0]

        # Join employee full_name
        if task.get("employee_id"):
            emp_result = (
                supabase.table("employees")
                .select("full_name")
                .eq("id", task["employee_id"])
                .limit(1)
                .execute()
            )
            task["employee_name"] = emp_result.data[0]["full_name"] if emp_result.data else ""
        else:
            task["employee_name"] = ""

        return _ok(task)

    except Exception as e:
        logger.error(f"Get task error: {e}")
        return _err(str(e))


@router.patch(
    "/{task_id}/complete",
    summary="Hoan thanh task",
    description="Danh dau stakeholder task la hoan thanh. "
                "Tu dong cap nhat checklist_item lien quan va tinh lai completion_percentage.",
)
async def complete_task(
    task_id: str,
    body: CompleteTaskRequest,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """PATCH /api/stakeholder-tasks/{task_id}/complete — hoan thanh task."""
    try:
        supabase = get_supabase()

        # Update stakeholder_task
        task_result = (
            supabase.table("stakeholder_tasks")
            .update({
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
                "completed_by": body.completed_by,
            })
            .eq("id", task_id)
            .execute()
        )

        if not task_result.data:
            return _err(f"Task {task_id} not found")

        task = task_result.data[0]
        checklist_item_id = task.get("checklist_item_id")
        checklist_item_updated = False
        new_completion_percentage = 0.0

        # Update checklist_item liên quan
        if checklist_item_id:
            supabase.table("checklist_items").update({
                "status": "hoan_thanh",
                "completed_at": datetime.now().isoformat(),
            }).eq("id", checklist_item_id).execute()
            checklist_item_updated = True

            # Tính lại completion cho plan
            plan_id = task.get("plan_id")
            if plan_id:
                # Đếm completed items
                completed_result = (
                    supabase.table("checklist_items")
                    .select("id", count="exact")
                    .eq("plan_id", plan_id)
                    .eq("status", "hoan_thanh")
                    .execute()
                )
                completed_items = completed_result.count if completed_result.count is not None else 0

                # Lấy total_items từ plan
                plan_result = (
                    supabase.table("onboarding_plans")
                    .select("total_items")
                    .eq("id", plan_id)
                    .limit(1)
                    .execute()
                )
                total_items = plan_result.data[0]["total_items"] if plan_result.data else 1
                new_completion_percentage = round((completed_items / total_items) * 100, 1) if total_items > 0 else 0

                # Update plan
                supabase.table("onboarding_plans").update({
                    "completed_items": completed_items,
                    "completion_percentage": new_completion_percentage,
                    "updated_at": datetime.now().isoformat(),
                }).eq("id", plan_id).execute()

                # ─── Bug #5 fix: Check mandatory 100% → auto-complete ───
                mandatory_incomplete = (
                    supabase.table("checklist_items")
                    .select("id", count="exact")
                    .eq("plan_id", plan_id)
                    .eq("is_mandatory", True)
                    .neq("status", "hoan_thanh")
                    .execute()
                )
                mandatory_remaining = mandatory_incomplete.count if mandatory_incomplete.count is not None else 1

                if mandatory_remaining == 0:
                    supabase.table("onboarding_plans").update({
                        "status": "hoan_thanh",
                        "updated_at": datetime.now().isoformat(),
                    }).eq("id", plan_id).execute()

                    employee_id = task.get("employee_id")
                    if employee_id:
                        supabase.table("employees").update({
                            "onboarding_status": "completed",
                            "updated_at": datetime.now().isoformat(),
                        }).eq("id", employee_id).execute()

                    # Fire outgoing webhook: onboarding completed
                    await fire_event("employee.onboarding.completed", {
                        "employee_id": task.get("employee_id"),
                        "plan_id": plan_id,
                        "completion_percentage": new_completion_percentage,
                        "trigger": "stakeholder_task_complete",
                    })

        return _ok({
            "task_id": task_id,
            "status": "completed",
            "checklist_item_updated": checklist_item_updated,
            "new_completion_percentage": new_completion_percentage,
        })

    except Exception as e:
        logger.error(f"Complete task error: {e}")
        return _err(str(e))
