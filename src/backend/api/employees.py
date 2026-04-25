"""
Employees API — CRUD endpoints cho quản lý nhân viên.

Endpoints:
- POST   /api/employees              — Tạo nhân viên mới
- GET    /api/employees              — Danh sách nhân viên (có filter)
- GET    /api/employees/{id}         — Chi tiết nhân viên + checklist + documents
- PATCH  /api/employees/{id}         — Cập nhật thông tin
- DELETE /api/employees/{id}         — Soft delete (terminated)
"""

import logging
from datetime import datetime, date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, Field

from src.backend.database import get_supabase
from src.backend.api.deps import get_current_active_user
from src.backend.schemas import UserInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/employees", tags=["Employees"])


# ─── Schemas ───


class EmployeeCreate(BaseModel):
    """Body cho POST /api/employees."""
    full_name: str = Field(..., min_length=2, examples=["Nguyen Van A"])
    email: EmailStr = Field(..., examples=["nguyen.van.a@company.com"])
    role: str = Field(..., examples=["Software Engineer"])
    department: str = Field(..., examples=["Engineering"])
    seniority: str = Field(default="junior", examples=["junior", "mid", "senior"])
    start_date: date = Field(..., examples=["2026-04-15"])
    personal_email: str | None = Field(default=None, examples=["personal@gmail.com"])
    manager_id: str | None = Field(default=None, description="UUID of manager")


class EmployeeUpdate(BaseModel):
    """Body cho PATCH - chi fields can update."""
    full_name: str | None = None
    role: str | None = None
    department: str | None = None
    seniority: str | None = None
    personal_email: str | None = None
    manager_id: str | None = None
    vai_tro: str | None = Field(default=None, description="nhan_vien_moi | quan_ly | hr_admin | it_admin")
    onboarding_status: str | None = Field(default=None, description="pre_boarding | in_progress | completed | terminated")
    health_score: str | None = Field(default=None, description="green | yellow | red")


# ─── Helpers ───


def _generate_employee_code(supabase) -> str:
    """
    Auto-generate employee_code: NV-{year}-{sequence}.
    Query max existing code for current year and increment.
    """
    year = datetime.now().year
    prefix = f"NV-{year}-"

    try:
        result = (
            supabase.table("employees")
            .select("employee_code")
            .like("employee_code", f"{prefix}%")
            .order("employee_code", desc=True)
            .limit(1)
            .execute()
        )

        if result.data and result.data[0].get("employee_code"):
            last_code = result.data[0]["employee_code"]
            # Extract sequence number: "NV-2026-005" -> 5
            seq = int(last_code.split("-")[-1])
            next_seq = seq + 1
        else:
            next_seq = 1
    except Exception:
        next_seq = 1

    return f"{prefix}{next_seq:03d}"


def _ok(data):
    """Standard success response."""
    return {"success": True, "data": data}


def _err(msg: str, status_code: int = 400):
    """Standard error response — returned as dict, caller sets status."""
    return {"success": False, "error": msg}


# ─── Endpoints ───


