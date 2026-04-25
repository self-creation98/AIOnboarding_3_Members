"""
Webhooks API — Endpoints nhận webhook từ hệ thống bên ngoài.

Webhooks KHÔNG cần auth — hệ thống bên ngoài (HRIS, LMS, IT Ops) gọi vào.

Endpoints:
- POST /api/webhooks/hris/new-employee      — HRIS tạo NV mới → trigger full flow
- POST /api/webhooks/hris/employee-updated   — HRIS cập nhật NV (đổi dept/role/start_date)
- POST /api/webhooks/lms/course-completed    — LMS báo hoàn thành khóa training
- POST /api/webhooks/it/ticket-resolved      — IT báo provision xong
- POST /api/webhooks/documents/submitted     — Doc Portal báo NV upload giấy tờ
"""

import logging
import json
from datetime import datetime, timedelta, date

from fastapi import APIRouter
from pydantic import BaseModel, Field, EmailStr

from src.backend.database import get_supabase
from src.backend.api.checklist import _build_checklist
from src.backend.services.stakeholder_notifier import notify_stakeholders

logger = logging.getLogger(__name__)

# Webhook endpoints — không cần auth, hệ thống bên ngoài gọi
router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


# ─── Schemas ───


class EmployeeData(BaseModel):
    """Data cho new-employee webhook."""
    full_name: str = Field(..., examples=["Nguyễn Văn An"])
    email: str = Field(..., examples=["an.nguyen@company.com"])
    personal_email: str | None = Field(default=None, examples=["an.nguyen@gmail.com"])
    role: str = Field(..., examples=["software_engineer"])
    department: str = Field(..., examples=["engineering"])
    seniority: str = Field(default="junior", examples=["junior"])
    start_date: str = Field(..., examples=["2024-05-15"])
    manager_id: str | None = Field(default=None)
    location: str | None = Field(default="HCM")


class NewEmployeeWebhook(BaseModel):
    """Body cho POST /api/webhooks/hris/new-employee."""
    event: str = Field(..., examples=["employee.created"])
    data: EmployeeData


class CourseData(BaseModel):
    """Data cho course-completed webhook."""
    employee_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    course_id: str = Field(..., examples=["SEC-101"])
    course_name: str = Field(..., examples=["Security Awareness Training"])
    score: int | None = Field(default=None, examples=[85])
    passed: bool = Field(default=True)


class CourseCompletedWebhook(BaseModel):
    """Body cho POST /api/webhooks/lms/course-completed."""
    event: str = Field(..., examples=["course.completed"])
    data: CourseData


class TicketItem(BaseModel):
    """Chi tiết 1 item đã provision."""
    type: str = Field(..., examples=["email"])
    detail: str = Field(..., examples=["an.nguyen@company.com đã tạo"])


class TicketData(BaseModel):
    """Data cho ticket-resolved webhook."""
    employee_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    task_type: str = Field(..., examples=["account_provisioning"])
    items_completed: list[TicketItem] = Field(default=[])
    resolved_by: str = Field(..., examples=["IT-Admin Hoàng"])


class TicketResolvedWebhook(BaseModel):
    """Body cho POST /api/webhooks/it/ticket-resolved."""
    event: str = Field(..., examples=["ticket.resolved"])
    data: TicketData


# ─── Helpers ───


def _ok(data):
    """Standard success response."""
    return {"success": True, "data": data}


def _err(msg: str, status_code: int = 400):
    """Standard error response — returned as dict, caller sets status."""
    return {"success": False, "error": msg}


def _log_webhook(supabase, direction: str, event_type: str,
                 request_body: dict, success: bool, error_message: str | None = None):
    """Ghi log webhook vào webhook_logs."""
    try:
        supabase.table("webhook_logs").insert({
            "direction": direction,
            "event_type": event_type,
            "endpoint_url": f"/api/webhooks/{event_type}",
            "request_body": request_body,
            "response_status": 200,
            "success": success,
            "error_message": error_message,
        }).execute()
    except Exception as e:
        logger.error(f"Failed to log webhook: {e}")


