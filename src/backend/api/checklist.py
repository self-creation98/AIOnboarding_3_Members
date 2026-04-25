"""
Checklist API — Endpoints cho quản lý onboarding checklist.

Kiến trúc 3-Layer tạo kế hoạch:
  Layer 1: HR Template — tasks compliance/admin bắt buộc cho MỌI NV
  Layer 2: Role-Specific — tasks theo role/department (TODO: RAG search)
  Layer 3: AI Personalization — cá nhân hóa timeline (TODO: Gemini)

Endpoints:
- POST   /api/checklist/generate                  — Tạo checklist (3-layer)
- GET    /api/checklist/{plan_id}                  — Chi tiết plan + items
- POST   /api/checklist/{plan_id}/approve          — Duyệt plan
- PATCH  /api/checklist/items/{item_id}/complete   — Hoàn thành 1 item
- GET    /api/employees/{employee_id}/checklist    — Checklist theo employee
- DELETE /api/checklist/{plan_id}                  — Xóa plan + items
"""

import logging
from datetime import datetime, timedelta, date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.backend.database import get_supabase
from src.backend.api.deps import get_current_active_user
from src.backend.schemas import UserInfo
from src.backend.services.event_dispatcher import fire_event
from src.backend.services.stakeholder_notifier import notify_stakeholders

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Checklist"])


# ─── Schemas ───


class GenerateRequest(BaseModel):
    """Body cho POST /api/checklist/generate."""
    employee_id: str = Field(..., description="UUID of employee", examples=["550e8400-e29b-41d4-a716-446655440000"])


class ApproveRequest(BaseModel):
    """Body cho POST /api/checklist/{plan_id}/approve."""
    approved_by: str = Field(..., description="UUID of HR user who approves", examples=["550e8400-e29b-41d4-a716-446655440000"])


class CompleteRequest(BaseModel):
    """Body cho PATCH /api/checklist/items/{item_id}/complete."""
    completed_by: str = Field(..., description="UUID of user who completed", examples=["550e8400-e29b-41d4-a716-446655440000"])


# ─── Helpers ───


def _ok(data):
    """Standard success response."""
    return {"success": True, "data": data}


def _err(msg: str, status_code: int = 400):
    """Standard error response — returned as dict, caller sets status."""
    return {"success": False, "error": msg}


# ─── 3-Layer Checklist Generation ───


# Layer 1: HR Template — Bắt buộc cho MỌI nhân viên (không cần AI)
MANDATORY_TEMPLATE = [
    # Pre-boarding (trước ngày bắt đầu) — owner: stakeholder
    {"title": "Chuẩn bị laptop + accounts", "description": "Email, Slack, VPN. Spec theo role/department.", "category": "tools", "week": 0, "deadline_day": 0, "owner": "it", "is_mandatory": True, "is_compliance": False},
    {"title": "Chuẩn bị badge + chỗ ngồi", "description": "Badge nhân viên, chỗ ngồi theo department", "category": "admin", "week": 0, "deadline_day": 0, "owner": "admin", "is_mandatory": True, "is_compliance": False},
    {"title": "Assign buddy", "description": "Chọn buddy trong team để hỗ trợ NV mới tuần đầu", "category": "social", "week": 0, "deadline_day": 1, "owner": "manager", "is_mandatory": True, "is_compliance": False},
    # Tuần 1 — compliance bắt buộc
    {"title": "Nộp hồ sơ đầy đủ", "description": "CMND, ảnh 3x4, bằng cấp, số TK ngân hàng", "category": "admin", "week": 1, "deadline_day": 2, "owner": "new_hire", "is_mandatory": True, "is_compliance": False},
    {"title": "Đọc nội quy công ty", "description": "Đọc và xác nhận đã hiểu nội quy", "category": "compliance", "week": 1, "deadline_day": 2, "owner": "new_hire", "is_mandatory": True, "is_compliance": True},
    {"title": "Security Awareness Training", "description": "Hoàn thành khóa đào tạo bảo mật thông tin", "category": "compliance", "week": 1, "deadline_day": 5, "owner": "new_hire", "is_mandatory": True, "is_compliance": True},
    # Tuần 1 — social & management
    {"title": "1-on-1 với Manager tuần đầu", "description": "Gặp manager để hiểu kỳ vọng và mục tiêu", "category": "role_specific", "week": 1, "deadline_day": 3, "owner": "manager", "is_mandatory": True, "is_compliance": False},
    {"title": "Gặp team members", "description": "Coffee chat với từng thành viên trong team", "category": "social", "week": 1, "deadline_day": 5, "owner": "new_hire", "is_mandatory": False, "is_compliance": False},
    # Tuần 2 — goals
    {"title": "Set 30-60-90 day goals", "description": "Cùng manager đặt mục tiêu cho 3 tháng đầu", "category": "role_specific", "week": 2, "deadline_day": 10, "owner": "manager", "is_mandatory": True, "is_compliance": False},
]

