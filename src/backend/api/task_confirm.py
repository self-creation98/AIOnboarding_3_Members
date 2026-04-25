"""
Task Confirm API — Public endpoint cho magic link confirmation.

IT/Manager click magic link từ email → endpoint này xử lý:
1. Verify token (không cần login)
2. Hiển thị task list (GET)
3. Confirm hoàn thành tasks (POST)

Endpoints:
- GET  /api/tasks/confirm/{token}  — Xem danh sách tasks (trả JSON cho frontend)
- POST /api/tasks/confirm/{token}  — Xác nhận hoàn thành tasks
- GET  /api/tasks/confirm-page/{token}  — HTML page tự chứa (nếu không có frontend)
"""

import logging
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from src.backend.database import get_supabase
from src.backend.services.magic_link import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["Task Confirmation (Public)"])


# ─── Schemas ───


class ConfirmTasksRequest(BaseModel):
    """Body cho POST /api/tasks/confirm/{token}."""
    task_ids: list[str] = Field(
        ...,
        description="Danh sách task IDs đã hoàn thành",
    )
    completed_by: str = Field(
        default="",
        description="Tên người xác nhận (optional)",
    )
    notes: str = Field(
        default="",
        description="Ghi chú (optional)",
    )


# ─── Helpers ───


def _ok(data):
    return {"success": True, "data": data}


def _err(msg: str):
    return {"success": False, "error": msg}


def _recalc_completion(supabase, plan_id: str) -> float:
    """Tính lại completion_percentage cho plan."""
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


# ─── Endpoints ───


@router.get(
    "/confirm/{token}",
    summary="Xem tasks tu magic link (JSON)",
    description="IT/Manager click magic link → xem danh sach tasks can hoan thanh. "
                "Khong can login. Tra ve JSON de frontend render.",
)
async def get_tasks_from_token(token: str):
    """GET /api/tasks/confirm/{token} — xem tasks tu magic link."""
    payload = verify_token(token)
    if not payload:
        return _err("Link đã hết hạn hoặc không hợp lệ")

    token_type = payload.get("type")
    team = payload.get("team", "")
    employee_id = payload.get("emp_id", "")

    try:
        supabase = get_supabase()

        # Lấy employee info
        emp_result = (
            supabase.table("employees")
            .select("full_name, role, department, start_date")
            .eq("id", employee_id)
            .limit(1)
            .execute()
        )
        employee = emp_result.data[0] if emp_result.data else {}

        # Lấy tasks theo loại token
        if token_type == "task_confirm":
            # Token cho 1 task cụ thể
            task_id = payload["sub"]
            tasks_result = (
                supabase.table("stakeholder_tasks")
                .select("id, title, description, status, deadline, completed_at")
                .eq("id", task_id)
                .execute()
            )
        elif token_type == "team_confirm":
            # Token cho tất cả tasks của 1 team trong 1 plan
            plan_id = payload["sub"]
            tasks_result = (
                supabase.table("stakeholder_tasks")
                .select("id, title, description, status, deadline, completed_at")
                .eq("plan_id", plan_id)
                .eq("assigned_to_team", team)
                .execute()
            )
        else:
            return _err("Token type không hợp lệ")

        tasks = tasks_result.data or []

        return _ok({
            "team": team,
            "employee": {
                "id": employee_id,
                "full_name": employee.get("full_name"),
                "role": employee.get("role"),
                "department": employee.get("department"),
                "start_date": str(employee.get("start_date", "")),
            },
            "tasks": tasks,
            "pending_count": sum(1 for t in tasks if t["status"] == "pending"),
            "completed_count": sum(1 for t in tasks if t["status"] == "completed"),
        })

    except Exception as e:
        logger.error(f"Get tasks from token error: {e}")
        return _err(str(e))


