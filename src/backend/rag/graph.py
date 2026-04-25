"""
LangGraph Chatbot Pipeline — Optimized version.

CHANGES from original:
  - NeMo Guardrails: COMMENTED OUT (incompatible with Python 3.14, over-engineering)
  - doc_grader node: REMOVED (chunking + score_threshold replaces it)
  - retry loop: REMOVED (chunking makes retrieval accurate enough)
  - llm_router + rewrite_query: MERGED into 1 node, 1 LLM call
  - Embedding reuse: question_embedding flows through AgentState

Pipeline: 5 nodes, 2 LLM calls (was 8 nodes, 5-7 LLM calls)
  normalize → faq_cache_check → (miss) → classify_and_rewrite → retriever → generator → END
                               → (hit)  → END
"""

import json
import logging
import time
import asyncio
from typing import TypedDict, List, Dict, Any, Literal, Optional
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field

from src.config import OPENAI_API_KEY, DEFAULT_MODEL

# ── NeMo Guardrails — COMMENTED OUT ──────────────────────────────────────────
# Lý do: 
#   1. Không tương thích Python 3.14 (ImportError: tracing_enabled)
#   2. Thêm ~1 LLM call + ~1 embedding call mỗi request (~3-8s)
#   3. Chức năng off-topic đã được xử lý bởi intent classifier (off_topic intent)
#   4. Chatbot nội bộ (đã login) → rủi ro off-topic thấp
#
# import os
# from nemoguardrails import LLMRails, RailsConfig
# config_path = os.path.join(os.path.dirname(__file__), "guardrails_config")
# rails_config = RailsConfig.from_path(config_path)
# guardrails = LLMRails(rails_config)
# ─────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

# Import FAQ Cache (lazy — avoids circular imports)
_faq_cache = None

def _get_faq_cache():
    global _faq_cache
    if _faq_cache is None:
        from src.backend.rag.faq_cache import get_faq_cache
        _faq_cache = get_faq_cache()
    return _faq_cache

# Khởi tạo mô hình — ép dùng gpt-4o-mini nếu DEFAULT_MODEL là Claude
_model_name = DEFAULT_MODEL if DEFAULT_MODEL and DEFAULT_MODEL.startswith("gpt") else "gpt-4o-mini"
llm = ChatOpenAI(
    model=_model_name,
    api_key=OPENAI_API_KEY,
    temperature=0
)

# ==========================================
# 1. Định nghĩa State của Graph
# ==========================================
class AgentState(TypedDict):
    employee_id: str
    original_message: str
    normalized_message: str
    employee_context: Dict[str, Any]

    # FAQ Cache
    faq_cache_hit: bool

    # Embedding reuse — tránh embed cùng câu hỏi nhiều lần
    question_embedding: List[float]

    # Intent + search
    intent: str  # "policy", "hr_update", "it_ticket", "off_topic"
    search_query: str
    documents: List[Dict[str, Any]]

    # Tool results
    hr_data: Dict[str, Any]
    ticket_data: Dict[str, Any]

    # Output
    final_answer: str
    sources: List[str]
    actions_taken: List[str]

    # Waterfall / Timings
    timings: Dict[str, Dict[str, float]]


# ==========================================
# Structured Output cho merged node
# ==========================================
class IntentAndQuery(BaseModel):
    intent: Literal["policy", "hr_update", "it_ticket", "off_topic"] = Field(
        description=(
            "Phân loại yêu cầu: "
            "'policy' nếu hỏi về chính sách/sổ tay/quy trình, "
            "'hr_update' nếu tra cứu/cập nhật thông tin nhân sự, "
            "'it_ticket' nếu yêu cầu thiết bị/phần mềm/VPN, "
            "'off_topic' nếu KHÔNG liên quan đến công ty."
        )
    )
    search_query: str = Field(
        description=(
            "Câu hỏi đã được viết lại tối ưu cho vector search. "
            "Nếu intent là off_topic, trả về chuỗi rỗng."
        )
    )


# ==========================================
# 2. Node Functions
# ==========================================

async def normalize_input(state: AgentState) -> Dict[str, Any]:
    """1. Normalize text input."""
    start = time.time()
    logger.info("---NODE: NORMALIZE INPUT---")
    original = state.get("original_message", "")
    normalized = original.strip().lower()

    timings = state.get("timings") or {}
    end = time.time()
    timings["normalize_input"] = {"start": start, "end": end, "duration": round(end - start, 4)}

    return {"normalized_message": normalized, "faq_cache_hit": False, "timings": timings}