# Layer 2: Role-Specific Templates — Dựa trên role + department
# TODO: Thay bằng RAG search khi tích hợp:
#   rag_context = await rag_search(query=f"onboarding {role} {department}", ...)
#   role_tasks = await gemini_extract_tasks(rag_context)
ROLE_TEMPLATES = {
    "software_engineer": [
        {"title": "Setup dev environment", "description": "Cài đặt IDE, clone repo, chạy project local", "category": "tools", "week": 1, "deadline_day": 3, "owner": "new_hire", "is_mandatory": True, "is_compliance": False},
        {"title": "Setup VPN", "description": "Cài VPN client, kết nối mạng nội bộ", "category": "tools", "week": 1, "deadline_day": 2, "owner": "new_hire", "is_mandatory": True, "is_compliance": False},
        {"title": "Hoàn thành Git workflow training", "description": "Hiểu branching, PR, code review process", "category": "training", "week": 2, "deadline_day": 10, "owner": "new_hire", "is_mandatory": True, "is_compliance": False},
        {"title": "Review tech stack documentation", "description": "Đọc docs về architecture, coding standards, CI/CD pipeline", "category": "training", "week": 2, "deadline_day": 12, "owner": "new_hire", "is_mandatory": True, "is_compliance": False},
    ],
    "marketing": [
        {"title": "Học HubSpot CRM", "description": "Hoàn thành khóa onboarding HubSpot nội bộ", "category": "tools", "week": 1, "deadline_day": 5, "owner": "new_hire", "is_mandatory": True, "is_compliance": False},
        {"title": "Đọc Brand Guidelines", "description": "Đọc và hiểu brand voice, visual identity", "category": "training", "week": 1, "deadline_day": 3, "owner": "new_hire", "is_mandatory": True, "is_compliance": False},
        {"title": "Review social media policy", "description": "Đọc quy định về MXH đại diện công ty", "category": "compliance", "week": 1, "deadline_day": 2, "owner": "new_hire", "is_mandatory": True, "is_compliance": True},
    ],
    "default": [
        {"title": "Setup VPN", "description": "Cài VPN client, kết nối mạng nội bộ", "category": "tools", "week": 1, "deadline_day": 2, "owner": "new_hire", "is_mandatory": True, "is_compliance": False},
        {"title": "Tìm hiểu công cụ làm việc", "description": "Học sử dụng các tool chính: email, Slack, Jira/Trello", "category": "tools", "week": 1, "deadline_day": 3, "owner": "new_hire", "is_mandatory": True, "is_compliance": False},
    ],
}


