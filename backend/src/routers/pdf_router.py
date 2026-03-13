# src/routers/pdf_router.py

from fastapi import APIRouter, UploadFile, File, Query, HTTPException, Depends, Header
from fastapi.responses import FileResponse
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

#employee
# ──────────────────────────────────────────────
# GET /documents/public-download  ← ไม่ต้อง auth
# ──────────────────────────────────────────────
@router.get("/public-download")
def public_download_document(
    company_code: str = Query(...),
    department:   str = Query(...),
    filename:     str = Query(...),
):
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