@router.post(
    "",
    summary="Tao nhan vien moi",
    description="Tao nhan vien moi voi auto-generate employee_code (NV-YYYY-NNN).",
    status_code=201,
)
async def create_employee(
    body: EmployeeCreate,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """POST /api/employees — tao nhan vien moi."""
    try:
        supabase = get_supabase()
        employee_code = _generate_employee_code(supabase)

        insert_data = {
            "employee_code": employee_code,
            "full_name": body.full_name,
            "email": body.email.strip().lower(),
            "role": body.role,
            "department": body.department,
            "seniority": body.seniority,
            "start_date": body.start_date.isoformat(),
            "vai_tro": "nhan_vien_moi",
            "onboarding_status": "pre_boarding",
            "health_score": "green",
        }

        # Optional fields
        if body.personal_email:
            insert_data["personal_email"] = body.personal_email
        if body.manager_id:
            insert_data["manager_id"] = body.manager_id

        result = supabase.table("employees").insert(insert_data).execute()

        if not result.data:
            return _err("Insert failed — no data returned")

        emp = result.data[0]
        return _ok({"id": emp["id"], "employee_code": emp["employee_code"]})

    except Exception as e:
        logger.error(f"Create employee error: {e}")
        return _err(str(e))


@router.get(
    "",
    summary="Danh sach nhan vien",
    description="Lay danh sach nhan vien co filter theo department, onboarding_status, health_score. "
                "Join voi onboarding_plans de lay completion_percentage.",
)
async def list_employees(
    department: str | None = Query(default=None, description="Filter theo department"),
    onboarding_status: str | None = Query(default=None, description="Filter: pre_boarding | in_progress | completed | terminated"),
    health_score: str | None = Query(default=None, description="Filter: green | yellow | red"),
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/employees — danh sach co filter."""
    try:
        supabase = get_supabase()

        # Base query — select employee fields
        query = supabase.table("employees").select(
            "id, employee_code, full_name, email, role, department, "
            "seniority, start_date, vai_tro, onboarding_status, health_score, "
            "created_at"
        )

        # Apply filters
        if department:
            query = query.eq("department", department)
        if onboarding_status:
            query = query.eq("onboarding_status", onboarding_status)
        if health_score:
            query = query.eq("health_score", health_score)

        # Exclude terminated by default (unless explicitly filtered)
        if not onboarding_status:
            query = query.neq("onboarding_status", "terminated")

        result = query.order("created_at", desc=True).execute()

        # Join completion_percentage from onboarding_plans
        employees = result.data or []
        if employees:
            emp_ids = [e["id"] for e in employees]
            plans_result = (
                supabase.table("onboarding_plans")
                .select("employee_id, completion_percentage")
                .in_("employee_id", emp_ids)
                .execute()
            )
            plan_map = {
                p["employee_id"]: p["completion_percentage"]
                for p in (plans_result.data or [])
            }

            for emp in employees:
                emp["completion_percentage"] = plan_map.get(emp["id"], 0)

        return _ok(employees)

    except Exception as e:
        logger.error(f"List employees error: {e}")
        return _err(str(e))


@router.get(
    "/{employee_id}",
    summary="Chi tiet nhan vien",
    description="Lay thong tin nhan vien + checklist_items + preboarding_documents.",
)
async def get_employee(
    employee_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/employees/{id} — chi tiet + checklist + documents."""
    try:
        supabase = get_supabase()

        # Employee info
        emp_result = (
            supabase.table("employees")
            .select("*")
            .eq("id", employee_id)
            .limit(1)
            .execute()
        )

        if not emp_result.data:
            return _err(f"Employee {employee_id} not found")

        employee = emp_result.data[0]

        # Onboarding plan
        plan_result = (
            supabase.table("onboarding_plans")
            .select("id, status, completion_percentage, total_items, completed_items")
            .eq("employee_id", employee_id)
            .limit(1)
            .execute()
        )
        employee["onboarding_plan"] = plan_result.data[0] if plan_result.data else None

        # Checklist items
        checklist_result = (
            supabase.table("checklist_items")
            .select("id, title, description, category, week, deadline_date, "
                    "owner, is_mandatory, status, completed_at, sort_order")
            .eq("employee_id", employee_id)
            .order("sort_order")
            .execute()
        )
        employee["checklist"] = checklist_result.data or []

        # Preboarding documents
        docs_result = (
            supabase.table("preboarding_documents")
            .select("id, document_type, filename, status, uploaded_at")
            .eq("employee_id", employee_id)
            .execute()
        )
        employee["documents"] = docs_result.data or []

        return _ok(employee)

    except Exception as e:
        logger.error(f"Get employee error: {e}")
        return _err(str(e))


@router.patch(
    "/{employee_id}",
    summary="Cap nhat nhan vien",
    description="Cap nhat thong tin nhan vien. Chi gui fields can update.",
)
async def update_employee(
    employee_id: str,
    body: EmployeeUpdate,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """PATCH /api/employees/{id} — partial update."""
    try:
        # Only include non-None fields
        update_data = body.model_dump(exclude_none=True)

        if not update_data:
            return _err("No fields to update")

        update_data["updated_at"] = datetime.now().isoformat()

        supabase = get_supabase()
        result = (
            supabase.table("employees")
            .update(update_data)
            .eq("id", employee_id)
            .execute()
        )

        if not result.data:
            return _err(f"Employee {employee_id} not found")

        return _ok({"id": result.data[0]["id"]})

    except Exception as e:
        logger.error(f"Update employee error: {e}")
        return _err(str(e))


@router.delete(
    "/{employee_id}",
    summary="Xoa nhan vien (soft delete)",
    description="Soft delete: chuyen onboarding_status thanh 'terminated'.",
)
async def delete_employee(
    employee_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """DELETE /api/employees/{id} — soft delete."""
    try:
        supabase = get_supabase()
        result = (
            supabase.table("employees")
            .update({
                "onboarding_status": "terminated",
                "updated_at": datetime.now().isoformat(),
            })
            .eq("id", employee_id)
            .execute()
        )

        if not result.data:
            return _err(f"Employee {employee_id} not found")

        return _ok({"id": result.data[0]["id"]})

    except Exception as e:
        logger.error(f"Delete employee error: {e}")
        return _err(str(e))