@router.post(
    "/confirm/{token}",
    summary="Xac nhan hoan thanh tasks",
    description="IT/Manager xac nhan da hoan thanh 1 hoac nhieu tasks. "
                "Khong can login — chi can token hop le.",
)
async def confirm_tasks(token: str, body: ConfirmTasksRequest):
    """POST /api/tasks/confirm/{token} — xac nhan hoan thanh tasks."""
    payload = verify_token(token)
    if not payload:
        return _err("Link đã hết hạn hoặc không hợp lệ")

    team = payload.get("team", "")
    employee_id = payload.get("emp_id", "")

    try:
        supabase = get_supabase()

        completed_tasks = []
        already_completed = []

        for task_id in body.task_ids:
            # Verify task thuộc đúng team và employee
            task_result = (
                supabase.table("stakeholder_tasks")
                .select("id, status, plan_id, checklist_item_id, assigned_to_team, employee_id")
                .eq("id", task_id)
                .limit(1)
                .execute()
            )

            if not task_result.data:
                continue

            task = task_result.data[0]

            # Security check: task phải thuộc đúng team & employee
            if task["assigned_to_team"] != team or task["employee_id"] != employee_id:
                continue

            if task["status"] == "completed":
                already_completed.append(task_id)
                continue

            # Update stakeholder_task → completed
            supabase.table("stakeholder_tasks").update({
                "status": "completed",
                "completed_at": datetime.now().isoformat(),
                "completed_by": body.completed_by or f"magic_link_{team}",
                "notes": body.notes or None,
            }).eq("id", task_id).execute()

            # Update linked checklist_item → hoàn thành
            if task.get("checklist_item_id"):
                supabase.table("checklist_items").update({
                    "status": "hoan_thanh",
                    "completed_at": datetime.now().isoformat(),
                }).eq("id", task["checklist_item_id"]).execute()

            completed_tasks.append(task_id)

            # Recalc plan completion
            if task.get("plan_id"):
                _recalc_completion(supabase, task["plan_id"])

        # Check if all mandatory items are done → auto-complete plan
        if completed_tasks:
            # Lấy plan_id từ task cuối cùng
            sample_task = supabase.table("stakeholder_tasks").select(
                "plan_id"
            ).eq("id", completed_tasks[0]).limit(1).execute()

            if sample_task.data:
                plan_id = sample_task.data[0]["plan_id"]

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

                    supabase.table("employees").update({
                        "onboarding_status": "completed",
                        "updated_at": datetime.now().isoformat(),
                    }).eq("id", employee_id).execute()

                    # Fire webhook: onboarding completed
                    from src.backend.services.event_dispatcher import fire_event
                    await fire_event("employee.onboarding.completed", {
                        "employee_id": employee_id,
                        "plan_id": plan_id,
                        "trigger": "magic_link_confirm",
                    })

        return _ok({
            "confirmed": completed_tasks,
            "already_completed": already_completed,
            "confirmed_count": len(completed_tasks),
            "confirmed_by": body.completed_by or f"magic_link_{team}",
            "message": f"Đã xác nhận {len(completed_tasks)} tasks hoàn thành",
        })

    except Exception as e:
        logger.error(f"Confirm tasks error: {e}")
        return _err(str(e))


@router.get(
    "/confirm-page/{token}",
    summary="Trang xac nhan tasks (HTML)",
    description="Trang HTML tu chua de IT/Manager xac nhan tasks. "
                "Dung khi khong co frontend rieng.",
    response_class=HTMLResponse,
)
async def confirm_page(token: str):
    """GET /api/tasks/confirm-page/{token} — trang HTML xac nhan."""
    payload = verify_token(token)
    if not payload:
        return HTMLResponse(content=_error_html("Link đã hết hạn hoặc không hợp lệ"), status_code=400)

    team = payload.get("team", "")
    employee_id = payload.get("emp_id", "")

    try:
        supabase = get_supabase()

        # Lấy employee info
        emp_result = (
            supabase.table("employees")
            .select("full_name, role, department, start_date")
            .eq("id", employee_id)
            .limit(1)
            .execute()
        )
        employee = emp_result.data[0] if emp_result.data else {}

        # Lấy tasks
        token_type = payload.get("type")
        if token_type == "task_confirm":
            tasks_result = (
                supabase.table("stakeholder_tasks")
                .select("id, title, description, status, deadline")
                .eq("id", payload["sub"])
                .execute()
            )
        else:
            tasks_result = (
                supabase.table("stakeholder_tasks")
                .select("id, title, description, status, deadline")
                .eq("plan_id", payload["sub"])
                .eq("assigned_to_team", team)
                .execute()
            )

        tasks = tasks_result.data or []

        team_labels = {"it": "IT", "admin": "Admin", "manager": "Quản lý"}
        team_label = team_labels.get(team, team.upper())

        return HTMLResponse(content=_confirm_html(
            team_label=team_label,
            employee=employee,
            tasks=tasks,
            token=token,
        ))

    except Exception as e:
        logger.error(f"Confirm page error: {e}")
        return HTMLResponse(content=_error_html(str(e)), status_code=500)


