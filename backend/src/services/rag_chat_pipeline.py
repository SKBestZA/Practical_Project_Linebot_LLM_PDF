from src.services.chromadb_service import get_chroma_service
from src.services.llm_service import get_llm_service
from src.services.guardrail_service import get_guardrail_service
from src.utils.nlp_processor import NLPProcessor

import logging

logger = logging.getLogger(__name__)


async def process_chat_workflow(question: str, company: str, department: str = None):
    guardrail = get_guardrail_service()
    lang = guardrail._detect_language(question)

    # ════════════════════════════════════════════════
    # ด่าน 0 — Greeting Fast Track
    # ════════════════════════════════════════════════
    if guardrail.check_greeting(question):
        return _ok(
            "สวัสดีค่ะ ดิฉันเป็นผู้ช่วย AI หากต้องการสอบถามเรื่องระเบียบหรือสวัสดิการของบริษัท สามารถถามได้เลยนะคะ ดิฉันยินดีช่วยค่ะ 😊"
            if lang == "th"
            else "Hello! I'm your AI Assistant. How can I help you with policies or benefits today?",
            context_used=False,
        )

    # ════════════════════════════════════════════════
    # ด่าน 1 — Input Guardrail
    # ════════════════════════════════════════════════
    input_check = guardrail.check_comprehensive(question)
    if not input_check["allowed"]:
        logger.warning(f"🚫 INPUT BLOCKED [{input_check['block_reason']}]: {question[:60]}")
        return _blocked(input_check["message"])

    # ════════════════════════════════════════════════
    # ด่าน 2 — Hybrid Retrieval (1 → Top3 → 5x3 = 15)
    # ════════════════════════════════════════════════
    chroma_service = get_chroma_service()

    dept_list = (
        [department.strip().lower()]
        if department and department.strip().lower() != "all"
        else ["all"]
    )

    filenames = chroma_service.get_unique_filenames(company=company, dept_list=dept_list)
    logger.info(f"📂 Filenames found: {filenames}")

    if not filenames:
        return _ok(
            "ขออภัยค่ะ ไม่พบเอกสารในระบบ"
            if lang == "th"
            else "I apologize, but no documents were found in the system.",
            context_used=False,
        )

    logger.info(f"🔍 Searching [{company}] | {len(filenames)} files | dept={dept_list}")

    # ────────────────────────────────────────────────
    # Phase 1: หา 1 best chunk ต่อไฟล์ (แต่ query 5 เพื่อหา best จริง)
    # ────────────────────────────────────────────────
    best_per_file = []

    for filename in filenames:
        file_results = chroma_service.query_by_filename(
            question=question,
            company=company,
            dept_list=dept_list,
            filename=filename,
            top_k=5,  # ดึง 5 เพื่อหา best จริง
        )

        logger.info(f"📄 {filename} → {len(file_results)} chunks")

        if not file_results:
            continue

        file_results.sort(key=lambda x: x["score"])
        best_chunk = file_results[0]

        logger.info(f"   ↳ best score: {best_chunk['score']:.4f}")

        best_per_file.append({
            "filename": filename,
            "best_score": best_chunk["score"]
        })

    if not best_per_file:
        return _ok(
            "ขออภัยค่ะ ดิฉันไม่พบข้อมูลเกี่ยวกับเรื่องนี้ในเอกสารระเบียบของบริษัท"
            if lang == "th"
            else "I apologize, but I couldn't find relevant information in the policy documents.",
            context_used=False,
        )

    # ────────────────────────────────────────────────
    # Phase 2: เลือก Top 3 ไฟล์
    # ────────────────────────────────────────────────
    best_per_file.sort(key=lambda x: x["best_score"])
    top_files = [f["filename"] for f in best_per_file[:3]]

    logger.info(f"🏆 Top 3 Files: {top_files}")

    # ────────────────────────────────────────────────
    # Phase 3: ดึง 5 chunks ต่อไฟล์ (รวมสูงสุด 15)
    # ────────────────────────────────────────────────
    final_results = []

    for filename in top_files:
        deep_results = chroma_service.query_by_filename(
            question=question,
            company=company,
            dept_list=dept_list,
            filename=filename,
            top_k=5,
        )

        logger.info(f"📥 Deep fetch {filename} → {len(deep_results)} chunks")

        final_results.extend(deep_results)

    if not final_results:
        return _ok(
            "ขออภัยค่ะ ดิฉันไม่พบข้อมูลเพิ่มเติมที่เกี่ยวข้อง"
            if lang == "th"
            else "I apologize, but no additional relevant information was found.",
            context_used=False,
        )

    # ────────────────────────────────────────────────
    # Final Global Re-rank (15 chunks)
    # ────────────────────────────────────────────────
    final_results.sort(key=lambda x: x["score"])
    results = final_results[:15]

    logger.info(f"📊 Final selected chunks: {len(results)}")

    # ════════════════════════════════════════════════
    # ด่าน 3 — Context Construction & LLM
    # ════════════════════════════════════════════════
    context_parts = []

    for r in results:
        source = r["metadata"].get("original_filename", "Unknown")
        page = r["metadata"].get("page_number", "-")
        content = r["content"]

        context_parts.append(
            f"[Source: {source} | Page: {page}]\n{content}"
        )

    context_text = "\n\n---\n\n".join(context_parts)

    llm = get_llm_service()
    raw_answer = llm.answer_from_policy(question, context_text)

    if not raw_answer:
        return _ok(
            "ขออภัยค่ะ ระบบไม่สามารถสร้างคำตอบได้ในขณะนี้"
            if lang == "th"
            else "I'm sorry, the system was unable to generate an answer at this time.",
            context_used=True,
        )

    # ════════════════════════════════════════════════
    # ด่าน 4 — Output Guardrail
    # ════════════════════════════════════════════════
    output_safety = guardrail.check_output_safety(question, raw_answer)
    if not output_safety["is_safe"]:
        logger.warning(f"🚫 OUTPUT BLOCKED: {raw_answer[:80]}")
        return _blocked(
            "ขออภัยค่ะ คำตอบที่ระบบสร้างขึ้นไม่ผ่านการตรวจสอบความปลอดภัย"
            if lang == "th"
            else "I apologize, but the generated answer did not pass the safety check."
        )

    nlp_processor = NLPProcessor()
    safe_answer = nlp_processor.redact_sensitive_info(raw_answer)

    # Mask source display
    safe_sources = []
    for src in results:
        meta = src["metadata"].copy()
        col = meta.get("from_col") or f"{company}_{meta.get('department', 'general')}"
        page = meta.get("page_number", "-")

        dept_display = col.split("_", 1)[-1].upper() if "_" in col else col.upper()
        meta["source"] = f"เอกสารระเบียบการ ({dept_display}) หน้า {page}"

        safe_sources.append({
            "content": src["content"],
            "metadata": meta
        })

    logger.info(f"✅ Answer generated | company={company} | lang={lang} | sources={len(safe_sources)}")

    return {
        "status": "success",
        "answer": safe_answer,
        "sources": safe_sources,
        "context_used": True,
    }


# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────
def _ok(message: str, context_used: bool = False) -> dict:
    return {
        "status": "success",
        "answer": message,
        "sources": [],
        "context_used": context_used,
    }


def _blocked(message: str) -> dict:
    return {
        "status": "blocked",
        "answer": message,
        "sources": [],
        "context_used": False,
    }