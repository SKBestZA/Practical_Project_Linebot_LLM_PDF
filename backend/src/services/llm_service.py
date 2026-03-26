from groq import Groq
from typing import Optional
import logging
import re
import os
from pathlib import Path


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self, model: str = "qwen/qwen3-32b", api_key: str = None):
        self._model = model
        self._api_key = api_key or os.getenv("GROQ_API_KEY")

        if not self._api_key:
            raise ValueError("❌ ไม่พบ GROQ_API_KEY ใน /config/.env")

        self._client = Groq(api_key=self._api_key)

        self.__default_options = {
            "temperature": 0.1,
            "top_p": 0.95,
            "max_completion_tokens": 1024,
            "reasoning_effort": "none",
            "seed":42,
        }

        logger.info(f"✅ LLMService Connected: Groq | Model: {self._model}")

    def _detect_lang(self, text: str) -> str:
        clean_text = re.sub(r'[\s\d\W_]', '', text)
        if not clean_text:
            return 'en'
        thai_chars = len(re.findall(r'[\u0e00-\u0e7f]', clean_text))
        return 'th' if thai_chars / len(clean_text) > 0.5 else 'en'

    def _build_prompt(self, lang: str, context: str, question: str) -> str:
        if lang == 'th':
            return f"""ตอบเป็นภาษาไทยเท่านั้น ห้ามใช้ภาษาอังกฤษในคำตอบ คุณคือ AI ผู้เชี่ยวชาญด้านการวิเคราะห์เอกสาร มีความแม่นยำสูง และตอบโดยใช้ข้อมูลจากเอกสารที่กำหนดให้เท่านั้น ห้ามใช้ความรู้ภายนอกเด็ดขาด

                    ### กฎเหล็กที่ต้องปฏิบัติอย่างเคร่งครัด:
                    1. ✅ วิเคราะห์ทีละขั้น — ห้ามข้ามกระบวนการคิด
                    2. ✅ คัดลอกตัวเลข ชื่อ และเงื่อนไขจากเอกสาร 100% ห้ามเปลี่ยนแปลง
                    3. ✅ อ้างอิงแหล่งที่มาทุกครั้ง — ระบุหน้า/หัวข้อที่พบข้อมูล
                    4. ✅ หากพบข้อมูลหลายจุด ให้รวบรวมทั้งหมดก่อนตอบ
                    5. ❌ ห้ามคาดเดาหรือเติมข้อมูลที่ไม่มีในเอกสาร
                    6. ❌ ห้ามใช้ความรู้ภายนอกไม่ว่ากรณีใด
                    7. ❌ หากข้อมูลไม่เพียงพอ ให้ตอบว่า: "ขออภัยครับ ไม่พบข้อมูลนี้ในเอกสารที่ให้มา"

                    ---
                    ### กระบวนการคิด (ห้ามข้ามขั้นตอน):

                    ▸ ขั้น 1 [ระบุเจตนาคำถาม]
                    → ผู้ใช้ต้องการทราบอะไร? (ตัวเลข / นโยบาย / ขั้นตอน / วันที่ / เงื่อนไข)

                    ▸ ขั้น 2 [ค้นหาหลักฐานจากเอกสาร]
                    → คัดลอกประโยคที่เกี่ยวข้องโดยตรง (สูงสุด 3 จุด) พร้อมระบุหน้า/หัวข้อ

                    ▸ ขั้น 3 [ตรวจสอบความสมบูรณ์]
                    → หลักฐานตอบคำถามได้ครบถ้วนหรือไม่? มีข้อมูลขัดแย้งกันในเอกสารหรือเปล่า?

                    ▸ ขั้น 4 [ประเมินความมั่นใจ]
                    → 🟢 สูง — พบข้อมูลชัดเจนในเอกสาร
                    → 🟡 ปานกลาง — พบข้อมูลบางส่วน
                    → 🔴 ต่ำ — ข้อมูลไม่เพียงพอ ต้องแจ้งผู้ใช้

                    ▸ ขั้น 5 [สรุปคำตอบสุดท้าย]
                    → เรียบเรียงคำตอบให้กระชับ เข้าใจง่าย พร้อมอ้างอิงแหล่งที่มา

                    ---
                    ### รูปแบบคำตอบที่ต้องใช้:

                    **📋 สรุปคำตอบ:**
                    [คำตอบหลัก — กระชับ ตรงประเด็น]

                    **📎 หลักฐานจากเอกสาร:**
                    - "[ข้อความต้นฉบับ]" (อ้างอิง: หน้า X / หัวข้อ Y)

                    **🎯 ระดับความมั่นใจ:** 🟢 สูง / 🟡 ปานกลาง / 🔴 ต่ำ
                    **⚠️ ข้อสังเกต:** [หากมีข้อจำกัดหรือควรตรวจสอบเพิ่มเติม]

                    ---
                    ### เอกสารอ้างอิง:
                    {context}

                    ---
                    ### คำถามของผู้ใช้: {question}

                    ### ผลการวิเคราะห์และคำตอบ (อ้างอิงจากเอกสารเท่านั้น):"""
        else:
            return f"""You are a highly precise AI Document Analyst. Answer ONLY based on the provided reference documents — never from external knowledge.

            ### STRICT RULES:
            1. ✅ Follow the Thinking Process — no skipping steps
            2. ✅ Copy numbers, names, and conditions verbatim — 0% alteration
            3. ✅ Always cite sources (page number / section heading)
            4. ✅ If information spans multiple sections, consolidate all findings before answering
            5. ❌ Never guess, infer, or fabricate information
            6. ❌ Never use external knowledge under any circumstances
            7. ❌ If data is insufficient, respond: "I apologize, but no relevant information was found in the provided document."

            ---
            ### Thinking Process (Mandatory — no skipping):

            ▸ Step 1 [Identify Intent]
            → What exactly is the user asking for? (Statistics / Policy / Date / Procedure / Condition)

            ▸ Step 2 [Locate Evidence]
            → Copy verbatim sentences from the document (Max 3 points) and note the page/section

            ▸ Step 3 [Verify Completeness]
            → Does the evidence fully answer the question? Are there any contradictions in the document?

            ▸ Step 4 [Assess Confidence]
            → 🟢 High   — Clear, direct answer found in document
            → 🟡 Medium — Partial information found
            → 🔴 Low    — Insufficient data — must notify user

            ▸ Step 5 [Compose Final Answer]
            → Write a concise, accurate response with proper citations

            ---
            ### Required Response Format:

            **📋 Summary Answer:**
            [Main answer — concise and directly on-point]

            **📎 Evidence from Document:**
            - "[Verbatim quote]" (Ref: Page X / Section Y)

            **🎯 Confidence Level:** 🟢 High / 🟡 Medium / 🔴 Low
            **⚠️ Notes:** [Any limitations or recommendations for further verification]

            ---
            ### Reference Document:
            {context}

            ---
            ### User Question: {question}

            ### Analysis and Answer (Strictly based on document):"""

    def answer_from_policy(self, question: str, policy_context: str) -> str:
        try:
            if not question or not question.strip():
                return "กรุณาใส่คำถาม"
            if not policy_context or not policy_context.strip():
                return "ไม่พบข้อมูลในระบบ"

            lang = self._detect_lang(question)
            prompt = self._build_prompt(lang=lang, context=policy_context, question=question)

            completion = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.__default_options["temperature"],
                top_p=self.__default_options["top_p"],
                max_completion_tokens=self.__default_options["max_completion_tokens"],
                reasoning_effort=self.__default_options["reasoning_effort"],
                stream=True,
                stop=None,
            )

            answer = ""
            for chunk in completion:
                answer += chunk.choices[0].delta.content or ""

            answer = answer.strip()

            if self._is_contradictory(answer):
                return self._retry_with_stricter_prompt(question, policy_context)

            return answer if answer else "ไม่สามารถสร้างคำตอบได้"

        except Exception as e:
            logger.error(f"❌ Error: {e}")
            return "เกิดข้อผิดพลาดในการประมวลผล"

    def _is_contradictory(self, answer: str) -> bool:
        """
        ตรวจเฉพาะส่วน 'สรุปคำตอบ' เท่านั้น
        ไม่ให้ตัวเลขใน 'หลักฐานจากเอกสาร' trigger การ retry
        """
        # ดึงเฉพาะส่วน สรุปคำตอบ
        summary_match = re.search(
            r'(?:📋\s*สรุปคำตอบ|📋\s*Summary Answer)[:\s]*(.*?)(?=📎|🎯|⚠️|$)',
            answer,
            re.DOTALL
        )
        if not summary_match:
            return False

        summary = summary_match.group(1).strip()
        no_info_phrases = ["ไม่พบข้อมูล", "ไม่มีข้อมูล", "not found", "no information", "ขออภัย"]
        has_denial = any(phrase in summary.lower() for phrase in no_info_phrases)
        has_details = bool(re.search(r'\d+|บาท|วัน|เดือน', summary))

        return has_denial and has_details and len(answer) > 50

    def _retry_with_stricter_prompt(self, question: str, context: str) -> str:
        strict_prompt = f"Answer only 'Found: [Info]' or 'Not Found'.\nDoc: {context}\nQ: {question}"
        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": strict_prompt}],
                temperature=0.0,
                max_completion_tokens=256,
                stream=False,
                stop=None,
            )
            answer = ""
            for chunk in completion:
                answer += chunk.choices[0].delta.content or ""
            return answer.strip()
        except:
            return "ไม่พบข้อมูล"


# Singleton
_instance = None

def get_llm_service(model: str = "qwen/qwen3-32b", api_key: str = None) -> LLMService:
    global _instance
    if _instance is None:
        _instance = LLMService(model=model, api_key=api_key)
    return _instance