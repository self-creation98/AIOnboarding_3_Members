"""
Stakeholder Notifier — Orchestrator gửi email cho IT/Admin/Manager.

Flow:
    notify_stakeholders(plan_id, employee_info)
      → Query stakeholder_tasks grouped by team
      → Với mỗi team: generate magic link token → build email → send
      → Log kết quả

Usage:
    from src.backend.services.stakeholder_notifier import notify_stakeholders
    await notify_stakeholders(plan_id, employee_info)

Gọi tại 2 nơi:
    1. checklist.py: approve_plan() — HR duyệt plan
    2. webhooks.py: webhook_new_employee() — HRIS auto-create
"""

import logging
from datetime import datetime

from src.backend.database import get_supabase
from src.backend.services.magic_link import generate_team_token, build_confirm_url
from src.backend.services.email_service import (
    send_email,
    build_stakeholder_email,
    get_team_email,
)

logger = logging.getLogger(__name__)


async def notify_stakeholders(
    plan_id: str,
    employee_info: dict,
) -> dict:
    """
    Gửi email thông báo cho tất cả stakeholder teams có tasks trong plan.

    Args:
        plan_id: ID của onboarding plan đã được duyệt
        employee_info: Dict chứa:
            - id: employee UUID
            - full_name: tên NV
            - role: vị trí
            - department: phòng ban
            - start_date: ngày bắt đầu
            - manager_id: UUID manager (optional)

    Returns:
        dict với kết quả gửi email cho từng team
    """
    employee_id = employee_info.get("id", "")
    results = {}

    try:
        supabase = get_supabase()

        # Lấy tất cả stakeholder tasks grouped by team
        tasks_result = (
            supabase.table("stakeholder_tasks")
            .select("id, title, description, assigned_to_team, deadline, status")
            .eq("plan_id", plan_id)
            .eq("status", "pending")
            .order("deadline")
            .execute()
        )

        all_tasks = tasks_result.data or []

        if not all_tasks:
            logger.info(f"No pending stakeholder tasks for plan {plan_id}")
            return {"emails_sent": 0, "reason": "no_pending_tasks"}

        # Group tasks by team
        tasks_by_team: dict[str, list[dict]] = {}
        for task in all_tasks:
            team = task["assigned_to_team"]
            if team not in tasks_by_team:
                tasks_by_team[team] = []
            tasks_by_team[team].append(task)

        # Lấy manager email nếu có manager tasks
        manager_email = None
        if "manager" in tasks_by_team and employee_info.get("manager_id"):
            mgr_result = (
                supabase.table("employees")
                .select("email")
                .eq("id", employee_info["manager_id"])
                .limit(1)
                .execute()
            )
            if mgr_result.data:
                manager_email = mgr_result.data[0].get("email")

        # Gửi email cho từng team
        emails_sent = 0

        for team, tasks in tasks_by_team.items():
            # Get recipient email
            recipient = get_team_email(team, manager_email)

            if not recipient:
                logger.warning(f"No email address for team '{team}' — skipping")
                results[team] = {"sent": False, "reason": "no_email_address"}
                continue

            # Generate magic link token (team-level)
            token = generate_team_token(
                plan_id=plan_id,
                team=team,
                employee_id=employee_id,
            )
            confirm_url = build_confirm_url(token)

            # Build email
            subject, html_body, text_body = build_stakeholder_email(
                team=team,
                employee_name=employee_info.get("full_name", "N/A"),
                employee_role=employee_info.get("role", "N/A"),
                employee_department=employee_info.get("department", "N/A"),
                start_date=str(employee_info.get("start_date", "N/A")),
                tasks=tasks,
                confirm_url=confirm_url,
            )

            # Send email
            send_result = await send_email(
                to=recipient,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )

            results[team] = {
                "sent": send_result.get("success", False),
                "recipient": recipient,
                "tasks_count": len(tasks),
                "provider": send_result.get("provider"),
                "confirm_url": confirm_url,
            }

            if send_result.get("success"):
                emails_sent += 1

            # Log vào DB
            try:
                supabase.table("webhook_logs").insert({
                    "direction": "out",
                    "event_type": f"email.stakeholder.{team}",
                    "endpoint_url": f"mailto:{recipient}",
                    "request_body": {
                        "plan_id": plan_id,
                        "employee_id": employee_id,
                        "team": team,
                        "tasks_count": len(tasks),
                        "subject": subject,
                    },
                    "response_status": 200 if send_result.get("success") else 500,
                    "success": send_result.get("success", False),
                    "error_message": send_result.get("error"),
                }).execute()
            except Exception as log_err:
                logger.warning(f"Failed to log email send: {log_err}")

        results["emails_sent"] = emails_sent
        results["teams_notified"] = list(tasks_by_team.keys())

        logger.info(
            f"Stakeholder notification: plan={plan_id}, "
            f"emails_sent={emails_sent}/{len(tasks_by_team)}"
        )

        return results

    except Exception as e:
        logger.error(f"Stakeholder notifier error: {e}")
        return {"emails_sent": 0, "error": str(e)}
