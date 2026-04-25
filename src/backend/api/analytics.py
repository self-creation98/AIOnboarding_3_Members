"""
Analytics API — Endpoints cho HR dashboard, bottleneck detection, copilot.

Endpoints:
- GET  /api/analytics/overview               — Tổng quan HR dashboard
- GET  /api/analytics/bottlenecks            — Phát hiện bottleneck
- GET  /api/analytics/content-gaps           — Content gap detection
- GET  /api/analytics/chatbot-stats          — Thống kê chatbot
- GET  /api/analytics/employee/{employee_id} — Tổng hợp data 1 NV
- POST /api/analytics/copilot               — AI Copilot tóm tắt (rule-based)
- POST /api/analytics/recalculate-health     — Tính lại health_score
"""

import logging
from datetime import datetime, date, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.backend.database import get_supabase
from src.backend.api.deps import get_current_active_user
from src.backend.schemas import UserInfo
from src.backend.services.event_dispatcher import fire_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


# ─── Schemas ───

class CopilotRequest(BaseModel):
    employee_id: str = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])

class RecalcRequest(BaseModel):
    pass  # No body needed


# ─── Helpers ───

def _ok(data):
    return {"success": True, "data": data}

def _err(msg: str, status_code: int = 400):
    return {"success": False, "error": msg}


# ─── Endpoints ───


@router.get("/overview", summary="Tong quan HR dashboard")
async def overview(current_user: UserInfo = Depends(get_current_active_user)):
    """GET /api/analytics/overview"""
    try:
        supabase = get_supabase()
        today = date.today()
        month_start = today.replace(day=1)

        # total onboarding
        emp_res = (supabase.table("employees")
            .select("id, health_score, onboarding_status, updated_at")
            .in_("onboarding_status", ["pre_boarding", "in_progress"])
            .execute())
        active_emps = emp_res.data or []
        total_onboarding = len(active_emps)

        # health distribution
        health_dist = {"green": 0, "yellow": 0, "red": 0}
        for e in active_emps:
            h = e.get("health_score", "green")
            if h in health_dist:
                health_dist[h] += 1
        at_risk_count = health_dist["red"]

        # avg completion
        plans_res = (supabase.table("onboarding_plans")
            .select("completion_percentage")
            .in_("status", ["da_duyet", "dang_thuc_hien"])
            .execute())
        plans = plans_res.data or []
        avg_completion = round(sum(p["completion_percentage"] for p in plans) / len(plans), 1) if plans else 0

        # overdue
        overdue_res = (supabase.table("checklist_items")
            .select("employee_id")
            .in_("status", ["chua_bat_dau", "dang_lam"])
            .lt("deadline_date", today.isoformat())
            .execute())
        overdue_emp_ids = {i["employee_id"] for i in (overdue_res.data or [])}
        overdue_count = len(overdue_emp_ids)

        # completed this month
        comp_res = (supabase.table("employees")
            .select("id")
            .eq("onboarding_status", "completed")
            .gte("updated_at", month_start.isoformat())
            .execute())
        completed_this_month = len(comp_res.data or [])

        return _ok({
            "total_onboarding": total_onboarding,
            "avg_completion": avg_completion,
            "overdue_count": overdue_count,
            "at_risk_count": at_risk_count,
            "completed_this_month": completed_this_month,
            "health_distribution": health_dist,
        })
    except Exception as e:
        logger.error(f"Overview error: {e}")
        return _err(str(e))