async def faq_cache_check(state: AgentState) -> Dict[str, Any]:
    """2. FAQ Cache check — trả lời ngay nếu đã có trong cache."""
    start = time.time()
    logger.info("---NODE: FAQ CACHE CHECK---")
    question = state.get("normalized_message", "")
    timings = state.get("timings") or {}

    try:
        cache = _get_faq_cache()
        hit, result = await cache.lookup(question)

        if hit and result:
            end = time.time()
            timings["faq_cache_check"] = {"start": start, "end": end, "duration": round(end - start, 4)}
            logger.info(f" > Cache HIT (took {end - start:.4f}s)")
            return {
                "faq_cache_hit": True,
                "final_answer": result["final_answer"],
                "sources": result["sources"],
                "actions_taken": result["actions_taken"],
                "question_embedding": result.get("question_embedding", []),
                "timings": timings,
            }

        # Cache miss — lấy embedding đã compute để reuse
        question_embedding = result.get("question_embedding", []) if result else []

    except Exception as e:
        logger.warning(f" > FAQ cache check failed (skipping): {e}")
        question_embedding = []

    end = time.time()
    timings["faq_cache_check"] = {"start": start, "end": end, "duration": round(end - start, 4)}
    return {
        "faq_cache_hit": False,
        "question_embedding": question_embedding,
        "timings": timings,
    }


async def classify_and_rewrite(state: AgentState) -> Dict[str, Any]:
    """3. MERGED: Intent classification + Query rewrite in 1 LLM call."""
    start = time.time()
    logger.info("---NODE: CLASSIFY AND REWRITE---")
    question = state["normalized_message"]
    timings = state.get("timings") or {}

    intent = "policy"
    search_query = question

    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Bạn là AI phân loại ý định và tối ưu câu hỏi.\n\n"
             "Bước 1: Xếp câu hỏi vào 1 trong 4 nhóm:\n"
             "- policy: Hỏi về chính sách, nghỉ phép, sổ tay nhân viên, quy trình.\n"
             "- hr_update: Cập nhật hồ sơ, tra cứu tiến độ nhân sự.\n"
             "- it_ticket: Cấp quyền, laptop, reset password, VPN.\n"
             "- off_topic: Không liên quan đến công ty (thời tiết, game, nấu ăn, v.v.).\n\n"
             "Bước 2: Viết lại câu hỏi tối ưu cho vector search (ngắn gọn, rõ ràng).\n"
             "Nếu off_topic → search_query = chuỗi rỗng."),
            ("user", "Câu hỏi: {question}")
        ])
        structured_llm = llm.with_structured_output(IntentAndQuery)
        chain = prompt | structured_llm
        result = await chain.ainvoke({"question": question})
        intent = result.intent
        search_query = result.search_query or question
        logger.info(f" > Intent: {intent}, Query: {search_query[:60]}")
    except Exception as e:
        logger.warning(f" > Classification failed, defaulting to policy: {e}")

    end = time.time()
    timings["classify_and_rewrite"] = {"start": start, "end": end, "duration": round(end - start, 4)}

    # Off-topic → trả lời ngay
    if intent == "off_topic":
        return {
            "intent": "off_topic",
            "search_query": "",
            "final_answer": "Xin lỗi, tôi là trợ lý AI chuyên môn của công ty. "
                           "Tôi chỉ có thể hỗ trợ các vấn đề liên quan đến nội quy, "
                           "nhân sự, IT và quy trình làm việc.",
            "actions_taken": state.get("actions_taken", []) + ["Off-topic detected"],
            "timings": timings,
        }

    return {"intent": intent, "search_query": search_query, "timings": timings}


async def retriever(state: AgentState) -> Dict[str, Any]:
    """4. RETRIEVER: Semantic search trên chunks (dùng local embedding)."""
    start = time.time()
    logger.info("---NODE: RETRIEVER---")
    from src.backend.rag.documents import search_documents

    query = state.get("search_query", "")
    question_embedding = state.get("question_embedding")
    timings = state.get("timings") or {}

    try:
        # Truyền embedding nếu query giống original question (reuse)
        docs = await search_documents(
            query,
            top_k=5,
            score_threshold=0.3,
            query_embedding=question_embedding if query == state.get("normalized_message") else None,
        )
    except Exception as e:
        logger.warning(f" > Retriever error: {e}")
        docs = []

    logger.info(f" > Found {len(docs)} chunks for: {query[:60]}")

    end = time.time()
    timings["retriever"] = {"start": start, "end": end, "duration": round(end - start, 4)}
    return {"documents": docs, "timings": timings}


async def hr_api_tool(state: AgentState) -> Dict[str, Any]:
    """5a. HR API TOOL: Tra cứu Dashboard HR."""
    start = time.time()
    logger.info("---NODE: HR API TOOL---")
    timings = state.get("timings") or {}

    end = time.time()
    timings["hr_api_tool"] = {"start": start, "end": end, "duration": round(end - start, 4)}

    return {
        "hr_data": {"status": "success", "info": "Đã kiểm tra hệ thống HR."},
        "actions_taken": state.get("actions_taken", []) + ["Truy vấn API nhân sự"],
        "timings": timings,
    }


async def ticket_api_tool(state: AgentState) -> Dict[str, Any]:
    """5b. TICKET API TOOL: Tạo yêu cầu IT."""
    start = time.time()
    logger.info("---NODE: TICKET API TOOL---")
    timings = state.get("timings") or {}

    end = time.time()
    timings["ticket_api_tool"] = {"start": start, "end": end, "duration": round(end - start, 4)}

    return {
        "ticket_data": {"ticket_id": "IT-9999", "status": "created"},
        "actions_taken": state.get("actions_taken", []) + ["Tạo vé IT Support IT-9999"],
        "timings": timings,
    }


