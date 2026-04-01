# src/routers/pdf_router.py

from fastapi import APIRouter, UploadFile, File, Query, HTTPException, Depends, Header
from fastapi.responses import FileResponse,HTMLResponse
from src.services.rag_upload_pipeline import process_upload_workflow
from src.services.chromadb_service import get_chroma_service
from src.services.admin_service import admin_service
from src.utils.file_handler import get_file_path, list_files, delete_file, BASE_UPLOAD_DIR
from src.config.db import supabase
from datetime import date
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


# ============================================================
#  Dependency
# ============================================================
def verify_admin_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header ต้องเป็น Bearer token")

    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="ไม่พบ Token")

    return admin_service.verify_admin_token(token)


def _require_identity(company_code: str, department: str) -> None:
    if not company_code or not company_code.strip():
        raise HTTPException(status_code=400, detail="กรุณาระบุ company")
    if not department or not department.strip():
        raise HTTPException(status_code=400, detail="กรุณาระบุ department")


# ============================================================
#  Helper: สร้าง DocID
# ============================================================
def _generate_doc_id() -> str:
    result = supabase().table("document").select("docid").order("docid", desc=True).limit(1).execute()
    if not result.data:
        return "D00001"
    last_id = result.data[0]["docid"]
    num = int(last_id[1:]) + 1
    return f"D{str(num).zfill(5)}"


# ============================================================
#  Helper: แปลง ScpCode → ScpName
# ============================================================
def _get_company_name(scp_code: str) -> str:
    try:
        result = supabase().table("setcompany").select("scpname").eq("scpcode", scp_code).single().execute()
        return result.data["scpname"] if result.data else scp_code
    except Exception:
        return scp_code


# ============================================================
#  Helper: แปลง SdpCode → SdpName
# ============================================================
def _get_department_name(sdp_code: str) -> str:
    if sdp_code.lower() == "all":
        return "all"
    try:
        result = supabase().table("setdepartment").select("sdpname").eq("sdpcode", sdp_code).single().execute()
        return result.data["sdpname"] if result.data else sdp_code
    except Exception:
        return sdp_code


