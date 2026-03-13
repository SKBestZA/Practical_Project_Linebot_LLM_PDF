from fastapi import APIRouter, Request, HTTPException, Header, BackgroundTasks
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
from urllib.parse import quote

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["LINE Webhook"])

LINE_API = "https://api.line.me/v2/bot/message"
BASE_URL = os.getenv("BASE_URL", "https://yourserver.com")


# ============================================================
#  Signature Verify
# ============================================================
def _verify_signature(body: bytes, signature: str) -> bool:
    secret   = os.getenv("LINE_CHANNEL_SECRET", "")
    hash_    = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    expected = base64.b64encode(hash_).decode()
    return hmac.compare_digest(expected, signature)


# ============================================================
#  LINE API Helpers
# ============================================================
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


# ============================================================
#  Typing Indicator
# ============================================================
async def _typing_loop(line_user_id: str, stop_event: asyncio.Event):
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    async with httpx.AsyncClient() as client:
        while not stop_event.is_set():
            try:
                await client.post(
                    "https://api.line.me/v2/bot/chat/loading/start",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type":  "application/json",
                    },
                    json={"chatId": line_user_id, "loadingSeconds": 5},
                )
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=4)
            except asyncio.TimeoutError:
                pass


# ============================================================
#  Message Builders
# ============================================================
def _text(text: str) -> dict:
    return {"type": "text", "text": text}


def _flex_login(line_user_id: str) -> dict:
    liff_url = os.getenv("LIFF_URL", "https://your-liff-url.com/login")
    return {
        "type":     "flex",
        "altText":  "กรุณาเข้าสู่ระบบก่อนใช้งาน",
        "contents": {
            "type": "bubble",
            "body": {
                "type":    "box",
                "layout":  "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": "🔐 เข้าสู่ระบบ", "weight": "bold", "size": "xl"},
                    {
                        "type":  "text",
                        "text":  "กรุณาเข้าสู่ระบบเพื่อผูกบัญชีและใช้งาน PoliChatbot",
                        "wrap":  True,
                        "color": "#666666",
                        "size":  "sm",
                    },
                ],
            },
            "footer": {
                "type":   "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type":  "button",
                        "style": "primary",
                        "color": "#00C851",
                        "action": {
                            "type":  "uri",
                            "label": "เข้าสู่ระบบ",
                            "uri":   f"{liff_url}?lineUserId={line_user_id}",
                        },
                    }
                ],
            },
        },
    }


def _build_download_url(company_code: str, department: str, filename: str) -> str:
    return (
        f"{BASE_URL}/documents/public-download"
        f"?company_code={quote(company_code)}"
        f"&department={quote(department)}"
        f"&filename={quote(filename)}"
    )


def _flex_answer(answer: str, sources: list[dict]) -> dict:
    # deduplicate by filename
    seen, unique_sources = set(), []
    for src in sources:
        if src["filename"] not in seen:
            seen.add(src["filename"])
            unique_sources.append(src)

    body_contents = [
        {
            "type":  "text",
            "text":  answer,
            "wrap":  True,
            "size":  "sm",
            "color": "#333333",
        }
    ]

    footer_contents = []
    if unique_sources:
        footer_contents.append({
            "type":   "text",
            "text":   "📎 เอกสารอ้างอิง",
            "size":   "xs",
            "color":  "#888888",
            "margin": "sm",
        })
        for src in unique_sources[:3]:
            label = src["filename"]
            if len(label) > 40:
                label = label[:37] + "..."
            footer_contents.append({
                "type":   "button",
                "height": "sm",
                "margin": "sm",
                "style":  "secondary",
                "action": {
                    "type":  "uri",
                    "label": label,
                    "uri":   src["url"],
                },
            })

    flex = {
        "type":    "flex",
        "altText": answer[:100],
        "contents": {
            "type": "bubble",
            "size": "kilo",
            "body": {
                "type":     "box",
                "layout":   "vertical",
                "contents": body_contents,
            },
        },
    }

    if footer_contents:
        flex["contents"]["footer"] = {
            "type":     "box",
            "layout":   "vertical",
            "spacing":  "sm",
            "contents": footer_contents,
        }

    return flex