@router.get("/bottlenecks", summary="Phat hien bottleneck")
async def bottlenecks(
    min_affected: int = Query(default=2),
    department: str | None = Query(default=None),
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/analytics/bottlenecks"""
    try:
        supabase = get_supabase()
        today = date.today()

        # Get active plan IDs
        plans_res = (supabase.table("onboarding_plans")
            .select("id").in_("status", ["da_duyet", "dang_thuc_hien"]).execute())
        active_plan_ids = [p["id"] for p in (plans_res.data or [])]
        if not active_plan_ids:
            return _ok([])

        # Get overdue items in active plans
        query = (supabase.table("checklist_items")
            .select("title, category, owner, employee_id, deadline_date")
            .in_("status", ["chua_bat_dau", "dang_lam"])
            .lt("deadline_date", today.isoformat())
            .in_("plan_id", active_plan_ids))
        items_res = query.execute()
        items = items_res.data or []

        # Filter by department if provided
        if department and items:
            emp_ids = list({i["employee_id"] for i in items})
            emp_res = (supabase.table("employees").select("id")
                .in_("id", emp_ids).eq("department", department).execute())
            dept_emp_ids = {e["id"] for e in (emp_res.data or [])}
            items = [i for i in items if i["employee_id"] in dept_emp_ids]

        # Group by title
        groups = {}
        for item in items:
            key = item["title"]
            if key not in groups:
                groups[key] = {"title": key, "category": item["category"],
                    "owner": item["owner"], "employees": set(), "overdue_days": []}
            groups[key]["employees"].add(item["employee_id"])
            try:
                dd = date.fromisoformat(str(item["deadline_date"]))
                groups[key]["overdue_days"].append((today - dd).days)
            except (ValueError, TypeError):
                pass

        result = []
        for g in groups.values():
            affected = len(g["employees"])
            if affected >= min_affected:
                avg_days = round(sum(g["overdue_days"]) / len(g["overdue_days"]), 1) if g["overdue_days"] else 0
                result.append({
                    "task_name": g["title"], "category": g["category"],
                    "owner": g["owner"], "affected_employees": affected,
                    "avg_overdue_days": avg_days,
                })
        result.sort(key=lambda x: x["affected_employees"], reverse=True)
        return _ok(result)
    except Exception as e:
        logger.error(f"Bottlenecks error: {e}")
        return _err(str(e))


@router.get("/content-gaps", summary="Content gap detection")
async def content_gaps(current_user: UserInfo = Depends(get_current_active_user)):
    """GET /api/analytics/content-gaps"""
    try:
        supabase = get_supabase()

        # Check clustered
        clustered_res = (supabase.table("unanswered_questions")
            .select("topic_cluster, question_text")
            .neq("topic_cluster", "null")
            .execute())
        clustered = [q for q in (clustered_res.data or []) if q.get("topic_cluster")]

        total_res = (supabase.table("unanswered_questions")
            .select("id", count="exact").execute())
        total = total_res.count if total_res.count is not None else 0

        if clustered:
            clusters_map = {}
            for q in clustered:
                topic = q["topic_cluster"]
                if topic not in clusters_map:
                    clusters_map[topic] = []
                clusters_map[topic].append(q["question_text"])

            clusters = [{"topic": t, "question_count": len(qs),
                "sample_questions": qs[:5]} for t, qs in clusters_map.items()]
            clusters.sort(key=lambda x: x["question_count"], reverse=True)
            return _ok({"has_clusters": True, "clusters": clusters, "total_unanswered": total})
        else:
            raw_res = (supabase.table("unanswered_questions")
                .select("id, question_text, reason, confidence_score, created_at")
                .eq("reviewed", False)
                .order("created_at", desc=True).limit(50).execute())
            return _ok({"has_clusters": False, "questions": raw_res.data or [],
                "total_unanswered": total})
    except Exception as e:
        logger.error(f"Content gaps error: {e}")
        return _err(str(e))


@router.get("/chatbot-stats", summary="Thong ke chatbot")
async def chatbot_stats(current_user: UserInfo = Depends(get_current_active_user)):
    """GET /api/analytics/chatbot-stats"""
    try:
        supabase = get_supabase()

        conv_res = (supabase.table("chatbot_conversations")
            .select("id, escalated", count="exact").execute())
        total_conversations = conv_res.count or 0
        escalated_count = sum(1 for c in (conv_res.data or []) if c.get("escalated"))

        msg_res = (supabase.table("chatbot_messages")
            .select("id, feedback, role").execute())
        msgs = msg_res.data or []
        total_messages = sum(1 for m in msgs if m.get("role") == "user")
        positive = sum(1 for m in msgs if m.get("feedback") == "positive")
        negative = sum(1 for m in msgs if m.get("feedback") == "negative")
        sat_rate = round(positive / (positive + negative), 2) if (positive + negative) > 0 else None

        unans_res = (supabase.table("unanswered_questions")
            .select("id", count="exact").execute())
        unanswered = unans_res.count or 0

        return _ok({
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "feedback": {"positive": positive, "negative": negative,
                "satisfaction_rate": sat_rate},
            "escalated_count": escalated_count,
            "unanswered_count": unanswered,
        })
    except Exception as e:
        logger.error(f"Chatbot stats error: {e}")
        return _err(str(e))


@router.get("/employee/{employee_id}", summary="Tong hop data 1 NV")
async def employee_analytics(
    employee_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/analytics/employee/{employee_id}"""
    try:
        supabase = get_supabase()
        today = date.today()

        # Employee + plan
        emp_res = (supabase.table("employees")
            .select("id, full_name, role, department, start_date, health_score, onboarding_status")
            .eq("id", employee_id).limit(1).execute())
        if not emp_res.data:
            return _err(f"Employee {employee_id} not found")
        employee = emp_res.data[0]

        plan_res = (supabase.table("onboarding_plans")
            .select("completion_percentage, total_items, completed_items")
            .eq("employee_id", employee_id).limit(1).execute())
        plan = plan_res.data[0] if plan_res.data else {}

        # Checklist
        cl_res = (supabase.table("checklist_items")
            .select("id, status, category, deadline_date")
            .eq("employee_id", employee_id).execute())
        cl_items = cl_res.data or []
        cl_total = len(cl_items)
        cl_completed = sum(1 for i in cl_items if i["status"] == "hoan_thanh")
        cl_overdue = sum(1 for i in cl_items
            if i["status"] in ("chua_bat_dau", "dang_lam")
            and i.get("deadline_date") and str(i["deadline_date"]) < today.isoformat())

        by_cat = {}
        for i in cl_items:
            cat = i["category"]
            if cat not in by_cat:
                by_cat[cat] = {"total": 0, "completed": 0}
            by_cat[cat]["total"] += 1
            if i["status"] == "hoan_thanh":
                by_cat[cat]["completed"] += 1

        # Stakeholder tasks
        st_res = (supabase.table("stakeholder_tasks")
            .select("status").eq("employee_id", employee_id).execute())
        st_pending = sum(1 for t in (st_res.data or []) if t["status"] == "pending")
        st_completed = sum(1 for t in (st_res.data or []) if t["status"] == "completed")

        # Preboarding
        pb_res = (supabase.table("preboarding_documents")
            .select("status").eq("employee_id", employee_id).execute())
        pb_docs = pb_res.data or []
        pb_total = len(pb_docs)
        pb_uploaded = sum(1 for d in pb_docs if d["status"] in ("uploaded", "verified"))
        pb_missing = sum(1 for d in pb_docs if d["status"] == "missing")
        pb_verified = sum(1 for d in pb_docs if d["status"] == "verified")

        # Chat
        chat_res = (supabase.table("chatbot_conversations")
            .select("id").eq("employee_id", employee_id).execute())
        total_conv = len(chat_res.data or [])
        conv_ids = [c["id"] for c in (chat_res.data or [])]
        total_msgs = 0
        if conv_ids:
            msg_res = (supabase.table("chatbot_messages")
                .select("id", count="exact")
                .in_("conversation_id", conv_ids).eq("role", "user").execute())
            total_msgs = msg_res.count or 0

        # Sentiment
        sent_res = (supabase.table("sentiment_logs")
            .select("sentiment, confidence, created_at")
            .eq("employee_id", employee_id)
            .order("created_at", desc=True).limit(10).execute())

        # Reminders
        rem_res = (supabase.table("reminder_logs")
            .select("escalation_tier")
            .eq("employee_id", employee_id).execute())
        rem_data = rem_res.data or []
        rem_total = len(rem_data)
        rem_t1 = sum(1 for r in rem_data if r["escalation_tier"] == 1)
        rem_t2 = sum(1 for r in rem_data if r["escalation_tier"] == 2)
        rem_t3 = sum(1 for r in rem_data if r["escalation_tier"] == 3)

        return _ok({
            "employee": employee,
            "checklist": {
                "total": cl_total, "completed": cl_completed, "overdue": cl_overdue,
                "completion_percentage": plan.get("completion_percentage", 0),
                "by_category": by_cat,
            },
            "stakeholder_tasks": {"pending": st_pending, "completed": st_completed},
            "preboarding": {"total": pb_total, "uploaded": pb_uploaded,
                "verified": pb_verified, "missing": pb_missing},
            "chat": {"total_conversations": total_conv, "total_messages": total_msgs},
            "sentiment_history": sent_res.data or [],
            "reminders": {"total": rem_total, "tier1": rem_t1, "tier2": rem_t2, "tier3": rem_t3},
        })
    except Exception as e:
        logger.error(f"Employee analytics error: {e}")
        return _err(str(e))


@router.post("/copilot", summary="AI Copilot tom tat")
async def copilot_summary(
    body: CopilotRequest,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """POST /api/analytics/copilot — rule-based copilot (TODO: noi AI)."""
    try:
        supabase = get_supabase()
        today = date.today()
        eid = body.employee_id

        # Employee
        emp_res = (supabase.table("employees")
            .select("id, full_name, health_score")
            .eq("id", eid).limit(1).execute())
        if not emp_res.data:
            return _err(f"Employee {eid} not found")
        employee = emp_res.data[0]

        # Overdue
        overdue_res = (supabase.table("checklist_items")
            .select("id").eq("employee_id", eid)
            .in_("status", ["chua_bat_dau", "dang_lam"])
            .lt("deadline_date", today.isoformat()).execute())
        overdue = len(overdue_res.data or [])

        # Stakeholder
        st_res = (supabase.table("stakeholder_tasks")
            .select("assigned_to_team, title, status")
            .eq("employee_id", eid).eq("status", "pending").execute())
        st_tasks = st_res.data or []
        it_pending = any(t["assigned_to_team"] == "it" for t in st_tasks)
        buddy_pending = any("buddy" in t.get("title", "").lower() for t in st_tasks)

        # Sentiment
        sent_res = (supabase.table("sentiment_logs")
            .select("sentiment").eq("employee_id", eid)
            .order("created_at", desc=True).limit(1).execute())
        latest_sentiment = sent_res.data[0]["sentiment"] if sent_res.data else None

        # Preboarding
        pb_res = (supabase.table("preboarding_documents")
            .select("status").eq("employee_id", eid)
            .eq("status", "missing").execute())
        missing_docs = len(pb_res.data or [])

        # ============================================
        # TODO: Nối Agent ML tại đây
        # result = await copilot_summarize(employee_data)
        # ============================================
        risk_factors = []
        suggested_actions = []

        if overdue > 0:
            risk_factors.append(f"{overdue} nhiệm vụ quá hạn")
            suggested_actions.append({"type": "send_reminder", "label": "Gửi nhắc nhở", "target": "employee"})
        if it_pending:
            risk_factors.append("IT chưa provision")
            suggested_actions.append({"type": "escalate_it", "label": "Escalate IT", "target": "it"})
        if buddy_pending:
            risk_factors.append("Chưa assign buddy")
            suggested_actions.append({"type": "assign_buddy", "label": "Nhắc assign buddy", "target": "manager"})
        if latest_sentiment in ("frustrated", "negative"):
            risk_factors.append("Sentiment tiêu cực")
            suggested_actions.append({"type": "schedule_checkin", "label": "Đặt lịch check-in", "target": "hr"})
        if missing_docs > 0:
            risk_factors.append(f"Thiếu {missing_docs} giấy tờ")

        risk_count = len(risk_factors)
        priority = "low" if risk_count == 0 else ("medium" if risk_count <= 2 else "high")

        if risk_factors:
            summary = f"NV {employee['full_name']} cần chú ý: {'; '.join(risk_factors)}."
        else:
            summary = f"NV {employee['full_name']} đang onboard bình thường, không có vấn đề."

        return _ok({
            "employee_id": eid, "employee_name": employee["full_name"],
            "summary": summary, "risk_factors": risk_factors,
            "suggested_actions": suggested_actions,
            "priority": priority, "data_source": "rule_based",
        })
    except Exception as e:
        logger.error(f"Copilot error: {e}")
        return _err(str(e))


@router.post("/recalculate-health", summary="Tinh lai health_score")
async def recalculate_health(
    current_user: UserInfo = Depends(get_current_active_user),
):
    """POST /api/analytics/recalculate-health"""
    try:
        supabase = get_supabase()
        today = date.today()
        now = datetime.now()

        # Bug #6 fix: chỉ tính cho in_progress
        # NV pre_boarding chưa có checklist → days_inactive = 999 → bị red nhầm
        # → giữ green cho pre_boarding, chỉ recalc cho in_progress
        emp_res = (supabase.table("employees")
            .select("id, onboarding_status, health_score")
            .in_("onboarding_status", ["in_progress"])
            .execute())
        employees = emp_res.data or []

        counts = {"green": 0, "yellow": 0, "red": 0}

        for emp in employees:
            eid = emp["id"]

            # Overdue count
            od_res = (supabase.table("checklist_items")
                .select("id", count="exact")
                .eq("employee_id", eid)
                .in_("status", ["chua_bat_dau", "dang_lam"])
                .lt("deadline_date", today.isoformat()).execute())
            overdue = od_res.count if od_res.count is not None else 0

            # Last activity
            last_dates = []
            msg_res = (supabase.table("chatbot_conversations")
                .select("id").eq("employee_id", eid).execute())
            conv_ids = [c["id"] for c in (msg_res.data or [])]
            if conv_ids:
                lm_res = (supabase.table("chatbot_messages")
                    .select("created_at").in_("conversation_id", conv_ids)
                    .order("created_at", desc=True).limit(1).execute())
                if lm_res.data:
                    last_dates.append(lm_res.data[0]["created_at"])

            cl_res = (supabase.table("checklist_items")
                .select("completed_at").eq("employee_id", eid)
                .eq("status", "hoan_thanh")
                .order("completed_at", desc=True).limit(1).execute())
            if cl_res.data and cl_res.data[0].get("completed_at"):
                last_dates.append(cl_res.data[0]["completed_at"])

            if last_dates:
                latest_str = max(last_dates)
                try:
                    latest_dt = datetime.fromisoformat(str(latest_str).replace("Z", "+00:00"))
                    days_inactive = (now - latest_dt.replace(tzinfo=None)).days
                except (ValueError, TypeError):
                    days_inactive = 999
            else:
                days_inactive = 999

            # Latest sentiment
            sent_res = (supabase.table("sentiment_logs")
                .select("sentiment").eq("employee_id", eid)
                .order("created_at", desc=True).limit(1).execute())
            sentiment = sent_res.data[0]["sentiment"] if sent_res.data else None

            # Determine score
            if overdue >= 3 or days_inactive >= 5 or sentiment in ("frustrated", "negative"):
                score = "red"
            elif overdue >= 1 or days_inactive >= 3 or sentiment == "confused":
                score = "yellow"
            else:
                score = "green"

            supabase.table("employees").update({
                "health_score": score, "updated_at": now.isoformat(),
            }).eq("id", eid).execute()

            # Fire outgoing webhook when health transitions to red
            old_score = emp.get("health_score", "green")
            if score == "red" and old_score != "red":
                await fire_event("employee.risk.detected", {
                    "employee_id": eid,
                    "health_score": score,
                    "previous_score": old_score,
                    "trigger": "health_recalculation",
                })

            counts[score] += 1

        return _ok({
            "employees_updated": len(employees),
            **counts,
        })
    except Exception as e:
        logger.error(f"Recalculate health error: {e}")
        return _err(str(e))