def _generate_employee_code(supabase) -> str:
    """Auto-generate employee_code: NV-{year}-{sequence}."""
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
            seq = int(last_code.split("-")[-1])
            next_seq = seq + 1
        else:
            next_seq = 1
    except Exception:
        next_seq = 1

    return f"{prefix}{next_seq:03d}"


def _recalc_completion(supabase, plan_id: str) -> float:
    """Tính lại completion_percentage cho plan và update DB."""
    completed_result = (
        supabase.table("checklist_items")
        .select("id", count="exact")
        .eq("plan_id", plan_id)
        .eq("status", "hoan_thanh")
        .execute()
    )
    completed_items = completed_result.count if completed_result.count is not None else 0

    plan_result = (
        supabase.table("onboarding_plans")
        .select("total_items")
        .eq("id", plan_id)
        .limit(1)
        .execute()
    )
    total_items = plan_result.data[0]["total_items"] if plan_result.data else 1
    percentage = round((completed_items / total_items) * 100, 1) if total_items > 0 else 0

    supabase.table("onboarding_plans").update({
        "completed_items": completed_items,
        "completion_percentage": percentage,
        "updated_at": datetime.now().isoformat(),
    }).eq("id", plan_id).execute()

    return percentage


# Checklist tasks giờ dùng _build_checklist() từ checklist.py (3-layer)

PREBOARDING_DOCS = [
    {"document_type": "cmnd", "document_label": "CMND/CCCD (mặt trước + mặt sau)"},
    {"document_type": "photo_3x4", "document_label": "Ảnh thẻ 3x4"},
    {"document_type": "so_bhxh", "document_label": "Sổ BHXH (nếu có)"},
    {"document_type": "bang_cap", "document_label": "Bằng đại học / cao đẳng"},
    {"document_type": "so_tai_khoan", "document_label": "Số tài khoản ngân hàng"},
]


# ─── Endpoints ───