# ─── HTML Templates ───


def _confirm_html(team_label: str, employee: dict, tasks: list, token: str) -> str:
    """Build HTML page cho task confirmation."""
    pending_tasks = [t for t in tasks if t["status"] == "pending"]
    completed_tasks = [t for t in tasks if t["status"] == "completed"]

    task_checkboxes = ""
    for task in pending_tasks:
        deadline = task.get("deadline", "N/A")
        desc = f'<span class="desc">{task.get("description", "")}</span>' if task.get("description") else ""
        task_checkboxes += f"""
        <label class="task-item">
            <input type="checkbox" name="task_ids" value="{task['id']}" checked>
            <div class="task-content">
                <span class="task-title">{task['title']}</span>
                {desc}
                <span class="deadline">Hạn: {deadline}</span>
            </div>
        </label>
        """

    completed_html = ""
    if completed_tasks:
        completed_html = '<div class="completed-section"><h3>✅ Đã hoàn thành</h3>'
        for task in completed_tasks:
            completed_html += f'<div class="task-done">✓ {task["title"]}</div>'
        completed_html += '</div>'

    return f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>Xác nhận công việc — {team_label}</title>
        <style>
            * {{ margin:0; padding:0; box-sizing:border-box; }}
            body {{ font-family:'Segoe UI',system-ui,sans-serif; background:#f0f2f5; min-height:100vh;
                   display:flex; justify-content:center; padding:20px; }}
            .container {{ max-width:600px; width:100%; }}
            .header {{ background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                       padding:28px 32px; border-radius:16px 16px 0 0; color:#fff; }}
            .header h1 {{ font-size:22px; margin-bottom:4px; }}
            .header p {{ opacity:0.85; font-size:14px; }}
            .card {{ background:#fff; border-radius:0 0 16px 16px; padding:24px 32px;
                     box-shadow:0 4px 24px rgba(0,0,0,0.08); }}
            .emp-info {{ background:#f8fafc; border-left:4px solid #667eea; padding:16px 20px;
                         margin:16px 0; border-radius:0 8px 8px 0; }}
            .emp-info table td {{ padding:3px 12px 3px 0; font-size:14px; }}
            .emp-info .label {{ color:#666; }}
            h3 {{ color:#333; margin:20px 0 12px; font-size:16px; }}
            .task-item {{ display:flex; align-items:flex-start; gap:12px; padding:12px 16px;
                          border:1px solid #e5e7eb; border-radius:10px; margin-bottom:8px;
                          cursor:pointer; transition:all 0.2s; }}
            .task-item:hover {{ border-color:#667eea; background:#f8f9ff; }}
            .task-item input {{ margin-top:4px; width:18px; height:18px; accent-color:#667eea; }}
            .task-content {{ flex:1; }}
            .task-title {{ font-weight:600; font-size:14px; display:block; }}
            .desc {{ color:#666; font-size:13px; display:block; margin-top:2px; }}
            .deadline {{ color:#999; font-size:12px; display:block; margin-top:4px; }}
            .completed-section {{ margin-top:20px; opacity:0.7; }}
            .task-done {{ padding:8px 16px; color:#16a34a; font-size:14px; }}
            .name-input {{ width:100%; padding:10px 14px; border:1px solid #d1d5db;
                           border-radius:8px; font-size:14px; margin:8px 0 20px; }}
            .name-input:focus {{ outline:none; border-color:#667eea; box-shadow:0 0 0 3px rgba(102,126,234,0.15); }}
            .btn {{ background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); color:#fff;
                    border:none; padding:14px 36px; border-radius:10px; font-size:16px;
                    font-weight:600; cursor:pointer; width:100%; transition:all 0.2s;
                    box-shadow:0 4px 12px rgba(102,126,234,0.3); }}
            .btn:hover {{ transform:translateY(-1px); box-shadow:0 6px 20px rgba(102,126,234,0.4); }}
            .btn:disabled {{ opacity:0.5; cursor:not-allowed; transform:none; }}
            .success {{ text-align:center; padding:40px; }}
            .success .icon {{ font-size:48px; margin-bottom:16px; }}
            .success h2 {{ color:#16a34a; margin-bottom:8px; }}
            .footer {{ text-align:center; margin-top:16px; color:#999; font-size:12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏢 AI Onboarding System</h1>
                <p>Xác nhận công việc — Team {team_label}</p>
            </div>
            <div class="card" id="formCard">
                <div class="emp-info">
                    <table>
                        <tr><td class="label">Nhân viên:</td><td><strong>{employee.get('full_name', 'N/A')}</strong></td></tr>
                        <tr><td class="label">Vị trí:</td><td>{employee.get('role', 'N/A')}</td></tr>
                        <tr><td class="label">Phòng:</td><td>{employee.get('department', 'N/A')}</td></tr>
                        <tr><td class="label">Ngày bắt đầu:</td><td><strong>{employee.get('start_date', 'N/A')}</strong></td></tr>
                    </table>
                </div>

                {'<h3>📋 Công việc cần hoàn thành (' + str(len(pending_tasks)) + ')</h3>' if pending_tasks else ''}

                <form id="confirmForm">
                    {task_checkboxes}

                    {completed_html}

                    {'<div style="margin-top:20px">' if pending_tasks else '<div style="margin-top:20px;display:none">'}
                        <label style="font-size:14px;color:#666">Người xác nhận:</label>
                        <input type="text" class="name-input" id="completedBy"
                               placeholder="Nhập tên của bạn (không bắt buộc)">

                        <button type="submit" class="btn" id="submitBtn">
                            ✅ Xác nhận hoàn thành
                        </button>
                    </div>
                </form>

                {"" if pending_tasks else '<div class="success"><div class="icon">🎉</div><h2>Tất cả công việc đã hoàn thành!</h2><p>Cảm ơn bạn đã hỗ trợ.</p></div>'}
            </div>
            <p class="footer">Email tự động bởi AI Onboarding System</p>
        </div>

        <script>
            const form = document.getElementById('confirmForm');
            const btn = document.getElementById('submitBtn');

            form?.addEventListener('submit', async (e) => {{
                e.preventDefault();
                btn.disabled = true;
                btn.textContent = '⏳ Đang xử lý...';

                const checkboxes = form.querySelectorAll('input[name="task_ids"]:checked');
                const taskIds = Array.from(checkboxes).map(cb => cb.value);
                const completedBy = document.getElementById('completedBy')?.value || '';

                try {{
                    const res = await fetch('/api/tasks/confirm/{token}', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ task_ids: taskIds, completed_by: completedBy }})
                    }});
                    const data = await res.json();

                    if (data.success) {{
                        document.getElementById('formCard').innerHTML = `
                            <div class="success">
                                <div class="icon">🎉</div>
                                <h2>Xác nhận thành công!</h2>
                                <p>${{data.data.confirmed_count}} công việc đã được đánh dấu hoàn thành.</p>
                                <p style="color:#666;margin-top:12px">Cảm ơn bạn đã hỗ trợ onboarding!</p>
                            </div>
                        `;
                    }} else {{
                        alert('Lỗi: ' + (data.error || 'Không xác định'));
                        btn.disabled = false;
                        btn.textContent = '✅ Xác nhận hoàn thành';
                    }}
                }} catch (err) {{
                    alert('Lỗi kết nối: ' + err.message);
                    btn.disabled = false;
                    btn.textContent = '✅ Xác nhận hoàn thành';
                }}
            }});
        </script>
    </body>
    </html>
    """


def _error_html(message: str) -> str:
    """Build HTML page cho error."""
    return f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>Link không hợp lệ</title>
        <style>
            body {{ font-family:'Segoe UI',sans-serif; background:#f0f2f5; display:flex;
                   justify-content:center; align-items:center; min-height:100vh; }}
            .card {{ background:#fff; border-radius:16px; padding:40px; max-width:400px;
                     text-align:center; box-shadow:0 4px 24px rgba(0,0,0,0.08); }}
            .icon {{ font-size:48px; margin-bottom:16px; }}
            h2 {{ color:#dc2626; margin-bottom:8px; }}
            p {{ color:#666; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">⚠️</div>
            <h2>Link không hợp lệ</h2>
            <p>{message}</p>
            <p style="margin-top:12px;font-size:13px;color:#999">
                Vui lòng liên hệ HR để nhận link mới.
            </p>
        </div>
    </body>
    </html>
    """
