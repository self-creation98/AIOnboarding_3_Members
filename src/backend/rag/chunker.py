"""
Document Chunker — Tách tài liệu thành các chunk nhỏ cho RAG.

Spec (theo PRD):
  - chunk_size: 400 ký tự
  - overlap: 80 ký tự
  - Tách theo sentence boundary trước, rồi mới tách theo char limit
  - Mỗi chunk giữ metadata gốc (doc_id, title, category)
"""

import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# ─── Sentence splitting ──────────────────────────────────────────────────────

# Tách câu theo dấu kết thúc câu tiếng Việt / bullet points / newlines
_SENTENCE_SPLIT_RE = re.compile(
    r'(?<=[.!?])\s+'     # Sau dấu . ! ?
    r'|(?<=\n)\s*'        # Sau newline
    r'|(?=\n[-•●]\s)'     # Trước bullet point
)


def _split_sentences(text: str) -> List[str]:
    """Tách text thành danh sách câu/đoạn."""
    parts = _SENTENCE_SPLIT_RE.split(text.strip())
    return [p.strip() for p in parts if p and p.strip()]


# ─── Chunking ────────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = 400,
    overlap: int = 80,
) -> List[str]:
    """
    Tách text thành các chunk.

    Thuật toán:
      1. Tách thành câu
      2. Gộp câu lại cho đến khi gần đủ chunk_size
      3. Overlap: chunk tiếp theo bắt đầu từ vài câu cuối của chunk trước

    Args:
        text: Nội dung cần chunk
        chunk_size: Kích thước tối đa mỗi chunk (ký tự)
        overlap: Số ký tự overlap giữa 2 chunk liền kề

    Returns:
        List[str] — danh sách chunks
    """
    if not text or not text.strip():
        return []

    sentences = _split_sentences(text)

    # Nếu toàn bộ text ngắn hơn chunk_size → trả về nguyên
    if len(text) <= chunk_size:
        return [text.strip()]

    chunks: List[str] = []
    current_sentences: List[str] = []
    current_length = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        # Nếu thêm câu này vượt quá chunk_size → lưu chunk hiện tại
        if current_length + sentence_len > chunk_size and current_sentences:
            chunk_text_str = " ".join(current_sentences).strip()
            if chunk_text_str:
                chunks.append(chunk_text_str)

            # Overlap: giữ lại các câu cuối có tổng length <= overlap
            overlap_sentences: List[str] = []
            overlap_len = 0
            for s in reversed(current_sentences):
                if overlap_len + len(s) > overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_len += len(s)

            current_sentences = overlap_sentences
            current_length = overlap_len

        current_sentences.append(sentence)
        current_length += sentence_len

    # Chunk cuối cùng
    if current_sentences:
        chunk_text_str = " ".join(current_sentences).strip()
        if chunk_text_str:
            chunks.append(chunk_text_str)

    logger.debug(f"Chunked text ({len(text)} chars) → {len(chunks)} chunks")
    return chunks


def chunk_document(
    doc: Dict[str, Any],
    chunk_size: int = 400,
    overlap: int = 80,
) -> List[Dict[str, Any]]:
    """
    Chunk 1 document thành nhiều chunks, giữ nguyên metadata.

    Args:
        doc: Dict với keys: id, title, content, category (optional)

    Returns:
        List[Dict] — mỗi item có: chunk_id, doc_id, title, category, content, chunk_index
    """
    doc_id = doc.get("id", "unknown")
    title = doc.get("title", "")
    category = doc.get("category", "general")
    content = doc.get("content", "")

    text_chunks = chunk_text(content, chunk_size=chunk_size, overlap=overlap)

    results = []
    for i, chunk in enumerate(text_chunks):
        results.append({
            "chunk_id": f"{doc_id}_chunk_{i}",
            "doc_id": doc_id,
            "title": title,
            "category": category,
            "content": chunk,
            "chunk_index": i,
        })

    return results


def chunk_all_documents(
    documents: List[Dict[str, Any]],
    chunk_size: int = 400,
    overlap: int = 80,
) -> List[Dict[str, Any]]:
    """
    Chunk tất cả documents.

    Returns:
        List[Dict] — tất cả chunks từ tất cả documents.
    """
    all_chunks = []
    for doc in documents:
        chunks = chunk_document(doc, chunk_size=chunk_size, overlap=overlap)
        all_chunks.extend(chunks)

    logger.info(f"Chunked {len(documents)} documents → {len(all_chunks)} chunks")
    return all_chunks