@router.post(
    "/hris/new-employee",
    summary="HRIS tao NV moi",
    description="HRIS hoac Mock Panel tao nhan vien moi. "
                "Trigger toan bo flow: tao employee + preboarding docs + checklist.",
    status_code=201,
)
async def webhook_new_employee(body: NewEmployeeWebhook):
    """POST /api/webhooks/hris/new-employee — tao NV + checklist + preboarding."""
    request_body = body.model_dump(mode="json")

    try:
        supabase = get_supabase()
        data = body.data

        # (a) Kiểm tra email trùng
        existing = (
            supabase.table("employees")
            .select("id")
            .eq("email", data.email.strip().lower())
            .limit(1)
            .execute()
        )

        if existing.data:
            _log_webhook(supabase, "in", "employee.created", request_body,
                         success=False, error_message="Email đã tồn tại")
            return _err(f"Email {data.email} đã tồn tại trong hệ thống")

        # (b) Tạo employee — logic copy từ employees.py
        employee_code = _generate_employee_code(supabase)

        insert_data = {
            "employee_code": employee_code,
            "full_name": data.full_name,
            "email": data.email.strip().lower(),
            "role": data.role,
            "department": data.department,
            "seniority": data.seniority,
            "start_date": data.start_date,
            "vai_tro": "nhan_vien_moi",
            "onboarding_status": "pre_boarding",
            "health_score": "green",
        }

        if data.personal_email:
            insert_data["personal_email"] = data.personal_email
        if data.manager_id:
            insert_data["manager_id"] = data.manager_id
        if data.location:
            insert_data["location"] = data.location

        emp_result = supabase.table("employees").insert(insert_data).execute()

        if not emp_result.data:
            _log_webhook(supabase, "in", "employee.created", request_body,
                         success=False, error_message="Insert employee failed")
            return _err("Insert employee failed")

        employee = emp_result.data[0]
        employee_id = employee["id"]

        # (c) Auto-create preboarding_documents
        docs_to_insert = [
            {
                "employee_id": employee_id,
                "document_type": doc["document_type"],
                "document_label": doc["document_label"],
                "status": "missing",
            }
            for doc in PREBOARDING_DOCS
        ]
        supabase.table("preboarding_documents").insert(docs_to_insert).execute()

        # (d) Generate checklist — dùng 3-layer từ checklist.py
        start_date_str = data.start_date
        try:
            start_date_parsed = date.fromisoformat(str(start_date_str))
        except (ValueError, TypeError):
            start_date_parsed = date.today()

        # Build tasks theo 3-layer architecture
        checklist_tasks = _build_checklist(
            role=data.role,
            department=data.department,
            seniority=data.seniority,
        )

        plan_result = (
            supabase.table("onboarding_plans")
            .insert({
                "employee_id": employee_id,
                "status": "da_duyet",  # Auto-approve cho webhook flow
                "generated_by": "ai",
                "approved_at": datetime.now().isoformat(),
                "total_items": len(checklist_tasks),
                "completed_items": 0,
                "completion_percentage": 0,
            })
            .execute()
        )

        plan_id = plan_result.data[0]["id"] if plan_result.data else None

        checklist_items_count = 0
        stakeholder_tasks_count = {"it": 0, "admin": 0, "manager": 0}

        if plan_id:
            items_to_insert = []
            for idx, task in enumerate(checklist_tasks):
                deadline_date = start_date_parsed + timedelta(days=task["deadline_day"])
                items_to_insert.append({
                    "plan_id": plan_id,
                    "employee_id": employee_id,
                    "title": task["title"],
                    "description": task["description"],
                    "category": task["category"],
                    "week": task["week"],
                    "deadline_day": task["deadline_day"],
                    "deadline_date": deadline_date.isoformat(),
                    "owner": task["owner"],
                    "is_mandatory": task["is_mandatory"],
                    "is_compliance": task["is_compliance"],
                    "status": "chua_bat_dau",
                    "sort_order": idx,
                })

            supabase.table("checklist_items").insert(items_to_insert).execute()
            checklist_items_count = len(items_to_insert)

            # ─── Auto-create stakeholder_tasks (Bug #2 fix) ───
            # Webhook = full flow: NV, IT, Admin, Manager đều nhận task ngay
            stakeholder_items = (
                supabase.table("checklist_items")
                .select("id, title, description, owner, deadline_date")
                .eq("plan_id", plan_id)
                .neq("owner", "new_hire")
                .execute()
            )

            st_tasks_to_insert = []
            for item in (stakeholder_items.data or []):
                owner = item["owner"]
                if owner not in ("it", "admin", "manager", "hr"):
                    continue

                st_task = {
                    "plan_id": plan_id,
                    "employee_id": employee_id,
                    "checklist_item_id": item["id"],
                    "assigned_to_team": owner if owner != "hr" else "admin",
                    "title": item["title"],
                    "description": item.get("description"),
                    "status": "pending",
                    "deadline": item.get("deadline_date"),
                    "details": {
                        "employee_name": data.full_name,
                        "role": data.role,
                        "department": data.department,
                    },
                    "created_at": datetime.now().isoformat(),
                }

                if owner == "manager" and data.manager_id:
                    st_task["assigned_to_user_id"] = data.manager_id

                st_tasks_to_insert.append(st_task)
                team_key = owner if owner in stakeholder_tasks_count else "admin"
                stakeholder_tasks_count[team_key] = stakeholder_tasks_count.get(team_key, 0) + 1

            if st_tasks_to_insert:
                supabase.table("stakeholder_tasks").insert(st_tasks_to_insert).execute()

            # Update employee status → in_progress
            supabase.table("employees").update({
                "onboarding_status": "in_progress",
                "updated_at": datetime.now().isoformat(),
            }).eq("id", employee_id).execute()

        # (e) Gửi email thông báo cho stakeholders
        email_results = {}
        if plan_id and st_tasks_to_insert:
            email_results = await notify_stakeholders(
                plan_id=plan_id,
                employee_info={
                    "id": employee_id,
                    "full_name": data.full_name,
                    "role": data.role,
                    "department": data.department,
                    "start_date": data.start_date,
                    "manager_id": data.manager_id,
                },
            )

        # (f) Log webhook
        _log_webhook(supabase, "in", "employee.created", request_body, success=True)

        return _ok({
            "employee_id": employee_id,
            "employee_code": employee_code,
            "onboarding_plan_id": plan_id,
            "plan_status": "da_duyet",
            "checklist_items_count": checklist_items_count,
            "stakeholder_tasks_created": stakeholder_tasks_count,
            "preboarding_docs_created": len(docs_to_insert),
            "stakeholder_emails": email_results,
            "message": "Đã tạo NV + checklist + auto-approve + stakeholder tasks + email",
        })

    except Exception as e:
        logger.error(f"Webhook new-employee error: {e}")
        try:
            supabase = get_supabase()
            _log_webhook(supabase, "in", "employee.created", request_body,
                         success=False, error_message=str(e))
        except Exception:
            pass
        return _err(str(e))


