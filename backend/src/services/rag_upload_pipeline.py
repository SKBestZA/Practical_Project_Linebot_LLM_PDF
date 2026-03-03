from fastapi import UploadFile, HTTPException
import logging
import os

from src.utils.file_handler import save_uploaded_file, delete_file
from src.services.pdf_service import get_pdf_service
from src.services.chromadb_service import get_chroma_service

logger = logging.getLogger(__name__)


def _is_junk_chunk(content: str) -> bool:
    """กรอง chunk ที่เป็น header/footer หรือไม่มีเนื้อหา"""
    content = content.strip()
    if len(content) < 80:
        return True
    return False


async def process_upload_workflow(file: UploadFile, company: str, department: str):
    """
    Pipeline: 1. Save → 2. Extract → 3. Filter → 4. Vector DB
    """
    file_path = None
    try:
        # 1. บันทึกไฟล์
        file_path = save_uploaded_file(file, company, department)
        if not file_path:
            raise ValueError("บันทึกไฟล์ลง Disk ไม่สำเร็จ")

        # 2. ประมวลผล PDF
        pdf_service = get_pdf_service()
        chunks_data = pdf_service.process_pdf(file_path)

        if not chunks_data:
            raise ValueError("อ่านไฟล์สำเร็จแต่ไม่พบเนื้อหาข้อความ (อาจเป็น Scanned PDF)")

        # 3. เตรียม Documents สำหรับ ChromaDB + กรอง junk
        doc_name = os.path.splitext(file.filename)[0]
        documents_for_db = []
        junk_count = 0

        for i, item in enumerate(chunks_data):
            # กรอง junk chunk ออกก่อน ingest
            if _is_junk_chunk(item["content"]):
                junk_count += 1
                continue

            metadata = item["metadata"].copy()
            metadata["company"]           = company
            metadata["department"]        = department
            metadata["original_filename"] = file.filename

            chunk_id = f"{company}_{doc_name}_c{i:04d}"

            documents_for_db.append({
                "content":  item["content"],
                "metadata": metadata,
                "id":       chunk_id,
            })

        logger.info(f"🧹 Filtered {junk_count} junk chunks | Remaining: {len(documents_for_db)}")

        if not documents_for_db:
            raise ValueError("ไม่พบเนื้อหาที่ใช้งานได้หลังกรอง chunk (ไฟล์อาจมีแต่ header/footer)")

        # 4. บันทึกลง ChromaDB
        chroma_service = get_chroma_service()
        success = chroma_service.add_documents(documents_for_db)

        if not success:
            raise RuntimeError("ไม่สามารถบันทึกข้อมูลลง Vector Database ได้")

        logger.info(
            f"✅ [{file.filename}] สำเร็จ: {len(documents_for_db)} chunks "
            f"→ [{company}_{department}]"
        )

        return {
            "status":       "success",
            "filename":     file.filename,
            "company":      company,
            "department":   department,
            "collection":   f"{company}_{department}",
            "chunks_count": len(documents_for_db),
            "message":      f"ประมวลผลและบันทึก {len(documents_for_db)} ส่วนเรียบร้อย (กรอง {junk_count} chunks ที่ไม่มีเนื้อหา)",
        }

    except (ValueError, RuntimeError) as e:
        if file_path:
            delete_file(file_path)
        logger.warning(f"⚠️ Upload rejected [{file.filename}]: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        if file_path:
            delete_file(file_path)
        logger.error(f"❌ Upload Workflow Failed [{file.filename}]: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดภายในระบบ: {str(e)}")