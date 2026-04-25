"""
Preboarding API — Endpoints cho quản lý giấy tờ preboarding nhân viên mới.

Endpoints:
- GET  /api/preboarding/overview                          — Tổng quan tất cả NV preboarding
- GET  /api/preboarding/{employee_id}                     — Danh sách giấy tờ của NV
- POST /api/preboarding/{employee_id}/upload              — Upload giấy tờ
- POST /api/preboarding/{employee_id}/verify/{document_id}  — HR xác nhận hợp lệ
- POST /api/preboarding/{employee_id}/reject/{document_id}  — HR từ chối giấy tờ
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, UploadFile, File, Form
from pydantic import BaseModel, Field

from src.backend.database import get_supabase
from src.backend.api.deps import get_current_active_user
from src.backend.schemas import UserInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/preboarding", tags=["Preboarding"])

# Danh sách document_type hợp lệ
VALID_DOCUMENT_TYPES = ["cmnd", "photo_3x4", "so_bhxh", "bang_cap", "so_tai_khoan"]


# ─── Schemas ───


class VerifyRequest(BaseModel):
    """Body cho POST /api/preboarding/{employee_id}/verify/{document_id}."""
    verified_by: str = Field(..., description="UUID of HR user", examples=["550e8400-e29b-41d4-a716-446655440000"])


class RejectRequest(BaseModel):
    """Body cho POST /api/preboarding/{employee_id}/reject/{document_id}."""
    rejected_reason: str = Field(..., min_length=2, examples=["Ảnh bị mờ, vui lòng chụp lại"])


# ─── Helpers ───


def _ok(data):
    """Standard success response."""
    return {"success": True, "data": data}


def _err(msg: str, status_code: int = 400):
    """Standard error response — returned as dict, caller sets status."""
    return {"success": False, "error": msg}


# ─── Endpoints ───


@router.get(
    "/overview",
    summary="Tong quan preboarding tat ca NV",
    description="HR xem tong quan giay to cua tat ca NV dang preboarding. "
                "Group theo employee, dem uploaded/verified/missing.",
)
async def preboarding_overview(
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/preboarding/overview — tong quan preboarding."""
    try:
        supabase = get_supabase()

        # Lấy NV đang pre_boarding
        emp_result = (
            supabase.table("employees")
            .select("id, full_name, start_date")
            .eq("onboarding_status", "pre_boarding")
            .order("start_date")
            .execute()
        )

        employees = emp_result.data or []

        if not employees:
            return _ok([])

        # Lấy tất cả preboarding_documents cho các NV này
        emp_ids = [e["id"] for e in employees]
        docs_result = (
            supabase.table("preboarding_documents")
            .select("employee_id, status")
            .in_("employee_id", emp_ids)
            .execute()
        )

        docs = docs_result.data or []

        # Group và đếm theo employee
        doc_stats = {}
        for doc in docs:
            eid = doc["employee_id"]
            if eid not in doc_stats:
                doc_stats[eid] = {"total_docs": 0, "uploaded": 0, "verified": 0, "missing": 0}
            doc_stats[eid]["total_docs"] += 1
            status = doc["status"]
            if status == "uploaded":
                doc_stats[eid]["uploaded"] += 1
            elif status == "verified":
                doc_stats[eid]["verified"] += 1
            elif status == "missing":
                doc_stats[eid]["missing"] += 1

        # Build response
        overview = []
        for emp in employees:
            stats = doc_stats.get(emp["id"], {"total_docs": 0, "uploaded": 0, "verified": 0, "missing": 0})
            overview.append({
                "employee_id": emp["id"],
                "employee_name": emp["full_name"],
                "start_date": emp.get("start_date"),
                **stats,
            })

        return _ok(overview)

    except Exception as e:
        logger.error(f"Preboarding overview error: {e}")
        return _err(str(e))


