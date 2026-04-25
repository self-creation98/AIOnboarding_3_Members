"""
Event Dispatcher Service — Gửi outgoing webhooks tới registered URLs.

Flow:
    fire_event(event_type, payload)
      → Query webhook_configs WHERE events contains event_type AND active = true
      → POST payload tới mỗi registered URL (async httpx)
      → Retry 3 lần (exponential backoff: 1s, 2s, 4s)
      → Log vào webhook_logs (direction="out")
      → Fire-and-forget: không block main flow

Usage:
    from src.backend.services.event_dispatcher import fire_event
    await fire_event("employee.onboarding.started", {"employee_id": "..."})

Supported events:
    - employee.onboarding.started
    - employee.task.assigned_to_stakeholder
    - employee.task.overdue
    - employee.risk.detected
    - employee.onboarding.completed
    - content.gap.detected
"""

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime

import httpx

from src.backend.database import get_supabase

logger = logging.getLogger(__name__)

# ─── Constants ───

VALID_EVENT_TYPES = [
    "employee.onboarding.started",
    "employee.task.assigned_to_stakeholder",
    "employee.task.overdue",
    "employee.risk.detected",
    "employee.onboarding.completed",
    "content.gap.detected",
]

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = [1, 2, 4]  # Exponential backoff
REQUEST_TIMEOUT_SECONDS = 10


# ─── HMAC Signing ───


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    """
    Tạo HMAC-SHA256 signature cho payload.

    Receiver verify bằng cách:
        expected = hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
        assert expected == request.headers["X-Webhook-Signature"]
    """
    return hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


# ─── HTTP Sender with Retry ───


async def _send_webhook(
    url: str,
    secret: str | None,
    payload: dict,
    max_retries: int = MAX_RETRIES,
) -> dict:
    """
    POST payload tới URL với retry logic.

    Returns:
        dict với status, response_code, retry_count, error
    """
    payload_bytes = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "AI-Onboarding-Webhook/1.0",
    }

    if secret:
        headers["X-Webhook-Signature"] = _sign_payload(payload_bytes, secret)

    last_error = None

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    url,
                    content=payload_bytes,
                    headers=headers,
                )

            if 200 <= response.status_code < 300:
                return {
                    "success": True,
                    "response_status": response.status_code,
                    "retry_count": attempt,
                    "error_message": None,
                }

            # Non-2xx response
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"

            # 4xx errors → không retry (client error)
            if 400 <= response.status_code < 500:
                return {
                    "success": False,
                    "response_status": response.status_code,
                    "retry_count": attempt,
                    "error_message": last_error,
                }

            # 5xx → retry
            if attempt < max_retries - 1:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS[attempt])

        except httpx.TimeoutException:
            last_error = f"Timeout after {REQUEST_TIMEOUT_SECONDS}s"
            if attempt < max_retries - 1:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS[attempt])

        except Exception as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS[attempt])

    return {
        "success": False,
        "response_status": 0,
        "retry_count": max_retries,
        "error_message": last_error,
    }


# ─── Webhook Log ───


def _log_outgoing_webhook(
    supabase,
    event_type: str,
    url: str,
    request_body: dict,
    result: dict,
):
    """Ghi log outgoing webhook vào webhook_logs."""
    try:
        supabase.table("webhook_logs").insert({
            "direction": "out",
            "event_type": event_type,
            "endpoint_url": url,
            "request_body": request_body,
            "response_status": result.get("response_status", 0),
            "success": result.get("success", False),
            "error_message": result.get("error_message"),
            "retry_count": result.get("retry_count", 0),
        }).execute()
    except Exception as e:
        logger.error(f"Failed to log outgoing webhook: {e}")


# ─── Main Entry Point ───


async def fire_event(event_type: str, payload: dict):
    """
    Gửi outgoing webhook cho tất cả registered URLs.

    Fire-and-forget: chạy background, không block caller.
    Nếu không có webhook_configs nào đăng ký → skip silently.

    Args:
        event_type: Tên event (VD: "employee.onboarding.started")
        payload: Data đi kèm event
    """
    if event_type not in VALID_EVENT_TYPES:
        logger.warning(f"Unknown event type: {event_type}")
        return

    try:
        supabase = get_supabase()

        # Query webhook_configs đang active
        configs_result = (
            supabase.table("webhook_configs")
            .select("id, name, url, secret, events")
            .eq("active", True)
            .execute()
        )

        configs = configs_result.data or []

        if not configs:
            return

        # Filter configs có đăng ký event_type này
        matching_configs = []
        for config in configs:
            events = config.get("events", [])
            if isinstance(events, str):
                # Handle case events stored as JSON string
                try:
                    events = json.loads(events)
                except (json.JSONDecodeError, TypeError):
                    events = []
            if event_type in events:
                matching_configs.append(config)

        if not matching_configs:
            return

        # Build standardized webhook payload
        webhook_payload = {
            "event": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": payload,
        }

        # Gửi tới tất cả matching configs (concurrent)
        tasks = []
        for config in matching_configs:
            tasks.append(
                _dispatch_single(supabase, event_type, config, webhook_payload)
            )

        await asyncio.gather(*tasks, return_exceptions=True)

    except Exception as e:
        # Fire-and-forget: log error nhưng không raise
        logger.error(f"Event dispatcher error for {event_type}: {e}")


async def _dispatch_single(supabase, event_type: str, config: dict, payload: dict):
    """Gửi webhook tới 1 URL và log kết quả."""
    url = config.get("url", "")
    secret = config.get("secret")

    try:
        result = await _send_webhook(url, secret, payload)
        _log_outgoing_webhook(supabase, event_type, url, payload, result)

        if result["success"]:
            logger.info(f"Webhook sent: {event_type} → {url}")
        else:
            logger.warning(
                f"Webhook failed: {event_type} → {url} "
                f"(retries={result['retry_count']}, error={result['error_message']})"
            )

    except Exception as e:
        logger.error(f"Dispatch error: {event_type} → {url}: {e}")
        _log_outgoing_webhook(supabase, event_type, url, payload, {
            "success": False,
            "response_status": 0,
            "retry_count": 0,
            "error_message": str(e),
        })


async def send_test_webhook(config_id: str) -> dict:
    """
    Gửi test payload tới 1 webhook config để verify URL.

    Returns:
        dict với success, response_status, error_message
    """
    supabase = get_supabase()

    config_result = (
        supabase.table("webhook_configs")
        .select("url, secret, events")
        .eq("id", config_id)
        .limit(1)
        .execute()
    )

    if not config_result.data:
        return {"success": False, "error_message": f"Config {config_id} not found"}

    config = config_result.data[0]

    test_payload = {
        "event": "webhook.test",
        "timestamp": datetime.now().isoformat(),
        "data": {
            "message": "Test webhook from AI Onboarding System",
            "config_id": config_id,
        },
    }

    result = await _send_webhook(config["url"], config.get("secret"), test_payload)
    _log_outgoing_webhook(supabase, "webhook.test", config["url"], test_payload, result)

    return result
