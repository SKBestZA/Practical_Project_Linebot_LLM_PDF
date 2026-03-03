from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.services.rag_chat_pipeline import process_chat_workflow
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat & RAG"])


class ChatRequest(BaseModel):
    question:   str
    company:    str
    department: str = "all"


@router.post("/ask")
async def ask_question(request: ChatRequest):
    """ถามคำถามกับ AI (RAG System)"""

    if not request.company or not request.company.strip():
        raise HTTPException(status_code=401, detail="กรุณาระบุ company")

    try:
        logger.info(f"💬 Question: '{request.question[:60]}' | [{request.company}/{request.department}]")

        result = await process_chat_workflow(
            question=request.question,
            company=request.company,
            department=request.department,
        )

        # Guardrail blocked
        if result["status"] == "blocked":
            return result

        # Internal error
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))