async def generator(state: AgentState) -> Dict[str, Any]:
    """6. GENERATOR: Tổng hợp câu trả lời cuối cùng."""
    start = time.time()
    logger.info("---NODE: GENERATOR---")
    intent = state.get("intent", "policy")
    timings = state.get("timings") or {}

    # Chuẩn bị Context
    context_str = ""
    if intent == "policy":
        for doc in state.get("documents", []):
            context_str += doc["content"] + "\n"
        if not context_str:
            context_str = "Không tìm thấy tài liệu liên quan."
    elif intent == "hr_update":
        context_str = json.dumps(state.get("hr_data", {}), ensure_ascii=False)
    elif intent == "it_ticket":
        context_str = json.dumps(state.get("ticket_data", {}), ensure_ascii=False)

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Bạn là trợ lý ảo Onboarding của công ty. Hãy trả lời thân thiện dựa vào Context bên dưới.\n"
         "Nếu Context không đủ thông tin, hãy trả lời theo hiểu biết chung và đề nghị liên hệ HR.\n\n"
         "Context:\n{context}"),
        ("user", "Yêu cầu: {question}")
    ])
    chain = prompt | llm | StrOutputParser()

    try:
        answer = await chain.ainvoke({
            "question": state.get("original_message", ""),
            "context": context_str,
        })
        answer = answer.strip() or "Xin lỗi, tôi không thể tạo câu trả lời lúc này."
    except Exception as e:
        logger.error(f" > Generator LLM failed: {e}")
        answer = "Xin lỗi, hệ thống đang gặp sự cố. Vui lòng thử lại sau."

    sources = (
        [doc["id"] for doc in state.get("documents", []) if doc.get("id")]
        if intent == "policy" else []
    )

    # Lưu kết quả mới vào FAQ cache (REUSE embedding, không gọi API lại)
    try:
        original_question = state.get("original_message", "")
        if original_question and answer and "không thể" not in answer.lower()[:50]:
            cache = _get_faq_cache()
            await cache.store(
                question=original_question,
                answer=answer,
                sources=sources,
                actions_taken=state.get("actions_taken", []),
                question_embedding=state.get("question_embedding"),  # REUSE
            )
    except Exception as e:
        logger.warning(f" > FAQ cache store failed: {e}")

    end = time.time()
    timings["generator"] = {"start": start, "end": end, "duration": round(end - start, 4)}

    return {"final_answer": answer, "sources": sources, "timings": timings}


# ==========================================
# 3. Conditional Edges
# ==========================================

def route_faq_cache(state: AgentState) -> Literal["cache_hit", "cache_miss"]:
    """Sau khi check cache: hit → END, miss → full pipeline."""
    return "cache_hit" if state.get("faq_cache_hit") else "cache_miss"


def route_intent(state: AgentState) -> Literal["policy", "hr_update", "it_ticket", "off_topic"]:
    """Điều hướng dựa trên intent."""
    intent = state.get("intent", "policy")
    return intent if intent in ("policy", "hr_update", "it_ticket", "off_topic") else "policy"


# ==========================================
# 4. Build Graph — Optimized (5 nodes, 2 LLM calls)
# ==========================================
# OLD: normalize → cache → NeMo+intent → rewrite → retrieve → grade → (retry?) → generate
# NEW: normalize → cache → classify+rewrite → retrieve → generate

def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("normalize_input", normalize_input)
    workflow.add_node("faq_cache_check", faq_cache_check)
    workflow.add_node("classify_and_rewrite", classify_and_rewrite)
    workflow.add_node("retriever", retriever)
    workflow.add_node("hr_api_tool", hr_api_tool)
    workflow.add_node("ticket_api_tool", ticket_api_tool)
    workflow.add_node("generator", generator)

    # normalize → cache check
    workflow.add_edge(START, "normalize_input")
    workflow.add_edge("normalize_input", "faq_cache_check")

    # cache check → hit: END, miss: classify
    workflow.add_conditional_edges(
        "faq_cache_check",
        route_faq_cache,
        {
            "cache_hit": END,
            "cache_miss": "classify_and_rewrite",
        },
    )

    # classify → route by intent
    workflow.add_conditional_edges(
        "classify_and_rewrite",
        route_intent,
        {
            "policy": "retriever",
            "hr_update": "hr_api_tool",
            "it_ticket": "ticket_api_tool",
            "off_topic": END,
        },
    )

    # retriever → generator (NO doc_grader, NO retry loop)
    workflow.add_edge("retriever", "generator")
    workflow.add_edge("hr_api_tool", "generator")
    workflow.add_edge("ticket_api_tool", "generator")
    workflow.add_edge("generator", END)

    return workflow.compile()


# Initialize the graph (module-level singleton)
chatbot_graph = build_graph()