@router.post(
    "/lms/course-completed",
    summary="LMS bao hoan thanh khoa hoc",
    description="LMS bao NV hoan thanh 1 khoa training. "
                "Tu dong tim checklist item khop va danh dau hoan thanh.",
)
async def webhook_course_completed(body: CourseCompletedWebhook):
    """POST /api/webhooks/lms/course-completed — cap nhat checklist tu LMS."""
    request_body = body.model_dump(mode="json")

    try:
        supabase = get_supabase()
        data = body.data

        # (a) Tìm checklist_items khớp với course_name (flexible search)
        # Thử tìm bằng ILIKE trên title
        items_result = (
            supabase.table("checklist_items")
            .select("id, plan_id, title, status")
            .eq("employee_id", data.employee_id)
            .neq("status", "hoan_thanh")
            .execute()
        )

        items = items_result.data or []

        # Tìm item khớp (flexible matching)
        course_name_lower = data.course_name.lower()
        course_words = course_name_lower.split()
        matched_item = None

        for item in items:
            title_lower = item["title"].lower()
            # Exact substring match
            if course_name_lower in title_lower or title_lower in course_name_lower:
                matched_item = item
                break
            # Word overlap match (ít nhất 2 từ trùng)
            title_words = title_lower.split()
            overlap = set(course_words) & set(title_words)
            if len(overlap) >= 2:
                matched_item = item
                break

        if matched_item:
            # (b) Update checklist_item
            supabase.table("checklist_items").update({
                "status": "hoan_thanh",
                "completed_at": datetime.now().isoformat(),
            }).eq("id", matched_item["id"]).execute()

            # Tính lại completion_percentage
            new_percentage = _recalc_completion(supabase, matched_item["plan_id"])

            _log_webhook(supabase, "in", "course.completed", request_body, success=True)

            return _ok({
                "employee_id": data.employee_id,
                "course_name": data.course_name,
                "checklist_item_found": True,
                "checklist_item_id": matched_item["id"],
                "new_completion_percentage": new_percentage,
                "message": "Đã cập nhật checklist",
            })
        else:
            # (c) Không tìm thấy item khớp
            _log_webhook(supabase, "in", "course.completed", request_body, success=True)

            return _ok({
                "employee_id": data.employee_id,
                "course_name": data.course_name,
                "checklist_item_found": False,
                "checklist_item_id": None,
                "new_completion_percentage": None,
                "message": "Không tìm thấy checklist item khớp",
            })

    except Exception as e:
        logger.error(f"Webhook course-completed error: {e}")
        try:
            supabase = get_supabase()
            _log_webhook(supabase, "in", "course.completed", request_body,
                         success=False, error_message=str(e))
        except Exception:
            pass
        return _err(str(e))