def _build_checklist(role: str, department: str, seniority: str) -> list[dict]:
    """
    3-Layer Checklist Builder.

    Layer 1: MANDATORY_TEMPLATE — tasks bắt buộc cho MỌI NV
    Layer 2: ROLE_TEMPLATES — tasks theo role (TODO: thay bằng RAG search)
    Layer 3: AI Personalization — (TODO: Gemini cá nhân hóa timeline)

    Returns:
        List of task dicts sẵn sàng insert vào DB.
    """
    # ─── Layer 1: HR Template (bắt buộc) ───
    tasks = list(MANDATORY_TEMPLATE)

    # ─── Layer 2: Role-specific tasks ───
    # TODO: Thay bằng RAG search:
    #   rag_chunks = await rag_search(
    #       query=f"onboarding tasks cho {role} {department}",
    #       filters={"role_tags": [role], "department_tags": [department]}
    #   )
    #   role_tasks = await gemini_extract_tasks(rag_chunks, role, seniority)
    role_key = role.lower().replace(" ", "_")
    role_tasks = ROLE_TEMPLATES.get(role_key, ROLE_TEMPLATES["default"])
    tasks.extend(role_tasks)

    # ─── Layer 3: AI Personalization (TODO) ───
    # TODO: Gọi Gemini để cá nhân hóa:
    #   personalized = await gemini_personalize_plan(
    #       tasks=tasks,
    #       employee_context={"role": role, "seniority": seniority, ...},
    #       prompt="Sắp xếp timeline hợp lý, thêm gợi ý cho junior..."
    #   )
    # Tạm thời: điều chỉnh đơn giản theo seniority
    if seniority in ("senior", "lead", "manager"):
        # Senior: deadline nới rộng hơn, bỏ 1 số training cơ bản
        for task in tasks:
            if task["week"] >= 1 and task["owner"] == "new_hire":
                task["deadline_day"] = task["deadline_day"] + 2  # thêm 2 ngày
    elif seniority == "intern":
        # Intern: thêm task hướng dẫn chi tiết hơn
        tasks.append({
            "title": "Hoàn thành orientation với HR",
            "description": "HR hướng dẫn chi tiết quy trình, phúc lợi, giải đáp thắc mắc",
            "category": "admin", "week": 1, "deadline_day": 1,
            "owner": "hr", "is_mandatory": True, "is_compliance": False,
        })

    return tasks


# ─── Endpoints ───


