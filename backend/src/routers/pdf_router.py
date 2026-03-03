from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from fastapi.responses import FileResponse
from src.services.rag_upload_pipeline import process_upload_workflow  # ✅
from src.services.chromadb_service import get_chroma_service
from src.utils.file_handler import get_file_path, list_files, delete_file
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


def _require_identity(company: str, department: str) -> None:
    if not company or not company.strip():
        raise HTTPException(status_code=401, detail="กรุณาระบุ company")
    if not department or not department.strip():
        raise HTTPException(status_code=401, detail="กรุณาระบุ department")


# ──────────────────────────────────────────────
# POST /documents/upload
# ──────────────────────────────────────────────
@router.post("/upload")
async def upload_pdf(
    file:       UploadFile = File(...),
    company:    str = Query(..., description="ชื่อบริษัท เช่น scg"),
    department: str = Query(..., description="ชื่อแผนก เช่น hr"),
):
    _require_identity(company, department)

    if file.content_type != "application/pdf":
        logger.warning(f"⚠️ Non-PDF upload attempt: {file.filename}")
        raise HTTPException(status_code=400, detail="กรุณาอัปโหลดไฟล์ PDF เท่านั้น")

    try:
        logger.info(f"📥 Upload: {file.filename} → [{company}/{department}]")
        result = await process_upload_workflow(
            file=file,
            company=company,
            department=department,
        )
        return {"status": "success", "message": "Upload & Processing Complete", "data": result}

    except Exception as e:
        logger.error(f"❌ Upload error [{file.filename}]: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# GET /documents/list
# ──────────────────────────────────────────────
@router.get("/list")
def list_documents(
    company:    str = Query(...),
    department: str = Query("all"),
):
    _require_identity(company, department)

    files = list_files(company, department)
    return {
        "status":     "success",
        "company":    company,
        "department": department,
        "total":      len(files),
        "files":      files,
    }


# ──────────────────────────────────────────────
# GET /documents/download
# ──────────────────────────────────────────────
@router.get("/download")
def download_document(
    company:    str = Query(...),
    department: str = Query(...),
    filename:   str = Query(...),
):
    _require_identity(company, department)

    file_path = get_file_path(company, department, filename)
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
    company:    str = Query(...),
    department: str = Query(...),
    filename:   str = Query(...),
):
    _require_identity(company, department)

    source = os.path.splitext(filename)[0]
    chroma = get_chroma_service()
    chroma.delete_document_by_source(company, department, source)

    file_path = get_file_path(company, department, filename)
    if not file_path:
        raise HTTPException(status_code=404, detail=f"ไม่พบไฟล์ '{filename}'")

    delete_file(str(file_path))
    logger.info(f"🗑️ Deleted [{company}/{department}]: {filename}")

    return {
        "status":     "success",
        "message":    f"ลบไฟล์ '{filename}' เรียบร้อยแล้ว",
        "company":    company,
        "department": department,
    }

# ──────────────────────────────────────────────
# PUT /documents/update
# ──────────────────────────────────────────────
@router.put("/update")
async def update_document(
    file:        UploadFile = File(...),
    company:     str = Query(..., description="ชื่อบริษัท เช่น scg"),
    department:  str = Query(..., description="ชื่อแผนก เช่น hr"),
    old_filename: str = Query(..., description="ชื่อไฟล์เก่าที่ต้องการแทนที่"),
):
    _require_identity(company, department)

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="กรุณาอัปโหลดไฟล์ PDF เท่านั้น")

    try:
        logger.info(f"🔄 Update: {old_filename} → {file.filename} [{company}/{department}]")

        # Step 1: ลบไฟล์เก่าออกจาก ChromaDB
        old_source = os.path.splitext(old_filename)[0]
        chroma = get_chroma_service()
        chroma.delete_document_by_source(company, department, old_source)

        # Step 2: ลบไฟล์เก่าออกจาก disk
        old_file_path = get_file_path(company, department, old_filename)
        if old_file_path:
            delete_file(str(old_file_path))
            logger.info(f"🗑️ Deleted old file: {old_filename}")
        else:
            logger.warning(f"⚠️ Old file not found on disk: {old_filename}")

        # Step 3: upload ไฟล์ใหม่
        result = await process_upload_workflow(
            file=file,
            company=company,
            department=department,
        )

        return {
            "status":       "success",
            "message":      f"อัปเดตไฟล์เรียบร้อย '{old_filename}' → '{file.filename}'",
            "company":      company,
            "department":   department,
            "old_filename": old_filename,
            "new_filename": file.filename,
            "data":         result,
        }

    except Exception as e:
        logger.error(f"❌ Update error [{old_filename}]: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