@router.post(
    "/it/ticket-resolved",
    summary="IT bao provision xong",
    description="IT bao da provision accounts/devices xong cho NV moi. "
                "Tu dong update stakeholder_tasks va checklist_items lien quan.",
)
async def webhook_ticket_resolved(body: TicketResolvedWebhook):
    """POST /api/webhooks/it/ticket-resolved — cap nhat tasks IT."""
    request_body = body.model_dump(mode="json")

    try:
        supabase = get_supabase()
        data = body.data

        # (a) Update stakeholder_tasks (IT, pending → completed)
        st_result = (
            supabase.table("stakeholder_tasks")
            .update({
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
                "completed_by": data.resolved_by,
            })
            .eq("employee_id", data.employee_id)
            .eq("assigned_to_team", "it")
            .eq("status", "pending")
            .execute()
        )

        stakeholder_tasks_completed = len(st_result.data) if st_result.data else 0

        # (b) Update checklist_items (owner = 'it')
        ci_result = (
            supabase.table("checklist_items")
            .select("id, plan_id")
            .eq("employee_id", data.employee_id)
            .eq("owner", "it")
            .neq("status", "hoan_thanh")
            .execute()
        )

        checklist_items_updated = 0
        plan_id = None

        for item in (ci_result.data or []):
            supabase.table("checklist_items").update({
                "status": "hoan_thanh",
                "completed_at": datetime.now().isoformat(),
            }).eq("id", item["id"]).execute()
            checklist_items_updated += 1
            plan_id = item["plan_id"]

        # (c) Tính lại completion_percentage
        new_percentage = 0.0
        if plan_id:
            new_percentage = _recalc_completion(supabase, plan_id)

        # (d) Log webhook
        _log_webhook(supabase, "in", "ticket.resolved", request_body, success=True)

        return _ok({
            "employee_id": data.employee_id,
            "stakeholder_tasks_completed": stakeholder_tasks_completed,
            "checklist_items_updated": checklist_items_updated,
            "new_completion_percentage": new_percentage,
            "message": "Đã cập nhật tasks IT",
        })

    except Exception as e:
        logger.error(f"Webhook ticket-resolved error: {e}")
        try:
            supabase = get_supabase()
            _log_webhook(supabase, "in", "ticket.resolved", request_body,
                         success=False, error_message=str(e))
        except Exception:
            pass
        return _err(str(e))


# ═══════════════════════════════════════════════════════════════════════
# Webhook In #4: HRIS employee-updated
# ═══════════════════════════════════════════════════════════════════════