@router.post(
    "/api/checklist/generate",
    summary="Tao checklist onboarding (3-layer)",
    description="Tao ke hoach onboarding cho nhan vien. "
                "3 tang: HR Template + Role-Specific + AI Personalization.",
    status_code=201,
)
async def generate_checklist(
    body: GenerateRequest,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """POST /api/checklist/generate — tao checklist 3-layer."""
    try:
        supabase = get_supabase()

        # Lay employee info
        emp_result = (
            supabase.table("employees")
            .select("id, full_name, role, department, seniority, start_date")
            .eq("id", body.employee_id)
            .limit(1)
            .execute()
        )

        if not emp_result.data:
            return _err(f"Employee {body.employee_id} not found")

        employee = emp_result.data[0]

        # Kiem tra da co plan chua
        existing_plan = (
            supabase.table("onboarding_plans")
            .select("id")
            .eq("employee_id", body.employee_id)
            .limit(1)
            .execute()
        )

        if existing_plan.data:
            return _err("Nhân viên đã có kế hoạch onboarding")

        # ─── 3-Layer Checklist Generation ───
        tasks = _build_checklist(
            role=employee.get("role", "default"),
            department=employee.get("department", ""),
            seniority=employee.get("seniority", "junior"),
        )

        # Tao onboarding_plans
        plan_result = (
            supabase.table("onboarding_plans")
            .insert({
                "employee_id": body.employee_id,
                "status": "ban_thao",
                "generated_by": "ai",
                "total_items": len(tasks),
                "completed_items": 0,
                "completion_percentage": 0,
            })
            .execute()
        )

        if not plan_result.data:
            return _err("Failed to create onboarding plan")

        plan_id = plan_result.data[0]["id"]

        # Parse start_date
        start_date_str = employee.get("start_date")
        if start_date_str:
            start_date = date.fromisoformat(str(start_date_str))
        else:
            start_date = date.today()

        # Tao checklist_items
        items_to_insert = []
        for idx, task in enumerate(tasks):
            deadline_date = start_date + timedelta(days=task["deadline_day"])
            items_to_insert.append({
                "plan_id": plan_id,
                "employee_id": body.employee_id,
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

        return _ok({
            "plan_id": plan_id,
            "employee_id": body.employee_id,
            "items_count": len(tasks),
            "generation_layers": {
                "layer1_mandatory": len(MANDATORY_TEMPLATE),
                "layer2_role_specific": len(tasks) - len(MANDATORY_TEMPLATE),
                "layer3_ai_personalized": "pending",  # TODO: khi nối Gemini
            },
            "status": "ban_thao",
        })

    except Exception as e:
        logger.error(f"Generate checklist error: {e}")
        return _err(str(e))


@router.get(
    "/api/checklist/{plan_id}",
    summary="Chi tiet plan + items",
    description="Lay thong tin onboarding plan va tat ca checklist items.",
)
async def get_plan(
    plan_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/checklist/{plan_id} — chi tiet plan + items."""
    try:
        supabase = get_supabase()

        # Plan info
        plan_result = (
            supabase.table("onboarding_plans")
            .select("id, employee_id, status, total_items, completed_items, completion_percentage")
            .eq("id", plan_id)
            .limit(1)
            .execute()
        )

        if not plan_result.data:
            return _err(f"Plan {plan_id} not found")

        plan = plan_result.data[0]

        # Items
        items_result = (
            supabase.table("checklist_items")
            .select(
                "id, title, description, category, week, deadline_day, "
                "deadline_date, owner, is_mandatory, is_compliance, "
                "status, sort_order"
            )
            .eq("plan_id", plan_id)
            .order("week")
            .order("sort_order")
            .execute()
        )

        plan["items"] = items_result.data or []

        return _ok(plan)

    except Exception as e:
        logger.error(f"Get plan error: {e}")
        return _err(str(e))


@router.post(
    "/api/checklist/{plan_id}/approve",
    summary="Duyet plan",
    description="HR duyet ke hoach onboarding. Chuyen status thanh 'da_duyet' "
                "va employee sang 'in_progress'.",
)
async def approve_plan(
    plan_id: str,
    body: ApproveRequest,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """POST /api/checklist/{plan_id}/approve — duyet plan."""
    try:
        supabase = get_supabase()

        # Update plan
        plan_result = (
            supabase.table("onboarding_plans")
            .update({
                "status": "da_duyet",
                "approved_by": body.approved_by,
                "approved_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            })
            .eq("id", plan_id)
            .execute()
        )

        if not plan_result.data:
            return _err(f"Plan {plan_id} not found")

        # Update employee onboarding_status
        employee_id = plan_result.data[0].get("employee_id")
        if employee_id:
            supabase.table("employees").update({
                "onboarding_status": "in_progress",
                "updated_at": datetime.now().isoformat(),
            }).eq("id", employee_id).execute()

        return _ok({
            "plan_id": plan_id,
            "status": "da_duyet",
            "approved_at": plan_result.data[0].get("approved_at"),
        })

    except Exception as e:
        logger.error(f"Approve plan error: {e}")
        return _err(str(e))


@router.patch(
    "/api/checklist/items/{item_id}/complete",
    summary="Hoan thanh 1 item",
    description="Danh dau 1 checklist item la hoan thanh. "
                "Tu dong tinh lai completion_percentage.",
)
async def complete_item(
    item_id: str,
    body: CompleteRequest,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """PATCH /api/checklist/items/{item_id}/complete — hoan thanh item."""
    try:
        supabase = get_supabase()

        # Update item
        item_result = (
            supabase.table("checklist_items")
            .update({
                "status": "hoan_thanh",
                "completed_at": datetime.now().isoformat(),
                "completed_by": body.completed_by,
            })
            .eq("id", item_id)
            .execute()
        )

        if not item_result.data:
            return _err(f"Item {item_id} not found")

        item = item_result.data[0]
        plan_id = item["plan_id"]

        # Tinh lai completed_items
        completed_result = (
            supabase.table("checklist_items")
            .select("id", count="exact")
            .eq("plan_id", plan_id)
            .eq("status", "hoan_thanh")
            .execute()
        )
        completed_items = completed_result.count if completed_result.count is not None else 0

        # Lay total_items tu plan
        plan_result = (
            supabase.table("onboarding_plans")
            .select("total_items, employee_id")
            .eq("id", plan_id)
            .limit(1)
            .execute()
        )

        total_items = plan_result.data[0]["total_items"] if plan_result.data else 1
        employee_id = plan_result.data[0]["employee_id"] if plan_result.data else None
        completion_percentage = round((completed_items / total_items) * 100, 1) if total_items > 0 else 0

        # Update plan
        supabase.table("onboarding_plans").update({
            "completed_items": completed_items,
            "completion_percentage": completion_percentage,
            "updated_at": datetime.now().isoformat(),
        }).eq("id", plan_id).execute()

        # Kiem tra tat ca mandatory items da hoan thanh chua
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
            # Tat ca mandatory da hoan thanh
            supabase.table("onboarding_plans").update({
                "status": "hoan_thanh",
                "updated_at": datetime.now().isoformat(),
            }).eq("id", plan_id).execute()

            if employee_id:
                supabase.table("employees").update({
                    "onboarding_status": "completed",
                    "updated_at": datetime.now().isoformat(),
                }).eq("id", employee_id).execute()

            # Fire outgoing webhook: onboarding completed
            await fire_event("employee.onboarding.completed", {
                "employee_id": employee_id,
                "plan_id": plan_id,
                "completion_percentage": completion_percentage,
            })

        return _ok({
            "item_id": item_id,
            "status": "hoan_thanh",
            "plan_completion_percentage": completion_percentage,
        })

    except Exception as e:
        logger.error(f"Complete item error: {e}")
        return _err(str(e))


@router.get(
    "/api/employees/{employee_id}/checklist",
    summary="Checklist theo employee",
    description="Lay ke hoach onboarding cua nhan vien theo employee_id.",
)
async def get_employee_checklist(
    employee_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/employees/{employee_id}/checklist — checklist theo employee."""
    try:
        supabase = get_supabase()

        # Lay plan
        plan_result = (
            supabase.table("onboarding_plans")
            .select("id, status, completion_percentage")
            .eq("employee_id", employee_id)
            .limit(1)
            .execute()
        )

        if not plan_result.data:
            return _err("Nhân viên chưa có kế hoạch onboarding")

        plan = plan_result.data[0]

        # Lay items
        items_result = (
            supabase.table("checklist_items")
            .select(
                "id, title, category, week, deadline_date, "
                "owner, is_mandatory, status, completed_at"
            )
            .eq("plan_id", plan["id"])
            .order("week")
            .order("sort_order")
            .execute()
        )

        return _ok({
            "plan_id": plan["id"],
            "status": plan["status"],
            "completion_percentage": plan["completion_percentage"],
            "items": items_result.data or [],
        })

    except Exception as e:
        logger.error(f"Get employee checklist error: {e}")
        return _err(str(e))


@router.delete(
    "/api/checklist/{plan_id}",
    summary="Xoa plan + items",
    description="Xoa ke hoach onboarding va tat ca checklist items lien quan.",
)
async def delete_plan(
    plan_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """DELETE /api/checklist/{plan_id} — xoa plan + items."""
    try:
        supabase = get_supabase()

        # Xoa items truoc (FK constraint)
        supabase.table("checklist_items").delete().eq("plan_id", plan_id).execute()

        # Xoa plan
        result = (
            supabase.table("onboarding_plans")
            .delete()
            .eq("id", plan_id)
            .execute()
        )

        if not result.data:
            return _err(f"Plan {plan_id} not found")

        return _ok({"message": "Đã xóa kế hoạch onboarding"})

    except Exception as e:
        logger.error(f"Delete plan error: {e}")
        return _err(str(e))
