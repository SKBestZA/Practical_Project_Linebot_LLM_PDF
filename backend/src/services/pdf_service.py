import fitz  # PyMuPDF
from typing import List, Dict, Any
from datetime import datetime, timezone
import logging
import os

from src.utils.nlp_processor import NLPProcessor

logger = logging.getLogger(__name__)


class PDFService:
    def __init__(self):
        self.chunk_size = 1200
        self.overlap_sentences = 1

        self.nlp_processor = NLPProcessor(
            chunk_size=self.chunk_size,
            overlap_sentences=self.overlap_sentences,
        )

    def process_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(file_path):
            logger.error(f"❌ ไม่พบไฟล์: {file_path}")
            return []

        try:
            doc = fitz.open(file_path)
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            total_pages = len(doc)
            uploaded_at = datetime.now(timezone.utc).isoformat()

            logger.info(f"📂 กำลังอ่านไฟล์: {file_name} (รวม {total_pages} หน้า)")

            pages_text = []
            for page in doc:
                text = page.get_text("text")
                pages_text.append(text if text.strip() else "")
            doc.close()

            nlp_results = self.nlp_processor.process_document(
                pages_text,
                doc_name=file_name,
            )

            formatted_chunks = []
            for i, item in enumerate(nlp_results):
                content = item["content"]

                # ✅ เฉพาะ 3 fields ที่ต้องการ — ชัดเจน ไม่มีขยะ
                metadata = {
                    "source":      file_name,
                    "page_number": item["metadata"].get("page_number", 0),
                    "uploaded_at": uploaded_at,  # เหมือนกันทุก chunk ของไฟล์นี้
                }

                formatted_chunks.append({
                    "content": content,
                    "metadata": metadata,
                })

            logger.info(f"✅ [{file_name}] สำเร็จ! {len(formatted_chunks)} chunks | {total_pages} หน้า")
            return formatted_chunks

        except Exception as e:
            logger.error(f"❌ PDFService Error: {e}", exc_info=True)
            return []


# --- Singleton ---
_service_instance = PDFService()


def get_pdf_service() -> PDFService:
    return _service_instance


def extract_text_from_pdf(file_path: str) -> List[str]:
    return [item["content"] for item in get_pdf_service().process_pdf(file_path)]