@router.get(
    "/{employee_id}",
    summary="Giay to preboarding cua NV",
    description="Lay danh sach preboarding documents cua 1 nhan vien. "
                "Tinh total, uploaded, missing.",
)
async def get_preboarding(
    employee_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/preboarding/{employee_id} — danh sach giay to."""
    try:
        supabase = get_supabase()

        # Employee info
        emp_result = (
            supabase.table("employees")
            .select("id, full_name, start_date")
            .eq("id", employee_id)
            .limit(1)
            .execute()
        )

        if not emp_result.data:
            return _err(f"Employee {employee_id} not found")

        employee = emp_result.data[0]

        # Documents
        docs_result = (
            supabase.table("preboarding_documents")
            .select(
                "id, document_type, document_label, status, "
                "filename, storage_path, file_size, "
                "uploaded_at, verified_by, rejected_reason, created_at"
            )
            .eq("employee_id", employee_id)
            .order("created_at")
            .execute()
        )

        documents = docs_result.data or []

        # Đếm stats
        total = len(documents)
        uploaded = sum(1 for d in documents if d["status"] in ("uploaded", "verified"))
        missing = sum(1 for d in documents if d["status"] == "missing")

        return _ok({
            "employee_id": employee_id,
            "employee_name": employee["full_name"],
            "start_date": employee.get("start_date"),
            "total": total,
            "uploaded": uploaded,
            "missing": missing,
            "documents": documents,
        })

    except Exception as e:
        logger.error(f"Get preboarding error: {e}")
        return _err(str(e))


@router.post(
    "/{employee_id}/upload",
    summary="Upload giay to",
    description="Upload 1 giay to preboarding. Document_type phai la: "
                "cmnd, photo_3x4, so_bhxh, bang_cap, so_tai_khoan.",
    status_code=201,
)
async def upload_document(
    employee_id: str,
    document_type: str = Form(..., description="Loại giấy tờ: cmnd, photo_3x4, so_bhxh, bang_cap, so_tai_khoan"),
    file: UploadFile = File(..., description="File giấy tờ (jpg, png, pdf)"),
    current_user: UserInfo = Depends(get_current_active_user),
):
    """POST /api/preboarding/{employee_id}/upload — upload giay to."""
    try:
        # Validate document_type
        if document_type not in VALID_DOCUMENT_TYPES:
            return _err(
                f"document_type '{document_type}' không hợp lệ. "
                f"Chấp nhận: {', '.join(VALID_DOCUMENT_TYPES)}"
            )

        supabase = get_supabase()

        # Đọc file content
        file_content = await file.read()
        file_size = len(file_content)
        storage_path = f"{employee_id}/{document_type}_{file.filename}"

        # Upload file vào Supabase Storage
        storage_success = False
        try:
            supabase.storage.from_("preboarding").upload(
                storage_path,
                file_content,
                {"content-type": file.content_type or "application/octet-stream"},
            )
            storage_success = True
        except Exception as storage_err:
            # Bucket chưa tồn tại → tạo mới rồi retry
            err_str = str(storage_err).lower()
            if "not found" in err_str or "bucket" in err_str:
                try:
                    supabase.storage.create_bucket(
                        "preboarding",
                        {"public": False},
                    )
                    supabase.storage.from_("preboarding").upload(
                        storage_path,
                        file_content,
                        {"content-type": file.content_type or "application/octet-stream"},
                    )
                    storage_success = True
                except Exception as retry_err:
                    logger.warning(f"Storage upload retry failed: {retry_err}")
            else:
                logger.warning(f"Storage upload failed: {storage_err}")

        # Update preboarding_documents
        update_result = (
            supabase.table("preboarding_documents")
            .update({
                "status": "uploaded",
                "filename": file.filename,
                "storage_path": storage_path,
                "file_size": file_size,
                "uploaded_at": datetime.now().isoformat(),
            })
            .eq("employee_id", employee_id)
            .eq("document_type", document_type)
            .execute()
        )

        if not update_result.data:
            return _err(f"Không tìm thấy document_type '{document_type}' cho employee {employee_id}")

        # Kiểm tra còn thiếu docs nào
        missing_result = (
            supabase.table("preboarding_documents")
            .select("document_type")
            .eq("employee_id", employee_id)
            .eq("status", "missing")
            .execute()
        )

        remaining = [d["document_type"] for d in (missing_result.data or [])]

        return _ok({
            "document_type": document_type,
            "status": "uploaded",
            "filename": file.filename,
            "storage_uploaded": storage_success,
            "remaining_count": len(remaining),
            "remaining": remaining,
        })

    except Exception as e:
        logger.error(f"Upload preboarding doc error: {e}")
        return _err(str(e))


@router.get(
    "/{employee_id}/download/{document_id}",
    summary="Download giay to (signed URL)",
    description="Tao signed URL (5 phut) de download giay to tu Supabase Storage.",
)
async def download_document(
    employee_id: str,
    document_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/preboarding/{employee_id}/download/{document_id} — signed URL."""
    try:
        supabase = get_supabase()

        # Lấy storage_path từ DB
        doc_result = (
            supabase.table("preboarding_documents")
            .select("id, document_type, filename, storage_path, status")
            .eq("id", document_id)
            .eq("employee_id", employee_id)
            .limit(1)
            .execute()
        )

        if not doc_result.data:
            return _err(f"Document {document_id} not found for employee {employee_id}")

        doc = doc_result.data[0]

        if doc["status"] == "missing":
            return _err("File chưa được upload")

        storage_path = doc.get("storage_path")
        if not storage_path:
            return _err("Không có storage_path — file chưa được upload lên Storage")

        # Tạo signed URL (5 phút = 300 giây)
        try:
            signed = supabase.storage.from_("preboarding").create_signed_url(
                storage_path, 300
            )
            signed_url = signed.get("signedURL") or signed.get("signedUrl", "")
        except Exception as sign_err:
            logger.warning(f"Create signed URL failed: {sign_err}")
            return _err(f"Không tạo được download URL: {sign_err}")

        return _ok({
            "document_id": document_id,
            "document_type": doc["document_type"],
            "filename": doc.get("filename"),
            "download_url": signed_url,
            "expires_in_seconds": 300,
        })

    except Exception as e:
        logger.error(f"Download preboarding doc error: {e}")
        return _err(str(e))


@router.post(
    "/{employee_id}/verify/{document_id}",
    summary="HR xac nhan giay to hop le",
    description="HR xac nhan giay to da duoc nop la hop le.",
)
async def verify_document(
    employee_id: str,
    document_id: str,
    body: VerifyRequest,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """POST /api/preboarding/{employee_id}/verify/{document_id} — xac nhan hop le."""
    try:
        supabase = get_supabase()

        result = (
            supabase.table("preboarding_documents")
            .update({
                "status": "verified",
                "verified_by": body.verified_by,
            })
            .eq("id", document_id)
            .eq("employee_id", employee_id)
            .execute()
        )

        if not result.data:
            return _err(f"Document {document_id} not found for employee {employee_id}")

        return _ok({
            "document_id": document_id,
            "status": "verified",
        })

    except Exception as e:
        logger.error(f"Verify preboarding doc error: {e}")
        return _err(str(e))


@router.post(
    "/{employee_id}/reject/{document_id}",
    summary="HR tu choi giay to",
    description="HR tu choi giay to khong hop le (anh mo, sai loai...).",
)
async def reject_document(
    employee_id: str,
    document_id: str,
    body: RejectRequest,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """POST /api/preboarding/{employee_id}/reject/{document_id} — tu choi giay to."""
    try:
        supabase = get_supabase()

        result = (
            supabase.table("preboarding_documents")
            .update({
                "status": "rejected",
                "rejected_reason": body.rejected_reason,
            })
            .eq("id", document_id)
            .eq("employee_id", employee_id)
            .execute()
        )

        if not result.data:
            return _err(f"Document {document_id} not found for employee {employee_id}")

        return _ok({
            "document_id": document_id,
            "status": "rejected",
            "rejected_reason": body.rejected_reason,
        })

    except Exception as e:
        logger.error(f"Reject preboarding doc error: {e}")
        return _err(str(e))
