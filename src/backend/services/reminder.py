"""
Reminder Service — Logic nhắc nhở 3 tầng cho checklist items quá hạn.

Escalation tiers:
- Tier 1 (< 48h overdue): Nhắc nhân viên
- Tier 2 (48-72h overdue): Nhắc Manager
- Tier 3 (>= 72h overdue): Alert HR + set health_score = 'red'

Usage:
    from src.backend.services.reminder import run_daily_reminders
    result = await run_daily_reminders(supabase)
"""

import logging
from datetime import datetime, date, timedelta

from src.backend.services.event_dispatcher import fire_event

logger = logging.getLogger(__name__)


async def run_daily_reminders(supabase) -> dict:
    """
    Chạy mỗi ngày 1 lần (gọi bằng API hoặc cron).
    Check tất cả checklist items overdue → gửi reminder theo 3 tầng.

    Returns:
        dict với số lượng reminders đã gửi theo tier.
    """
    today = date.today()
    now = datetime.now()

    # ─── 1. Lấy checklist_items overdue ───

    items_result = (
        supabase.table("checklist_items")
        .select(
            "id, title, deadline_date, status, employee_id, plan_id, owner"
        )
        .in_("status", ["chua_bat_dau", "dang_lam"])
        .lt("deadline_date", today.isoformat())
        .execute()
    )

    overdue_items = items_result.data or []

    if not overdue_items:
        return {
            "reminders_sent": 0,
            "tier1_employee": 0,
            "tier2_manager": 0,
            "tier3_hr": 0,
            "skipped_already_reminded": 0,
            "date": str(today),
        }

    # Lọc chỉ giữ items thuộc plan đang active (da_duyet hoặc dang_thuc_hien)
    plan_ids = list({item["plan_id"] for item in overdue_items if item.get("plan_id")})
    if plan_ids:
        plans_result = (
            supabase.table("onboarding_plans")
            .select("id, status")
            .in_("id", plan_ids)
            .in_("status", ["da_duyet", "dang_thuc_hien"])
            .execute()
        )
        active_plan_ids = {p["id"] for p in (plans_result.data or [])}
        overdue_items = [item for item in overdue_items if item.get("plan_id") in active_plan_ids]

    if not overdue_items:
        return {
            "reminders_sent": 0,
            "tier1_employee": 0,
            "tier2_manager": 0,
            "tier3_hr": 0,
            "skipped_already_reminded": 0,
            "date": str(today),
        }

    # ─── 2. Lấy employees info ───

    emp_ids = list({item["employee_id"] for item in overdue_items if item.get("employee_id")})
    emp_result = (
        supabase.table("employees")
        .select("id, full_name, email, manager_id")
        .in_("id", emp_ids)
        .execute()
    )
    emp_map = {e["id"]: e for e in (emp_result.data or [])}

    # ─── 3. Check reminders đã gửi hôm nay ───

    today_start = datetime.combine(today, datetime.min.time()).isoformat()
    today_end = datetime.combine(today, datetime.max.time()).isoformat()

    logs_result = (
        supabase.table("reminder_logs")
        .select("employee_id")
        .gte("sent_at", today_start)
        .lte("sent_at", today_end)
        .execute()
    )
    already_reminded_today = {log["employee_id"] for log in (logs_result.data or [])}

    # ─── 4. Loop và gửi reminders ───

    tier1 = 0
    tier2 = 0
    tier3 = 0
    skipped = 0

    for item in overdue_items:
        employee_id = item.get("employee_id")
        employee = emp_map.get(employee_id, {})
        item_owner = item.get("owner", "new_hire")

        if not employee:
            continue

        # Mỗi NV chỉ nhận MAX 1 reminder/ngày
        if employee_id in already_reminded_today:
            skipped += 1
            continue

        # Tính overdue hours
        try:
            deadline = date.fromisoformat(str(item["deadline_date"]))
            overdue_hours = (now - datetime.combine(deadline, datetime.min.time())).total_seconds() / 3600
        except (ValueError, TypeError):
            continue

        overdue_days = int(overdue_hours / 24)

        # ─── Bug #3 fix: Route reminder theo owner ───
        # Task owner = 'it'/'admin'/'manager' → gửi cho team đó, KHÔNG gửi cho NV
        if item_owner in ("it", "admin", "manager") and overdue_hours < 72:
            # Gửi trực tiếp cho team phụ trách
            sent_to = f"{item_owner}_admin"
            message = (
                f"📋 Task '{item['title']}' cho NV {employee['full_name']} "
                f"đã quá hạn {overdue_days} ngày. Vui lòng xử lý."
            )
            supabase.table("reminder_logs").insert({
                "checklist_item_id": item["id"],
                "employee_id": employee_id,
                "escalation_tier": 1,
                "sent_to": sent_to,
                "sent_to_role": item_owner,
                "message": message,
                "channel": "system",
                "sent_at": now.isoformat(),
            }).execute()
            # TODO: Gửi Slack cho channel tương ứng
            tier1 += 1

        elif overdue_hours < 48:
            # ─── Tier 1: Nhắc nhân viên (chỉ cho owner = new_hire) ───
            message = (
                f"⏰ Nhắc nhở: '{item['title']}' đã đến hạn. "
                f"Deadline: {item['deadline_date']}. Vui lòng hoàn thành sớm."
            )
            supabase.table("reminder_logs").insert({
                "checklist_item_id": item["id"],
                "employee_id": employee_id,
                "escalation_tier": 1,
                "sent_to": employee.get("email", ""),
                "sent_to_role": "employee",
                "message": message,
                "channel": "system",
                "sent_at": now.isoformat(),
            }).execute()
            # TODO: Gửi Slack DM cho NV
            tier1 += 1

        elif overdue_hours < 72:
            # ─── Tier 2: Nhắc Manager ───
            manager_id = employee.get("manager_id")

            if manager_id:
                mgr_result = (
                    supabase.table("employees")
                    .select("email, full_name")
                    .eq("id", manager_id)
                    .limit(1)
                    .execute()
                )
                manager = mgr_result.data[0] if mgr_result.data else {}
                manager_email = manager.get("email", "manager")

                message = (
                    f"📋 {employee['full_name']} chưa hoàn thành "
                    f"'{item['title']}' (quá hạn {overdue_days} ngày). "
                    f"Vui lòng hỗ trợ."
                )
                supabase.table("reminder_logs").insert({
                    "checklist_item_id": item["id"],
                    "employee_id": employee_id,
                    "escalation_tier": 2,
                    "sent_to": manager_email,
                    "sent_to_role": "manager",
                    "message": message,
                    "channel": "system",
                    "sent_at": now.isoformat(),
                }).execute()
                # TODO: Gửi Slack DM cho manager
                tier2 += 1
            else:
                # Không có manager → escalate lên HR luôn
                message = (
                    f"🚨 Cần xử lý: {employee['full_name']} bị kẹt tại "
                    f"'{item['title']}' (quá hạn {overdue_days} ngày). "
                    f"Không có manager assigned."
                )
                supabase.table("reminder_logs").insert({
                    "checklist_item_id": item["id"],
                    "employee_id": employee_id,
                    "escalation_tier": 3,
                    "sent_to": "hr_admin",
                    "sent_to_role": "hr",
                    "message": message,
                    "channel": "system",
                    "sent_at": now.isoformat(),
                }).execute()

                # Bug #7 fix: chỉ update nếu chưa red
                if employee.get("health_score") != "red":
                    supabase.table("employees").update({
                        "health_score": "red",
                        "updated_at": now.isoformat(),
                    }).eq("id", employee_id).execute()

                    # Fire outgoing webhook: risk detected
                    await fire_event("employee.risk.detected", {
                        "employee_id": employee_id,
                        "employee_name": employee.get("full_name"),
                        "health_score": "red",
                        "trigger": "reminder_tier3_no_manager",
                    })

                # Fire outgoing webhook: task overdue (tier 3)
                await fire_event("employee.task.overdue", {
                    "employee_id": employee_id,
                    "employee_name": employee.get("full_name"),
                    "task_title": item["title"],
                    "overdue_days": overdue_days,
                    "escalation_tier": 3,
                })

                tier3 += 1

        else:
            # ─── Tier 3: Alert HR ───
            message = (
                f"🚨 Cần xử lý: {employee['full_name']} bị kẹt tại "
                f"'{item['title']}' (quá hạn {overdue_days} ngày)."
            )
            supabase.table("reminder_logs").insert({
                "checklist_item_id": item["id"],
                "employee_id": employee_id,
                "escalation_tier": 3,
                "sent_to": "hr_admin",
                "sent_to_role": "hr",
                "message": message,
                "channel": "system",
                "sent_at": now.isoformat(),
            }).execute()

            # Bug #7 fix: chỉ update nếu chưa red
            if employee.get("health_score") != "red":
                supabase.table("employees").update({
                    "health_score": "red",
                    "updated_at": now.isoformat(),
                }).eq("id", employee_id).execute()

                # Fire outgoing webhook: risk detected
                await fire_event("employee.risk.detected", {
                    "employee_id": employee_id,
                    "employee_name": employee.get("full_name"),
                    "health_score": "red",
                    "trigger": "reminder_tier3",
                })

            # Fire outgoing webhook: task overdue (tier 3)
            await fire_event("employee.task.overdue", {
                "employee_id": employee_id,
                "employee_name": employee.get("full_name"),
                "task_title": item["title"],
                "overdue_days": overdue_days,
                "escalation_tier": 3,
            })

            tier3 += 1

        # Đánh dấu employee đã nhận reminder hôm nay
        already_reminded_today.add(employee_id)

    return {
        "reminders_sent": tier1 + tier2 + tier3,
        "tier1_employee": tier1,
        "tier2_manager": tier2,
        "tier3_hr": tier3,
        "skipped_already_reminded": skipped,
        "date": str(today),
    }