class EmployeeUpdateData(BaseModel):
    """Data cho employee-updated webhook."""
    employee_id: str | None = Field(
        default=None,
        description="UUID nếu biết",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    email: str | None = Field(
        default=None,
        description="Email lookup nếu không có UUID",
        examples=["an.nguyen@company.com"],
    )
    changes: dict = Field(
        ...,
        description="Fields thay đổi. Keys: department, role, seniority, "
                    "start_date, manager_id, full_name, email, location",
        examples=[{"department": "data", "role": "data_engineer"}],
    )


class EmployeeUpdatedWebhook(BaseModel):
    """Body cho POST /api/webhooks/hris/employee-updated."""
    event: str = Field(default="employee.updated", examples=["employee.updated"])
    data: EmployeeUpdateData


@router.post(
    "/hris/employee-updated",
    summary="HRIS cap nhat NV",
    description="HRIS bao NV thay doi dept/role/start_date/manager. "
                "Tu dong cap nhat employee, recalc checklist neu can.",
)
async def webhook_employee_updated(body: EmployeeUpdatedWebhook):
    """POST /api/webhooks/hris/employee-updated — cap nhat NV tu HRIS."""
    request_body = body.model_dump(mode="json")

    try:
        supabase = get_supabase()
        data = body.data

        # (a) Tìm employee bằng UUID hoặc email
        employee = None

        if data.employee_id:
            emp_result = (
                supabase.table("employees")
                .select("*")
                .eq("id", data.employee_id)
                .limit(1)
                .execute()
            )
            if emp_result.data:
                employee = emp_result.data[0]

        if not employee and data.email:
            emp_result = (
                supabase.table("employees")
                .select("*")
                .eq("email", data.email.strip().lower())
                .limit(1)
                .execute()
            )
            if emp_result.data:
                employee = emp_result.data[0]

        if not employee:
            _log_webhook(supabase, "in", "employee.updated", request_body,
                         success=False, error_message="Employee not found")
            return _err("Employee not found (cần employee_id hoặc email)")

        employee_id = employee["id"]
        changes = data.changes
        actions_taken = []

        # ─── Allowed fields to update on employee record ───
        ALLOWED_FIELDS = {
            "full_name", "email", "role", "department", "seniority",
            "start_date", "manager_id", "location", "personal_email",
        }

        update_data = {}
        for key, value in changes.items():
            if key in ALLOWED_FIELDS:
                update_data[key] = value

        if update_data:
            update_data["updated_at"] = datetime.now().isoformat()
            supabase.table("employees").update(update_data).eq("id", employee_id).execute()
            actions_taken.append(f"Updated employee fields: {list(update_data.keys())}")

        # ─── (b) Role/Department changed → add new tasks (Option A: giữ progress) ───
        role_changed = "role" in changes or "department" in changes

        if role_changed:
            new_role = changes.get("role", employee["role"])
            new_dept = changes.get("department", employee["department"])
            new_seniority = changes.get("seniority", employee.get("seniority", "junior"))

            # Lấy plan hiện tại
            plan_result = (
                supabase.table("onboarding_plans")
                .select("id, status")
                .eq("employee_id", employee_id)
                .in_("status", ["da_duyet", "dang_thuc_hien"])
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            if plan_result.data:
                plan = plan_result.data[0]
                plan_id = plan["id"]

                # Lấy existing checklist item titles (để dedupe)
                existing_items = (
                    supabase.table("checklist_items")
                    .select("title")
                    .eq("plan_id", plan_id)
                    .execute()
                )
                existing_titles = {item["title"] for item in (existing_items.data or [])}

                # Build tasks mới theo role/dept mới
                new_tasks = _build_checklist(
                    role=new_role,
                    department=new_dept,
                    seniority=new_seniority,
                )

                # Chỉ thêm tasks chưa có (dedupe theo title)
                tasks_to_add = [t for t in new_tasks if t["title"] not in existing_titles]

                if tasks_to_add:
                    # Tính start_date cho deadline
                    start_date_str = changes.get("start_date", employee.get("start_date"))
                    try:
                        start_date_parsed = date.fromisoformat(str(start_date_str))
                    except (ValueError, TypeError):
                        start_date_parsed = date.today()

                    # Lấy max sort_order hiện tại
                    max_order_result = (
                        supabase.table("checklist_items")
                        .select("sort_order")
                        .eq("plan_id", plan_id)
                        .order("sort_order", desc=True)
                        .limit(1)
                        .execute()
                    )
                    max_order = max_order_result.data[0]["sort_order"] if max_order_result.data else 0

                    items_to_insert = []
                    for idx, task in enumerate(tasks_to_add):
                        deadline_date = start_date_parsed + timedelta(days=task["deadline_day"])
                        items_to_insert.append({
                            "plan_id": plan_id,
                            "employee_id": employee_id,
                            "title": task["title"],
                            "description": task["description"],
                            "category": task["category"],
                            "week": task["week"],
                            "deadline_day": task["deadline_day"],
                            "deadline_date": deadline_date.isoformat(),
                            "owner": task["owner"],
                            "is_mandatory": task["is_mandatory"],
                            "is_compliance": task["is_compliance"],
                            "status": "chua_bat_dau",
                            "sort_order": max_order + idx + 1,
                        })

                    supabase.table("checklist_items").insert(items_to_insert).execute()

                    # Update total_items trên plan
                    new_total = len(existing_titles) + len(tasks_to_add)
                    supabase.table("onboarding_plans").update({
                        "total_items": new_total,
                        "updated_at": datetime.now().isoformat(),
                    }).eq("id", plan_id).execute()

                    # Recalc completion
                    _recalc_completion(supabase, plan_id)

                    # Tạo stakeholder_tasks cho items mới (owner != new_hire)
                    new_stakeholder_items = [i for i in items_to_insert if i["owner"] != "new_hire"]
                    st_tasks_to_insert = []
                    for item_data in new_stakeholder_items:
                        # Cần lấy ID sau khi insert — query lại
                        pass

                    # Query lại items vừa insert để lấy IDs
                    new_items_result = (
                        supabase.table("checklist_items")
                        .select("id, title, description, owner, deadline_date")
                        .eq("plan_id", plan_id)
                        .neq("owner", "new_hire")
                        .gt("sort_order", max_order)
                        .execute()
                    )

                    for item in (new_items_result.data or []):
                        owner = item["owner"]
                        if owner not in ("it", "admin", "manager"):
                            continue
                        st_task = {
                            "plan_id": plan_id,
                            "employee_id": employee_id,
                            "checklist_item_id": item["id"],
                            "assigned_to_team": owner,
                            "title": item["title"],
                            "description": item.get("description"),
                            "status": "pending",
                            "deadline": item.get("deadline_date"),
                            "details": {
                                "employee_name": changes.get("full_name", employee["full_name"]),
                                "role": new_role,
                                "department": new_dept,
                                "trigger": "role_change",
                            },
                            "created_at": datetime.now().isoformat(),
                        }

                        mgr_id = changes.get("manager_id", employee.get("manager_id"))
                        if owner == "manager" and mgr_id:
                            st_task["assigned_to_user_id"] = mgr_id

                        st_tasks_to_insert.append(st_task)

                    if st_tasks_to_insert:
                        supabase.table("stakeholder_tasks").insert(st_tasks_to_insert).execute()

                    actions_taken.append(
                        f"Added {len(tasks_to_add)} new tasks for role={new_role}, "
                        f"dept={new_dept}. {len(st_tasks_to_insert)} stakeholder tasks created."
                    )
                else:
                    actions_taken.append("Role/dept changed but no new tasks needed (all tasks already exist)")

        # ─── (c) Start date changed → recalculate deadlines ───
        if "start_date" in changes:
            new_start_str = changes["start_date"]
            try:
                new_start = date.fromisoformat(str(new_start_str))
            except (ValueError, TypeError):
                _log_webhook(supabase, "in", "employee.updated", request_body,
                             success=False, error_message=f"Invalid start_date: {new_start_str}")
                return _err(f"Invalid start_date format: {new_start_str}")

            # Lấy plan hiện tại
            plan_result = (
                supabase.table("onboarding_plans")
                .select("id")
                .eq("employee_id", employee_id)
                .in_("status", ["da_duyet", "dang_thuc_hien"])
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            if plan_result.data:
                plan_id = plan_result.data[0]["id"]

                # Lấy tất cả items chưa hoàn thành
                items_result = (
                    supabase.table("checklist_items")
                    .select("id, deadline_day")
                    .eq("plan_id", plan_id)
                    .neq("status", "hoan_thanh")
                    .execute()
                )

                updated_count = 0
                for item in (items_result.data or []):
                    new_deadline = new_start + timedelta(days=item["deadline_day"])
                    supabase.table("checklist_items").update({
                        "deadline_date": new_deadline.isoformat(),
                    }).eq("id", item["id"]).execute()
                    updated_count += 1

                # Update stakeholder_tasks deadlines
                st_items = (
                    supabase.table("stakeholder_tasks")
                    .select("id, checklist_item_id")
                    .eq("plan_id", plan_id)
                    .neq("status", "completed")
                    .execute()
                )
                for st in (st_items.data or []):
                    # Lookup deadline from checklist_item
                    ci = (
                        supabase.table("checklist_items")
                        .select("deadline_date")
                        .eq("id", st["checklist_item_id"])
                        .limit(1)
                        .execute()
                    )
                    if ci.data:
                        supabase.table("stakeholder_tasks").update({
                            "deadline": ci.data[0]["deadline_date"],
                        }).eq("id", st["id"]).execute()

                actions_taken.append(
                    f"Recalculated deadlines: {updated_count} items "
                    f"(new start_date={new_start_str})"
                )

        # ─── (d) Manager changed → reassign stakeholder tasks ───
        if "manager_id" in changes and not role_changed:
            new_manager_id = changes["manager_id"]

            # Update existing manager stakeholder_tasks
            supabase.table("stakeholder_tasks").update({
                "assigned_to_user_id": new_manager_id,
            }).eq("employee_id", employee_id).eq(
                "assigned_to_team", "manager"
            ).neq("status", "completed").execute()

            actions_taken.append(f"Reassigned manager tasks to {new_manager_id}")

        # (e) Log webhook
        _log_webhook(supabase, "in", "employee.updated", request_body, success=True)

        return _ok({
            "employee_id": employee_id,
            "changes_applied": list(changes.keys()),
            "actions_taken": actions_taken,
            "message": "Employee đã cập nhật",
        })

    except Exception as e:
        logger.error(f"Webhook employee-updated error: {e}")
        try:
            supabase = get_supabase()
            _log_webhook(supabase, "in", "employee.updated", request_body,
                         success=False, error_message=str(e))
        except Exception:
            pass
        return _err(str(e))


# ═══════════════════════════════════════════════════════════════════════
# Webhook In #5: Documents submitted
# ═══════════════════════════════════════════════════════════════════════


class DocumentSubmittedData(BaseModel):
    """Data cho documents/submitted webhook."""
    employee_id: str = Field(
        ...,
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    document_type: str = Field(
        ...,
        description="Loại giấy tờ: cmnd, photo_3x4, so_bhxh, bang_cap, so_tai_khoan",
        examples=["cmnd"],
    )
    filename: str = Field(
        ...,
        examples=["cmnd_front_back.pdf"],
    )
    external_url: str | None = Field(
        default=None,
        description="URL trên hệ thống ngoài (Google Drive, SharePoint...)",
        examples=["https://drive.google.com/file/d/abc123"],
    )


class DocumentSubmittedWebhook(BaseModel):
    """Body cho POST /api/webhooks/documents/submitted."""
    event: str = Field(default="document.submitted", examples=["document.submitted"])
    data: DocumentSubmittedData


@router.post(
    "/documents/submitted",
    summary="Doc Portal bao NV upload giay to",
    description="Doc Portal ben ngoai bao NV da upload giay to. "
                "Tu dong cap nhat preboarding_documents status.",
)
async def webhook_document_submitted(body: DocumentSubmittedWebhook):
    """POST /api/webhooks/documents/submitted — cap nhat preboarding tu Doc Portal."""
    request_body = body.model_dump(mode="json")

    try:
        supabase = get_supabase()
        data = body.data

        # (a) Kiểm tra employee tồn tại
        emp_result = (
            supabase.table("employees")
            .select("id, full_name")
            .eq("id", data.employee_id)
            .limit(1)
            .execute()
        )

        if not emp_result.data:
            _log_webhook(supabase, "in", "document.submitted", request_body,
                         success=False, error_message="Employee not found")
            return _err(f"Employee {data.employee_id} not found")

        # (b) Update preboarding_documents
        update_result = (
            supabase.table("preboarding_documents")
            .update({
                "status": "uploaded",
                "filename": data.filename,
                "storage_path": data.external_url or f"external/{data.employee_id}/{data.filename}",
                "uploaded_at": datetime.now().isoformat(),
            })
            .eq("employee_id", data.employee_id)
            .eq("document_type", data.document_type)
            .execute()
        )

        if not update_result.data:
            _log_webhook(supabase, "in", "document.submitted", request_body,
                         success=False,
                         error_message=f"document_type '{data.document_type}' not found")
            return _err(
                f"Không tìm thấy document_type '{data.document_type}' "
                f"cho employee {data.employee_id}"
            )

        # (c) Kiểm tra remaining missing docs
        missing_result = (
            supabase.table("preboarding_documents")
            .select("document_type")
            .eq("employee_id", data.employee_id)
            .eq("status", "missing")
            .execute()
        )

        remaining = [d["document_type"] for d in (missing_result.data or [])]

        # (d) Log webhook
        _log_webhook(supabase, "in", "document.submitted", request_body, success=True)

        return _ok({
            "employee_id": data.employee_id,
            "document_type": data.document_type,
            "status": "uploaded",
            "remaining_count": len(remaining),
            "remaining": remaining,
            "message": "Đã cập nhật trạng thái giấy tờ",
        })

    except Exception as e:
        logger.error(f"Webhook document-submitted error: {e}")
        try:
            supabase = get_supabase()
            _log_webhook(supabase, "in", "document.submitted", request_body,
                         success=False, error_message=str(e))
        except Exception:
            pass
        return _err(str(e))
