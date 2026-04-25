"""
Documents API — CRUD endpoints cho quản lý tài liệu knowledge base.

Endpoints:
- POST   /api/documents/upload       — Upload tài liệu mới (text content)
- GET    /api/documents              — Danh sách tài liệu
- GET    /api/documents/{id}         — Chi tiết tài liệu + chunks count
- DELETE /api/documents/{id}         — Xóa tài liệu + chunks liên quan
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.backend.database import get_supabase
from src.backend.api.deps import get_current_active_user
from src.backend.schemas import UserInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documents"])


# ─── Schemas ───


class DocumentUpload(BaseModel):
    """Body cho POST /api/documents/upload."""
    title: str = Field(..., min_length=2, examples=["Quy trình onboarding nhân viên mới"])
    content: str = Field(..., min_length=10, examples=["# Quy trình\n\nBước 1: ..."])
    department_tags: list[str] | None = Field(default=None, examples=[["Engineering", "HR"]])
    role_tags: list[str] | None = Field(default=None, examples=[["nhan_vien_moi", "quan_ly"]])
    category: str | None = Field(default=None, examples=["onboarding"])


# ─── Helpers ───


def _ok(data):
    """Standard success response."""
    return {"success": True, "data": data}


def _err(msg: str, status_code: int = 400):
    """Standard error response — returned as dict, caller sets status."""
    return {"success": False, "error": msg}


# ─── Endpoints ───


@router.post(
    "/upload",
    summary="Upload tai lieu moi",
    description="Upload tai lieu dang text (markdown). Noi dung duoc paste truc tiep, khong phai file upload.",
    status_code=201,
)
async def upload_document(
    body: DocumentUpload,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """POST /api/documents/upload — upload tai lieu text."""
    try:
        supabase = get_supabase()
        word_count = len(body.content.split())

        insert_data = {
            "title": body.title,
            "content": body.content,
            "source_type": "manual_upload",
            "language": "vi",
            "is_indexed": False,
            "word_count": word_count,
        }

        # Optional fields
        if body.department_tags:
            insert_data["department_tags"] = body.department_tags
        if body.role_tags:
            insert_data["role_tags"] = body.role_tags
        if body.category:
            insert_data["category"] = body.category

        result = supabase.table("knowledge_documents").insert(insert_data).execute()

        if not result.data:
            return _err("Insert failed — no data returned")

        doc = result.data[0]
        return _ok({
            "document_id": doc["id"],
            "title": doc["title"],
            "word_count": doc["word_count"],
            "message": "Đã upload. Chờ index.",
        })

    except Exception as e:
        logger.error(f"Upload document error: {e}")
        return _err(str(e))


@router.get(
    "",
    summary="Danh sach tai lieu",
    description="Lay danh sach tat ca tai lieu, order by created_at DESC.",
)
async def list_documents(
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/documents — danh sach tai lieu."""
    try:
        supabase = get_supabase()

        result = (
            supabase.table("knowledge_documents")
            .select(
                "id, title, category, is_indexed, word_count, "
                "department_tags, role_tags, created_at"
            )
            .order("created_at", desc=True)
            .execute()
        )

        return _ok(result.data or [])

    except Exception as e:
        logger.error(f"List documents error: {e}")
        return _err(str(e))


@router.get(
    "/{document_id}",
    summary="Chi tiet tai lieu",
    description="Lay thong tin tai lieu + so chunks da index.",
)
async def get_document(
    document_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """GET /api/documents/{id} — chi tiet + chunks count."""
    try:
        supabase = get_supabase()

        # Document info
        doc_result = (
            supabase.table("knowledge_documents")
            .select(
                "id, title, content, category, is_indexed, word_count, "
                "department_tags, role_tags, created_at"
            )
            .eq("id", document_id)
            .limit(1)
            .execute()
        )

        if not doc_result.data:
            return _err(f"Document {document_id} not found")

        document = doc_result.data[0]

        # Count chunks
        chunks_result = (
            supabase.table("knowledge_chunks")
            .select("id", count="exact")
            .eq("document_id", document_id)
            .execute()
        )
        document["chunks_count"] = chunks_result.count if chunks_result.count is not None else 0

        return _ok(document)

    except Exception as e:
        logger.error(f"Get document error: {e}")
        return _err(str(e))


@router.delete(
    "/{document_id}",
    summary="Xoa tai lieu",
    description="Xoa tai lieu va tat ca chunks lien quan.",
)
async def delete_document(
    document_id: str,
    current_user: UserInfo = Depends(get_current_active_user),
):
    """DELETE /api/documents/{id} — xoa document + chunks."""
    try:
        supabase = get_supabase()

        # Xoa chunks truoc (FK constraint)
        supabase.table("knowledge_chunks").delete().eq("document_id", document_id).execute()

        # Xoa document
        result = (
            supabase.table("knowledge_documents")
            .delete()
            .eq("id", document_id)
            .execute()
        )

        if not result.data:
            return _err(f"Document {document_id} not found")

        return _ok({"message": "Đã xóa tài liệu và chunks liên quan"})

    except Exception as e:
        logger.error(f"Delete document error: {e}")
        return _err(str(e))
