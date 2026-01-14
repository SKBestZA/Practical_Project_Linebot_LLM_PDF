import ollama
from ollama import ChatResponse, GenerateResponse
from typing import Optional, Dict, List
import logging
import re

# ตั้งค่า logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self,model:str="llama3.2"):
        self._model=model#ชื่อ โมเดล

        self.__default_options={
            "temperature": 0.1, #ความแม่นยำ 0.1(มากสุด)-1 (น้อยสุด)
            "top_p": 0.1, #ความหลากหลายในการเลือกคำมาตอบ 0.1(จำกัด)-0.9(อิสระ)
            "num_predict": 512 , #ความยาวคำตอบ tokens
            "repeat_penalty": 1.1 #ลดคำซ้ำ
        }
        self._check_model_exists()
        logger.info(f"self._check_model_exists()")
    def _check_model_exists(self)->None:#ตรวจสอบว่ามีโมเดลกำลังทำงาน
        try:
            models=ollama.list()
            model_names=[m.model for m in models.models]
            if not any(self._model in name for name in model_names):
                raise ValueError(
                    f"ไม่พบโมเดล '{self._model}'\n"
                    f"รันคำสั่ง: ollama pull {self._model}"
                )
        except Exception as e:
            logger.error(f"❌ ตรวจสอบโมเดลไม่สำเร็จ: {e}")
            raise ConnectionError(
                "ไม่สามารถเชื่อมต่อกับ Ollama ได้\n"
                "รันคำสั่ง: ollama serve"
            )
    def _detect_lang(self,text:str)->str:
        ### return 'th'=ไทย 'en' = english ไม่เอาภาษาอื่น###
        clean_text = re.sub(r'[\s\d\W_]', '', text) #ลบช่องว่าง
        #จำนวนตัวอักษรทั้งหมด
        total_chars_cnt = len(clean_text)
        if total_chars_cnt == 0:
            raise ValueError("Language is incorrect: ไม่พบตัวอักษรที่สามารถระบุภาษาได้")
        #นับตัวอักษรภาษาไทย
        thai_chars_cnt = len(re.findall(r'[\u0e00-\u0e7f]', clean_text))
        #นับจำนวนตัวอักษรภาษาอังกฤษ
        english_chars_cnt = len(re.findall(r'[a-zA-Z]', clean_text))
        #ตรวจเช็คภาษาห้ามมีภาษาอื่นๆ กันโมเดลพัง
        if (thai_chars_cnt+english_chars_cnt)<total_chars_cnt:
            raise ValueError("Language is incorrect: พบภาษาที่ไม่รองรับ (รับเฉพาะ TH/EN)")
        #ตรวจเช็คต้องมีไทยมากกว่าร้อยละ50ถึงตอบไทย 
        if thai_chars_cnt / total_chars_cnt > 0.5: 
            return 'th'
        return "en"
    def _build_prompt(self, question: str, context: str, lang: str) -> str:
      if lang == 'th':
        return f"""### คำสั่งสำหรับ AI:
คุณคือ "AI ผู้ช่วยจัดการความรู้องค์กร" ที่ให้ข้อมูลจาก <เอกสารอ้างอิง> เท่านั้น

### กฎข้อบังคับ (ต้องปฏิบัติอย่างเคร่งครัด):

1. **อ่านเอกสารให้ครบถ้วนก่อนตอบ**
   - ตรวจสอบทุกส่วนของเอกสารก่อนตอบว่า "ไม่พบ"
   - ถ้าพบข้อมูล ห้ามตอบว่า "ไม่พบ" โดยเด็ดขาด

2. **ห้ามแปลคำศัพท์ผิด**
   - "annual leave" = "ลาพักร้อน" หรือ "วันหยุดประจำปี"
   - "annual leave" ≠ "วันหยุดปีใหม่" (New Year Holiday)
   - ใช้คำศัพท์ตรงตามเอกสารเท่านั้น

3. **กรณีคำถามไม่ชัดเจน ให้ถามกลับ**
   - ตัวอย่าง: "ลาได้กี่วัน" → ถาม "คุณหมายถึงการลาประเภทใด? (ลาพักร้อน/ลาป่วย)"
   - ห้ามเดาเองหรือตอบว่า "ไม่พบ" ทันที

4. **ห้ามตอบขัดแย้งกัน**
   - ❌ ห้าม: "ไม่พบคำตอบ... อย่างไรก็ตาม... 3 วัน"
   - ✅ ถูกต้อง: "ตามเอกสารระบุว่า... 3 วัน"

5. **ตอบเฉพาะที่ถาม**
   - ถ้าถาม "ขั้นตอน" ให้ตอบเฉพาะขั้นตอน
   - ห้ามใส่ข้อมูลเพิ่มเติมที่ไม่ได้ถาม

6. **กรณีไม่พบข้อมูล**
   - ตรวจสอบให้แน่ใจว่าไม่มีข้อมูลในเอกสารจริงๆ
   - ตอบว่า: "ขออภัยครับ/ค่ะ ไม่พบข้อมูลที่ท่านต้องการในเอกสารอ้างอิง"
---

<เอกสารอ้างอิง>:
{context}

### คำถามจากผู้ใช้งาน:
{question}

### คำตอบ:"""

      else:
        return f"""### SYSTEM INSTRUCTIONS:
You are an "AI Knowledge Management Assistant" that provides information from <Reference Document> ONLY.

### STRICT RULES (Must Follow):

1. **Answer in English ONLY**
   - Use clear, easy-to-understand, and polite language
   - Do not use any other languages in your response

2. **Read and Understand the Question Carefully**
   - Analyze the question thoroughly
   - Be careful with similar but different terms
   - Example: "New Year Holiday" ≠ "Annual Leave"

3. **Answer ONLY Questions Related to the Reference Document**
   - If the question is unrelated, state: "This question is outside the scope of the available document."

4. **Use Information from <Reference Document> ONLY**
   - Do NOT add information from external sources
   - Answer only what is explicitly stated in the document

5. **Do NOT Use External Knowledge or Guess Answers**
   - Do not provide personal opinions
   - Do not interpret or conclude beyond what the document states
   - Do not infer information not present in the document

6. **If Information is Not Found**
   - Reply: "We apologize, but the requested information is not found in the organization's database."
   - Do NOT attempt to answer with uncertain information

---

<Reference Document>:
{context}

### User Question:
{question}

### Answer:"""
    def _validate_input(self, text: str, max_length: int = 10000) -> None:
        if not text or not text.strip():
            raise ValueError("กรุณาใส่คำถาม")
        if len(text) > max_length:
            raise ValueError(f"ข้อความยาวเกินพิกัด ({max_length} ตัวอักษร)")
    def answer_from_policy(self,question: str,policy_context: str,options: Optional[Dict] = None ) -> str:
        """ตอบคำถามจาก Policy (RAG Core Function)"""
        try:
            self._validate_input(question)
            self._validate_input(policy_context, max_length=20000)
            
            # ตรวจจับภาษา (ถ้าไม่ใช่ TH/EN จะดีด ValueError ออกไปทันที)
            lang = self._detect_lang(question)
            logger.info(f"🌐 ตรวจพบภาษา: {lang}")
            
            prompt = self._build_prompt(question, policy_context, lang)
            
            # รวม Options (ถ้ามี)
            gen_options = {**self.__default_options}
            if options:
                gen_options.update(options)
            
            logger.info(f"🔄 กำลังประมวลผลคำถามด้วย {self._model}...")
            
            response: GenerateResponse = ollama.generate(
                model=self._model,
                prompt=prompt,
                options=gen_options
            )
            
            result = response.response.strip()
            return result if result else "ไม่สามารถสรุปคำตอบได้ กรุณาลองใหม่อีกครั้ง"
            
        except ValueError as ve:
            # ส่งต่อ Error เรื่องภาษาหรือ Input ไปให้ Handler ด้านนอก
            raise ve
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return f"เกิดข้อผิดพลาดในการประมวลผล: {str(e)}"
_llm_service_instance: Optional[LLMService] = None
def get_llm_service() -> LLMService:
    global _llm_service_instance
    if _llm_service_instance is None:
        _llm_service_instance = LLMService()
    return _llm_service_instance
