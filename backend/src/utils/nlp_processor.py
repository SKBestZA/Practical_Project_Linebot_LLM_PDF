import re
import logging
from typing import List, Dict

# ตั้งค่า Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from pythainlp.tokenize import sent_tokenize
    HAS_PYTHAINLP = True
except ImportError:
    HAS_PYTHAINLP = False
    logger.warning("⚠️ ไม่พบ PyThaiNLP ระบบจะใช้การตัดบรรทัดแทน")

class NLPProcessor:
    # ✅ ใช้ 1200 ให้ก้อนใหญ่ขึ้น + overlap 2 ประโยค เพื่อกันข้อมูลแหว่ง
    def __init__(self, chunk_size: int = 1200, overlap_sentences: int = 2):
        self.chunk_size = chunk_size
        self.overlap_sentences = overlap_sentences 

    def process_document(self, pages_text: List[str], doc_name: str = "Unknown") -> List[Dict]:
        all_chunks = []
        for idx, page_content in enumerate(pages_text):
            page_num = idx + 1
            chunks = self._process_page_simple(page_content, page_num, doc_name)
            all_chunks.extend(chunks)
        return all_chunks

    def _process_page_simple(self, text: str, page_num: int, doc_name: str) -> List[Dict]:
        clean_text = self._clean_text(text)
        if not clean_text.strip():
            return []

        # ✅ พระเอกของเรากลับมาแล้ว: ให้ PyThaiNLP ช่วยต่อและตัดประโยคให้เนียนๆ
        sentences = sent_tokenize(clean_text, engine="crfcut") if HAS_PYTHAINLP else clean_text.split('\n')
        
        chunks = []
        current_sentences = []
        current_length = 0

        for sent in sentences:
            sent = sent.strip()
            if not sent: continue

            if current_length + len(sent) > self.chunk_size and current_sentences:
                # เชื่อมประโยคด้วยช่องว่าง (Space) ให้อ่านลื่นไหล
                chunk_text = " ".join(current_sentences)
                chunks.append(self._create_chunk_dict(chunk_text, page_num, doc_name, len(chunks)))
                
                # ทำ Overlap: ยก 2 ประโยคสุดท้ายมาเป็นตัวเชื่อม
                overlap_sents = current_sentences[-self.overlap_sentences:] if len(current_sentences) >= self.overlap_sentences else current_sentences
                
                current_sentences = overlap_sents + [sent]
                current_length = sum(len(s) + 1 for s in current_sentences)
            else:
                current_sentences.append(sent)
                current_length += len(sent) + 1

        if current_sentences:
            chunk_text = " ".join(current_sentences)
            chunks.append(self._create_chunk_dict(chunk_text, page_num, doc_name, len(chunks)))

        return chunks

    def _create_chunk_dict(self, content: str, page_num: int, doc_name: str, chunk_idx: int) -> Dict:
        redacted_content = self.redact_sensitive_info(content.strip())
        lines = redacted_content.split('\n')
        preview_header = lines[0][:100] if lines else "ไม่ระบุหัวข้อ"
        
        return {
            "content": redacted_content, 
            "metadata": {
                "source": doc_name,
                "page_number": page_num,
                "chunk_id": f"{doc_name}_p{page_num}_c{chunk_idx}",
                "header_preview": preview_header,
                "main_header": "ทั่วไป",
                "sub_header": ""
            }
        }

    def _clean_text(self, text: str) -> str:
        text = re.sub(r'\x0c', '', text) 
        
        # 💡 ทริคสำคัญ (PDF Line Un-breaker): 
        # เปลี่ยน \n เดี่ยวๆ (ที่ตัดกลางประโยค) ให้เป็นช่องว่าง 
        # แต่ถ้าเจอ \n\n (ย่อหน้าใหม่จริงๆ) ให้คงไว้เหมือนเดิม
        text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
        
        text = re.sub(r'[ \t]{2,}', ' ', text) 
        text = re.sub(r'\n{3,}', '\n\n', text) 
        return text

    def redact_sensitive_info(self, text: str) -> str:
        text = re.sub(r'\b\d{13}\b|\b\d{1}-\d{4}-\d{5}-\d{2}-\d{1}\b', '[ID_REDACTED]', text)
        text = re.sub(r'\b0[689]\d{1}-?\d{3}-?\d{4}\b', '[PHONE_REDACTED]', text)
        text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[EMAIL_REDACTED]', text)
        return text