"""
Email Service — Gửi email thông báo cho stakeholder tasks.

Hỗ trợ 2 provider:
- "resend": Gửi email thật qua Resend API (production)
- "console": In email ra console log (development/testing)

Email templates:
- Stakeholder task notification (IT/Admin/Manager nhận tasks cho NV mới)
- Reminder (task quá hạn)
"""

import logging
from datetime import datetime

import httpx

from src.config import (
    EMAIL_PROVIDER,
    RESEND_API_KEY,
    EMAIL_FROM,
    EMAIL_FROM_NAME,
)

logger = logging.getLogger(__name__)


# ─── Email Sending ───


async def send_email(
    to: str | list[str],
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> dict:
    """
    Gửi email qua provider đã cấu hình.

    Args:
        to: Email address(es) người nhận
        subject: Tiêu đề email
        html_body: Nội dung HTML
        text_body: Nội dung text thuần (fallback)

    Returns:
        dict với success, provider, message_id (nếu có)
    """
    if isinstance(to, str):
        to = [to]

    if EMAIL_PROVIDER == "resend":
        return await _send_via_resend(to, subject, html_body, text_body)
    else:
        return _send_via_console(to, subject, html_body, text_body)


async def _send_via_resend(
    to: list[str],
    subject: str,
    html_body: str,
    text_body: str | None,
) -> dict:
    """Gửi email qua Resend API."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — falling back to console")
        return _send_via_console(to, subject, html_body, text_body)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": f"{EMAIL_FROM_NAME} <{EMAIL_FROM}>",
                    "to": to,
                    "subject": subject,
                    "html": html_body,
                    "text": text_body or "",
                },
            )

        if response.status_code in (200, 201):
            data = response.json()
            logger.info(f"Email sent via Resend: {subject} → {to}")
            return {
                "success": True,
                "provider": "resend",
                "message_id": data.get("id"),
            }
        else:
            logger.error(f"Resend API error: {response.status_code} {response.text}")
            return {
                "success": False,
                "provider": "resend",
                "error": f"HTTP {response.status_code}: {response.text[:200]}",
            }

    except Exception as e:
        logger.error(f"Resend send error: {e}")
        return {"success": False, "provider": "resend", "error": str(e)}


def _send_via_console(
    to: list[str],
    subject: str,
    html_body: str,
    text_body: str | None,
) -> dict:
    """Log email ra console (development mode)."""
    logger.info(
        f"\n{'='*60}\n"
        f"📧 EMAIL (console mode)\n"
        f"{'='*60}\n"
        f"From: {EMAIL_FROM_NAME} <{EMAIL_FROM}>\n"
        f"To: {', '.join(to)}\n"
        f"Subject: {subject}\n"
        f"{'─'*60}\n"
        f"{text_body or '(HTML only)'}\n"
        f"{'='*60}\n"
    )
    return {"success": True, "provider": "console", "message_id": None}


# ─── Email Templates ───


def build_stakeholder_email(
    team: str,
    employee_name: str,
    employee_role: str,
    employee_department: str,
    start_date: str,
    tasks: list[dict],
    confirm_url: str,
) -> tuple[str, str, str]:
    """
    Build email cho stakeholder team (IT/Admin/Manager).

    Returns:
        (subject, html_body, text_body)
    """
    team_labels = {
        "it": "IT",
        "admin": "Admin/HR",
        "manager": "Quản lý trực tiếp",
    }
    team_label = team_labels.get(team, team.upper())

    # Task list
    task_list_html = ""
    task_list_text = ""
    for i, task in enumerate(tasks, 1):
        deadline = task.get("deadline", task.get("deadline_date", "N/A"))
        task_list_html += (
            f'<tr>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #eee">{i}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #eee"><strong>{task["title"]}</strong>'
        )
        if task.get("description"):
            task_list_html += f'<br><span style="color:#666;font-size:13px">{task["description"]}</span>'
        task_list_html += (
            f'</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #eee;white-space:nowrap">{deadline}</td>'
            f'</tr>'
        )
        task_list_text += f"  {i}. {task['title']} (hạn: {deadline})\n"

    subject = f"[Onboarding] Chuẩn bị cho {employee_name} — {team_label} {employee_department}"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#333">

    <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:24px 32px;border-radius:12px 12px 0 0">
        <h1 style="margin:0;color:#fff;font-size:20px">🏢 AI Onboarding System</h1>
        <p style="margin:8px 0 0;color:rgba(255,255,255,0.85);font-size:14px">Thông báo công việc chuẩn bị cho nhân viên mới</p>
    </div>

    <div style="background:#fff;border:1px solid #e5e7eb;border-top:none;padding:24px 32px;border-radius:0 0 12px 12px">

        <p>Xin chào team <strong>{team_label}</strong>,</p>

        <p>Nhân viên mới sẽ bắt đầu làm việc:</p>

        <div style="background:#f8fafc;border-left:4px solid #667eea;padding:16px 20px;margin:16px 0;border-radius:0 8px 8px 0">
            <table style="border:none;border-collapse:collapse">
                <tr><td style="padding:4px 16px 4px 0;color:#666">Tên:</td><td><strong>{employee_name}</strong></td></tr>
                <tr><td style="padding:4px 16px 4px 0;color:#666">Vị trí:</td><td>{employee_role}</td></tr>
                <tr><td style="padding:4px 16px 4px 0;color:#666">Phòng:</td><td>{employee_department}</td></tr>
                <tr><td style="padding:4px 16px 4px 0;color:#666">Ngày bắt đầu:</td><td><strong>{start_date}</strong></td></tr>
            </table>
        </div>

        <h3 style="color:#333;margin:24px 0 12px">📋 Công việc cần hoàn thành ({len(tasks)} tasks):</h3>

        <table style="width:100%;border-collapse:collapse;font-size:14px">
            <thead>
                <tr style="background:#f1f5f9">
                    <th style="padding:10px 12px;text-align:left;width:30px">#</th>
                    <th style="padding:10px 12px;text-align:left">Công việc</th>
                    <th style="padding:10px 12px;text-align:left;width:100px">Hạn</th>
                </tr>
            </thead>
            <tbody>
                {task_list_html}
            </tbody>
        </table>

        <div style="text-align:center;margin:32px 0 16px">
            <a href="{confirm_url}"
               style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                      color:#fff;padding:14px 36px;border-radius:8px;
                      text-decoration:none;font-weight:600;font-size:16px;
                      display:inline-block;box-shadow:0 4px 12px rgba(102,126,234,0.4)">
                ✅ Xác nhận hoàn thành
            </a>
        </div>

        <p style="color:#999;font-size:12px;text-align:center">
            Link này có hiệu lực trong 7 ngày. Không cần đăng nhập.
        </p>

    </div>

    <p style="color:#999;font-size:11px;text-align:center;margin-top:16px">
        Email này được gửi tự động bởi AI Onboarding System.<br>
        Nếu bạn không liên quan, vui lòng bỏ qua email này.
    </p>

    </body>
    </html>
    """

    text_body = (
        f"AI Onboarding System — Thông báo công việc\n"
        f"{'='*50}\n\n"
        f"Xin chào team {team_label},\n\n"
        f"Nhân viên mới sẽ bắt đầu làm việc:\n"
        f"  Tên: {employee_name}\n"
        f"  Vị trí: {employee_role}\n"
        f"  Phòng: {employee_department}\n"
        f"  Ngày bắt đầu: {start_date}\n\n"
        f"Công việc cần hoàn thành ({len(tasks)} tasks):\n"
        f"{task_list_text}\n"
        f"Xác nhận hoàn thành: {confirm_url}\n"
        f"(Link có hiệu lực 7 ngày, không cần đăng nhập)\n"
    )

    return subject, html_body, text_body


# ─── Stakeholder Email Recipients ───

# Default email addresses cho từng team
# Trong production, nên lấy từ DB hoặc config
TEAM_EMAILS: dict[str, str] = {
    "it": "it-admin@company.com",
    "admin": "hr-admin@company.com",
    "manager": "",  # Lấy từ employee.manager_id → email
}


def get_team_email(team: str, manager_email: str | None = None) -> str | None:
    """Lấy email address cho 1 team."""
    if team == "manager" and manager_email:
        return manager_email
    return TEAM_EMAILS.get(team) or None