# ──────────────────────────────────────────────
# POST /documents/upload
# ──────────────────────────────────────────────
@router.post("/upload")
async def upload_pdf(
    file:         UploadFile = File(...),
    company_code: str = Query(...),
    department:   str = Query(...),
    admin:        dict = Depends(verify_admin_token),
):
    _require_identity(company_code, department)

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="กรุณาอัปโหลดไฟล์ PDF เท่านั้น")

    try:
        company_name = _get_company_name(company_code)
        dept_name    = _get_department_name(department)

        logger.info(f"📥 Upload: {file.filename} → [{company_name}/{dept_name}]")

        result = await process_upload_workflow(
            file=file,
            company=company_name,
            department=dept_name,
        )

        doc_id = _generate_doc_id()
        supabase().table("document").insert({
            "docid":     doc_id,
            "name":      os.path.splitext(file.filename)[0],
            "lastdate":  str(date.today()),
            "admincode": admin["code"],
            "scpcode":   company_code,
            "sdpcode":   None if department.lower() == "all" else department,
        }).execute()

        logger.info(f"✅ Saved to DB: DocID={doc_id} by AdminCode={admin['code']}")

        return {
            "status":  "success",
            "message": "Upload & Processing Complete",
            "docId":   doc_id,
            "data":    result,
        }

    except Exception as e:
        logger.error(f"❌ Upload error [{file.filename}]: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# GET /documents/list
# ──────────────────────────────────────────────
@router.get("/list")
def list_documents(
    company_code: str = Query(...),
    department:   str = Query("all"),
    admin:        dict = Depends(verify_admin_token),
):
    _require_identity(company_code, department)

    company_name = _get_company_name(company_code)
    dept_name    = _get_department_name(department)

    if dept_name == "all":
        all_files = []
        dept_path = BASE_UPLOAD_DIR / company_name.lower()
        if dept_path.exists():
            for dept_dir in dept_path.iterdir():
                if dept_dir.is_dir():
                    all_files.extend(list_files(company_name, dept_dir.name))
        files = all_files
    else:
        files = list_files(company_name, dept_name)

    return {
        "status":     "success",
        "company":    company_name,
        "department": dept_name,
        "total":      len(files),
        "files":      files,
    }


# ──────────────────────────────────────────────
# GET /documents/download
# ──────────────────────────────────────────────
@router.get("/download")
def download_document(
    company_code: str = Query(...),
    department:   str = Query(...),
    filename:     str = Query(...),
    admin:        dict = Depends(verify_admin_token),
):
    _require_identity(company_code, department)

    company_name = _get_company_name(company_code)
    dept_name    = _get_department_name(department)

    file_path = get_file_path(company_name, dept_name, filename)
    if not file_path:
        raise HTTPException(status_code=404, detail=f"ไม่พบไฟล์ '{filename}'")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ──────────────────────────────────────────────
# DELETE /documents/delete
# ──────────────────────────────────────────────
@router.delete("/delete")
def delete_document(
    company_code: str = Query(...),
    department:   str = Query(...),
    filename:     str = Query(...),
    admin:        dict = Depends(verify_admin_token),
):
    _require_identity(company_code, department)

    company_name = _get_company_name(company_code)
    dept_name    = _get_department_name(department)
    source       = os.path.splitext(filename)[0]

    # Check file exists first
    file_path = get_file_path(company_name, dept_name, filename)
    if not file_path:
        raise HTTPException(status_code=404, detail=f"ไม่พบไฟล์ '{filename}'")

    chroma = get_chroma_service()
    chroma.delete_document_by_source(company_name, dept_name, source)

    delete_file(str(file_path))

    supabase().table("document").delete().eq("name", source).execute()

    logger.info(f"🗑️ Deleted [{company_name}/{dept_name}]: {filename} by AdminCode={admin['code']}")

    return {
        "status":  "success",
        "message": f"ลบไฟล์ '{filename}' เรียบร้อยแล้ว",
    }


# ──────────────────────────────────────────────
# PUT /documents/update
# ──────────────────────────────────────────────
@router.put("/update")
async def update_document(
    file:         UploadFile = File(...),
    company_code: str = Query(...),
    department:   str = Query(...),
    old_filename: str = Query(...),
    admin:        dict = Depends(verify_admin_token),
):
    _require_identity(company_code, department)

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="กรุณาอัปโหลดไฟล์ PDF เท่านั้น")

    try:
        company_name = _get_company_name(company_code)
        dept_name    = _get_department_name(department)

        logger.info(f"🔄 Update: {old_filename} → {file.filename} [{company_name}/{dept_name}]")

        old_source = os.path.splitext(old_filename)[0]
        new_source = os.path.splitext(file.filename)[0]

        chroma = get_chroma_service()
        chroma.delete_document_by_source(company_name, dept_name, old_source)

        old_file_path = get_file_path(company_name, dept_name, old_filename)
        if old_file_path:
            delete_file(str(old_file_path))

        result = await process_upload_workflow(
            file=file,
            company=company_name,
            department=dept_name,
        )

        supabase().table("document").update({
            "name":     new_source,
            "lastdate": str(date.today()),
            "sdpcode":  None if department.lower() == "all" else department,
        }).eq("name", old_source).execute()

        logger.info(f"✅ Updated: {old_source} → {new_source} by AdminCode={admin['code']}")

        return {
            "status":       "success",
            "message":      f"อัปเดตไฟล์เรียบร้อย '{old_filename}' → '{file.filename}'",
            "old_filename": old_filename,
            "new_filename": file.filename,
            "data":         result,
        }

    except Exception as e:
        logger.error(f"❌ Update error [{old_filename}]: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

#employee downloadfile
@router.get("/public-download")
def public_download_document(
    company_code: str = Query(...),
    department:   str = Query(...),
    filename:     str = Query(...),
):
    company_name = _get_company_name(company_code)
    dept_name    = _get_department_name(department)

    # ลองหาจาก department จริงก่อน ถ้าไม่เจอลอง all
    file_path = get_file_path(company_name, dept_name, filename)
    if not file_path:
        file_path = get_file_path(company_name, "all", filename)
    if not file_path:
        return HTMLResponse(
            status_code=404,
            content=f"""
<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>เอกสารไม่พร้อมใช้งาน</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: 'Segoe UI', Tahoma, sans-serif;
      background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
      color: #e2e8f0;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
    }}
    .card {{
      background: rgba(30, 41, 59, 0.9);
      border: 1px solid #334155;
      border-radius: 20px;
      padding: 48px 40px;
      text-align: center;
      max-width: 440px;
      width: 90%;
      backdrop-filter: blur(12px);
      box-shadow: 0 25px 50px rgba(0,0,0,0.5);
    }}
    .icon-wrap {{
      width: 80px;
      height: 80px;
      background: linear-gradient(135deg, #991b1b, #ef4444);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 28px;
      font-size: 36px;
      box-shadow: 0 0 30px rgba(239, 68, 68, 0.3);
    }}
    h1 {{
      font-size: 20px;
      font-weight: 700;
      color: #f8fafc;
      margin-bottom: 16px;
      line-height: 1.4;
    }}
    .desc {{
      font-size: 14px;
      color: #94a3b8;
      line-height: 1.8;
      margin-bottom: 24px;
    }}
    .desc strong {{
      color: #fca5a5;
    }}
    .divider {{
      border: none;
      border-top: 1px solid #334155;
      margin: 24px 0;
    }}
    .action-box {{
      background: rgba(153, 27, 27, 0.1);
      border: 1px solid #dc2626;
      border-radius: 12px;
      padding: 16px 20px;
      margin-bottom: 24px;
    }}
    .action-box p {{
      font-size: 13px;
      color: #fca5a5;
      line-height: 1.7;
    }}
    .action-box .line-hint {{
      font-size: 15px;
      font-weight: 600;
      color: #f87171;
      margin-top: 8px;
    }}
    .badge {{
      display: inline-block;
      background: rgba(239, 68, 68, 0.15);
      color: #fca5a5;
      border: 1px solid #991b1b;
      border-radius: 999px;
      padding: 5px 16px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.5px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon-wrap">🚫</div>
    <h1>เอกสาร Policy นี้<br>ไม่พร้อมให้ดาวน์โหลด</h1>
    <p class="desc">
      ไฟล์ <strong>{filename}</strong> อาจถูก<strong>อัปเดต</strong>หรือ<strong>ยกเลิกการใช้งาน</strong><br>
      โดยทีมผู้ดูแลนโยบายขององค์กรแล้ว
    </p>
    <hr class="divider">
    <div class="action-box">
      <p>หากต้องการข้อมูล Policy ล่าสุด<br>กรุณาสอบถามผ่าน</p>
      <div class="line-hint">💬 LINE Chatbot อีกครั้ง</div>
      <p style="margin-top:8px; font-size:12px; color:#94a3b8;">
        ระบบจะค้นหาเอกสารเวอร์ชันปัจจุบันให้อัตโนมัติ
      </p>
    </div>
    <span class="badge">🔒 Access Restricted</span>
  </div>
</body>
</html>
""",
        )

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )