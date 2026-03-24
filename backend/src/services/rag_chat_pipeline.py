from src.services.chromadb_service import get_chroma_service
from src.services.llm_service import get_llm_service
from src.services.guardrail_service import get_guardrail_service
from src.utils.nlp_processor import NLPProcessor
from src.config.db import supabase
from rank_bm25 import BM25Okapi
from src.utils.nlp_processor import NLPProcessor

import logging

logger = logging.getLogger(__name__)


async def process_chat_workflow(question: str, company: str, department: str = None):
    guardrail = get_guardrail_service()
    lang      = guardrail._detect_language(question)

    # ════════════════════════════════════════════════
    # ด่าน 0 — Greeting Fast Track
    # ════════════════════════════════════════════════
    if guardrail.check_greeting(question):
        return _ok(
            "สวัสดีค่ะ ดิฉันเป็นผู้ช่วย AI ฉันชื่อน้องโพลิ หากต้องการสอบถามเรื่องระเบียบหรือสวัสดิการของบริษัท สามารถถามได้เลยนะคะ ดิฉันยินดีช่วยค่ะ 😊"
            if lang == "th" else
            "Hello! I'm your AI Assistant. My name is Poli. How can I help you with policies or benefits today?",
            topic="ทักทาย",
        )

    # ════════════════════════════════════════════════
    # ด่าน 1 — Input Guardrail
    # ════════════════════════════════════════════════
    input_check = guardrail.check_comprehensive(question)
    topic       = input_check.get("topic", "ทั่วไป")

    if not input_check["allowed"]:
        logger.warning(f"🚫 INPUT BLOCKED [{input_check['block_reason']}]: {question[:60]}")
        return _blocked(input_check["message"], topic=topic)

    # ════════════════════════════════════════════════
    # ด่าน 2 — Hybrid Retrieval
    # ════════════════════════════════════════════════
    chroma_service = get_chroma_service()
    dept_clean     = department.strip().lower() if department and department.strip().lower() != "all" else None

    logger.info(f"🔍 Searching [{company}] | dept={dept_clean or 'all only'}")

    # ────────────────────────────────────────────────
    # Phase 1: ค้นแยก all + department แล้วรวม score
    # ────────────────────────────────────────────────

    # filename → best avg_score (เอาดีที่สุดจากทั้ง 2 collection)
    score_map: dict[str, float] = {}

    def _score_files(dept_list: list[str]):
        filenames = chroma_service.get_unique_filenames(company=company, dept_list=dept_list)
        logger.info(f"📂 [{dept_list}] found: {filenames}")
        for filename in filenames:
            results = chroma_service.query_by_filename(
                question=question,
                company=company,
                dept_list=dept_list,
                filename=filename,
                top_k=5,
            )
            if not results:
                continue
            results.sort(key=lambda x: x["score"])
            top3    = [r["score"] for r in results[:3]]
            avg     = sum(top3) / len(top3)
            logger.info(f"   📄 {filename} | avg_top3={avg:.4f}")
            # เก็บ score ที่ดีที่สุด (ต่ำสุด) ของแต่ละไฟล์
            if filename not in score_map or avg < score_map[filename]:
                score_map[filename] = avg

    # ค้น all collection เสมอ
    _score_files(["all"])

    # ค้น department collection ถ้ามี
    if dept_clean:
        _score_files([dept_clean])

    if not score_map:
        return _ok(
            "ขออภัยค่ะ ไม่พบเอกสารในระบบ" if lang == "th" else
            "I apologize, but no documents were found in the system.",
            topic=topic,
        )

    # ────────────────────────────────────────────────
    # Phase 2: Rerank — Dynamic top_files
    # ────────────────────────────────────────────────
    ranked          = sorted(score_map.items(), key=lambda x: x[1])
    best_file_score = ranked[0][1]
    FILE_GAP        = 0.15

    top_files = [ranked[0][0]]
    for fname, score in ranked[1:3]:
        if score - best_file_score <= FILE_GAP:
            top_files.append(fname)

    logger.info(f"🏆 Dynamic Top Files: {top_files} (gap≤{FILE_GAP})")

    # ────────────────────────────────────────────────
    # Phase 3: Deep fetch + BM25 + RRF Hybrid Rerank
    # ────────────────────────────────────────────────
    nlp_tok    = NLPProcessor()
    raw_chunks = []
    seen_ids   = set()

    def _deep_fetch(dept_list: list[str]):
        for filename in top_files:
            results = chroma_service.query_by_filename(
                question=question,
                company=company,
                dept_list=dept_list,
                filename=filename,
                top_k=5,
            )
            for r in results:
                if r["id"] not in seen_ids:
                    seen_ids.add(r["id"])
                    raw_chunks.append(r)

    _deep_fetch(["all"])
    if dept_clean:
        _deep_fetch([dept_clean])

    if not raw_chunks:
        return _ok(
            "ขออภัยค่ะ ดิฉันไม่พบข้อมูลเกี่ยวกับเรื่องนี้ในเอกสารระเบียบของบริษัท" if lang == "th" else
            "I apologize, but I couldn't find relevant information in the policy documents.",
            topic=topic,
        )

    # BM25
    corpus      = [nlp_tok.tokenize(r["content"]) for r in raw_chunks]
    bm25        = BM25Okapi(corpus)
    bm25_scores = bm25.get_scores(nlp_tok.tokenize(question))
    bm25_max    = max(bm25_scores) if max(bm25_scores) > 0 else 1.0
    bm25_norm   = [s / bm25_max for s in bm25_scores]

    # RRF
    emb_ranked  = sorted(range(len(raw_chunks)), key=lambda i: raw_chunks[i]["score"])
    bm25_ranked = sorted(range(len(raw_chunks)), key=lambda i: bm25_norm[i], reverse=True)
    emb_rank    = {idx: rank for rank, idx in enumerate(emb_ranked)}
    bm25_rank   = {idx: rank for rank, idx in enumerate(bm25_ranked)}

    K = 60
    for i, r in enumerate(raw_chunks):
        r["hybrid_score"] = 1/(K + emb_rank[i]) + 1/(K + bm25_rank[i])

    raw_chunks.sort(key=lambda x: x["hybrid_score"], reverse=True)
    results = raw_chunks[:15]

    logger.info(f"📊 Final chunks: {len(results)} | best_hybrid={results[0]['hybrid_score']:.4f}")

    # ════════════════════════════════════════════════
    # ด่าน 3 — Context Construction & LLM
    # ════════════════════════════════════════════════
    context_parts = []
    for r in results:
        source  = r["metadata"].get("original_filename", "Unknown")
        page    = r["metadata"].get("page_number", "-")
        content = r["content"]
        context_parts.append(f"[Source: {source} | Page: {page}]\n{content}")

    context_text = "\n\n---\n\n".join(context_parts)

    llm        = get_llm_service()
    raw_answer = llm.answer_from_policy(question, context_text)

    if not raw_answer:
        return _ok(
            "ขออภัยค่ะ ระบบไม่สามารถสร้างคำตอบได้ในขณะนี้" if lang == "th" else
            "I'm sorry, the system was unable to generate an answer at this time.",
            topic=topic,
        )

    # ════════════════════════════════════════════════
    # ด่าน 4 — Output Guardrail
    # ════════════════════════════════════════════════
    output_safety = guardrail.check_output_safety(question, raw_answer)
    if not output_safety["is_safe"]:
        logger.warning(f"🚫 OUTPUT BLOCKED: {raw_answer[:80]}")
        return _blocked(
            "ขออภัยค่ะ คำตอบที่ระบบสร้างขึ้นไม่ผ่านการตรวจสอบความปลอดภัย" if lang == "th" else
            "I apologize, but the generated answer did not pass the safety check.",
            topic=topic,
        )

    nlp_processor = NLPProcessor()
    safe_answer   = nlp_processor.redact_sensitive_info(raw_answer)

    # Mask source display
    safe_sources = []
    for src in results:
        meta = src["metadata"].copy()
        col  = meta.get("from_col") or f"{company}_{meta.get('department', 'general')}"
        page = meta.get("page_number", "-")
        dept_display   = col.split("_", 1)[-1].upper() if "_" in col else col.upper()
        meta["source"] = f"เอกสารระเบียบการ ({dept_display}) หน้า {page}"
        safe_sources.append({"content": src["content"], "metadata": meta})

    logger.info(f"✅ Answer generated | company={company} | lang={lang} | sources={len(safe_sources)}")

    return {
        "status":       "success",
        "answer":       safe_answer,
        "sources":      safe_sources,
        "context_used": True,
        "topic":        topic,
        "top_files":    top_files,
    }


# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────
def _ok(message: str, context_used: bool = False, topic: str = "ทั่วไป") -> dict:
    return {
        "status":       "success",
        "answer":       message,
        "sources":      [],
        "context_used": context_used,
        "topic":        topic,
        "top_files":    [],
    }


def _blocked(message: str, topic: str = "ทั่วไป") -> dict:
    return {
        "status":       "blocked",
        "answer":       message,
        "sources":      [],
        "context_used": False,
        "topic":        topic,
        "top_files":    [],
    }