# ============================================================
#  Query Log — บันทึก querylog + querydetail ทุกไฟล์
# ============================================================
async def _save_query_log(
    emp_no:    int,
    topic:     str,
    log_type:  str = "query",
    top_files: list[str] = None,
):
    try:
        db = supabase()

        # insert querylog ก่อน — ได้ query_id กลับมา
        log = db.table("querylog").insert({
            "empno": emp_no,
            "topic": topic,
            "type":  log_type,
        }).execute()

        if not log.data:
            return

        query_id = log.data[0]["queryid"]

        # insert querydetail ทุกไฟล์ใน top_files
        if top_files:
            for seq, filename in enumerate(top_files, start=1):
                name = filename.replace(".pdf", "")
                try:
                    doc_res = db.table("document").select("docid").eq("name", name).single().execute()
                    if doc_res.data:
                        db.table("querydetail").insert({
                            "queryid": query_id,
                            "seq":     seq,
                            "docid":   doc_res.data["docid"],
                        }).execute()
                        logger.info(f"📎 querydetail | seq={seq} | {name} → {doc_res.data['docid']}")
                except Exception as e:
                    logger.warning(f"⚠️ DocID lookup failed [{name}]: {e}")

        logger.info(f"📝 Log saved | empno={emp_no} | topic={topic} | type={log_type} | files={top_files}")

    except Exception as e:
        logger.error(f"❌ save_query_log error: {e}", exc_info=True)


# ============================================================
#  Build Sources จาก RAG result
# ============================================================
def _extract_sources(result: dict, company_code: str, department: str) -> list[dict]:
    sources = result.get("sources", [])
    seen, unique = set(), []

    for s in sources:
        filename = s.get("metadata", {}).get("original_filename", "")
        if filename and filename not in seen:
            seen.add(filename)
            unique.append({
                "filename": filename,
                "url": _build_download_url(company_code, department, filename),
            })

    return unique


# ============================================================
#  Webhook Entry Point
# ============================================================
@router.post("/line")
async def line_webhook(
    request:          Request,
    background_tasks: BackgroundTasks,
    x_line_signature: str = Header(...),
):
    body = await request.body()

    if not _verify_signature(body, x_line_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()
    for event in payload.get("events", []):
        background_tasks.add_task(_run_event, event)

    return {"status": "ok"}


def _run_event(event: dict):
    asyncio.run(_handle_event(event))


async def _handle_event(event: dict):
    event_type   = event.get("type")
    source       = event.get("source", {})
    line_user_id = source.get("userId")

    if not line_user_id:
        return

    if event_type == "message":
        msg_type = event.get("message", {}).get("type")
        if msg_type == "text":
            text = event.get("message", {}).get("text", "").strip()
            await _handle_text(line_user_id, text)

    elif event_type == "follow":
        bot_name = os.getenv("BOT_NAME", "PoliChatbot")
        await _push(line_user_id, [
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


async def _handle_text(line_user_id: str, text: str):
    service = get_line_service()
    user    = service.check_line_user(line_user_id)

    if not user.is_bound:
        await _push(line_user_id, [
            _text("⚠️ กรุณาเข้าสู่ระบบก่อนใช้งาน"),
            _flex_login(line_user_id),
        ])
        return

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(_typing_loop(line_user_id, stop_typing))

    try:
        emp_result = supabase().table("employee").select(
            "setdepartment(sdpname, sdpcode, setcompany(scpname, scpcode))"
        ).eq("empno", user.emp_no).execute()

        dept         = emp_result.data[0].get("setdepartment", {}) if emp_result.data else {}
        company_obj  = dept.get("setcompany", {})
        company      = company_obj.get("scpname", "default")
        company_code = company_obj.get("scpcode", "default")
        department   = dept.get("sdpname", "all")
        dept_code    = dept.get("sdpcode", "all")

        result = await process_chat_workflow(
            question=text,
            company=company,
            department=department,
        )

        stop_typing.set()
        await typing_task

        top_files = result.get("top_files", [])

        await _save_query_log(
            emp_no=user.emp_no,
            topic=result.get("topic", "ทั่วไป"),
            log_type="blocked" if result["status"] == "blocked" else "query",
            top_files=top_files if result["status"] != "blocked" else [],
        )

        sources = _extract_sources(result, company_code, dept_code)

        if sources:
            answer = result.get("answer", "ไม่พบข้อมูลที่เกี่ยวข้อง")
            await _push(line_user_id, [_flex_answer(answer, sources)])
        else:
            answer = result.get("answer") or result.get("message", "ไม่พบข้อมูลที่เกี่ยวข้อง")
            await _push(line_user_id, [_text(answer)])

    except Exception as e:
        stop_typing.set()
        await typing_task
        logger.error(f"❌ RAG error: {e}", exc_info=True)
        await _push(line_user_id, [_text("❌ เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง")])