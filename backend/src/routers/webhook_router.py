# src/routers/webhook_router.py
from fastapi import APIRouter, Request, HTTPException, Header
from src.services.line_service import get_line_service
from src.services.rag_chat_pipeline import process_chat_workflow
from src.config.db import supabase
import httpx
import hashlib
import hmac
import base64
import os
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["LINE Webhook"])

LINE_API = "https://api.line.me/v2/bot/message"


def _verify_signature(body: bytes, signature: str) -> bool:
    secret = os.getenv("LINE_CHANNEL_SECRET", "")
    hash_ = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    expected = base64.b64encode(hash_).decode()
    return hmac.compare_digest(expected, signature)


async def _reply(reply_token: str, messages: list):
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{LINE_API}/reply",
            headers={"Authorization": f"Bearer {token}"},
            json={"replyToken": reply_token, "messages": messages},
        )


async def _push(line_user_id: str, messages: list):
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{LINE_API}/push",
            headers={"Authorization": f"Bearer {token}"},
            json={"to": line_user_id, "messages": messages},
        )


def _flex_login(line_user_id: str) -> dict:
    liff_url = os.getenv("LIFF_URL", "https://your-liff-url.com/login")
    return {
        "type": "flex",
        "altText": "กรุณาเข้าสู่ระบบก่อนใช้งาน",
        "contents": {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": "🔐 เข้าสู่ระบบ", "weight": "bold", "size": "xl"},
                    {"type": "text", "text": "กรุณาเข้าสู่ระบบเพื่อผูกบัญชีและใช้งาน Policy Chatbot",
                     "wrap": True, "color": "#666666", "size": "sm"},
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": "#00C851",
                        "action": {
                            "type": "uri",
                            "label": "เข้าสู่ระบบ",
                            "uri": f"{liff_url}?lineUserId={line_user_id}",
                        },
                    }
                ],
            },
        },
    }


def _text(text: str) -> dict:
    return {"type": "text", "text": text}


async def _typing_loop(line_user_id: str, stop_event: asyncio.Event):
    """วนส่ง loading indicator ทุก 4 วินาที จนกว่า RAG จะเสร็จ"""
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    async with httpx.AsyncClient() as client:
        while not stop_event.is_set():
            try:
                await client.post(
                    "https://api.line.me/v2/bot/chat/loading/start",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={"chatId": line_user_id, "loadingSeconds": 5},
                )
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=4)
            except asyncio.TimeoutError:
                pass


async def _save_query_log(emp_no: int, topic: str, doc_id: str = None):
    try:
        db = supabase()
        log = db.table("querylog").insert({"empno": emp_no, "topic": topic}).execute()
        if doc_id and log.data:
            query_id = log.data[0]["queryid"]
            db.table("querydetail").insert({
                "queryid": query_id,
                "seq":     1,
                "docid":   doc_id,
            }).execute()
    except Exception as e:
        logger.error(f"❌ save_query_log error: {e}", exc_info=True)


@router.post("/line")
async def line_webhook(
    request: Request,
    x_line_signature: str = Header(...),
):
    body = await request.body()

    if not _verify_signature(body, x_line_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()
    for event in payload.get("events", []):
        await _handle_event(event)

    return {"status": "ok"}


async def _handle_event(event: dict):
    event_type   = event.get("type")
    reply_token  = event.get("replyToken")
    source       = event.get("source", {})
    line_user_id = source.get("userId")

    if not line_user_id:
        return

    if event_type == "message":
        msg_type = event.get("message", {}).get("type")
        if msg_type == "text":
            text = event.get("message", {}).get("text", "").strip()
            await _handle_text(reply_token, line_user_id, text)

    elif event_type == "follow":

        bot_name = os.getenv("BOT_NAME", "Policy Chatbot")

        await _reply(reply_token, [
            _text(
                f"👋 สวัสดีครับ! ยินดีต้อนรับสู่ {bot_name}\n\n"
                f"🤖 ผมคือ AI Assistant ที่ช่วยตอบคำถามเกี่ยวกับนโยบายและระเบียบของบริษัท\n\n"
                f"📋 วิธีใช้งาน\n"
                f"1. กดปุ่มด้านล่างเพื่อเข้าสู่ระบบ\n"
                f"2. ผูกบัญชีพนักงานของคุณ\n"
                f"3. พิมพ์คำถามได้เลย!"
            ),
            _flex_login(line_user_id),
        ])


async def _handle_text(reply_token: str, line_user_id: str, text: str):
    service = get_line_service()
    user = service.check_line_user(line_user_id)

    # SQL กรองแล้ว — is_bound=False หมายถึง ยังไม่ผูก / session หมด / logout
    if not user.is_bound:
        await _reply(reply_token, [
            _text("⚠️ กรุณาเข้าสู่ระบบก่อนใช้งาน"),
            _flex_login(line_user_id),
        ])
        return

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(_typing_loop(line_user_id, stop_typing))

    try:
        emp_result = supabase().table("employee").select(
            "setdepartment(sdpname, setcompany(scpname))"
        ).eq("empno", user.emp_no).execute()

        dept       = emp_result.data[0].get("setdepartment", {}) if emp_result.data else {}
        company    = dept.get("setcompany", {}).get("scpname", "default")
        department = dept.get("sdpname", "all")

        result = await process_chat_workflow(
            question=text,
            company=company,
            department=department,
        )

        stop_typing.set()
        await typing_task

        await _save_query_log(
            emp_no = user.emp_no,
            topic  = text,
            doc_id = result.get("source_doc_id"),
        )

        if result["status"] == "blocked":
            await _push(line_user_id, [_text("⚠️ ไม่สามารถตอบคำถามนี้ได้")])
        else:
            answer = result.get("answer", "ไม่พบข้อมูลที่เกี่ยวข้อง")
            await _push(line_user_id, [_text(answer)])

    except Exception as e:
        stop_typing.set()
        await typing_task
        logger.error(f"❌ RAG error: {e}", exc_info=True)
        await _push(line_user_id, [_text("❌ เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง")])