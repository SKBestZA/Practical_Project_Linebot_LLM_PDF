import ollama
import logging
import os
from typing import Dict
from sentence_transformers import SentenceTransformer, util
from utils.embedding_model import get_embedding_model
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GuardrailService:
    def __init__(self, safety_model: str = "llama-guard3:1b"):
        self._safety_model = safety_model
        self._host = os.getenv('OLLAMA_HOST', 'http://ollama:11434')
        self._client = ollama.Client(host=self._host)

        logger.info("⚡ Loading Embedding Model for Scope Check (CPU Mode)...")
        self.embed_model = get_embedding_model()

        self.allowed_topics = [
            "rules regulations policy guidelines compliance standards procedures",
            "กฎระเบียบ นโยบาย ข้อบังคับ แนวปฏิบัติ มาตรฐาน",
            "services request document application process workflow approval",
            "บริการ คำร้อง เอกสาร ขั้นตอน การขออนุมัติ",
            "rights benefits welfare entitlements allowance leave absence",
            "สิทธิ์ สวัสดิการ สิทธิประโยชน์ การลา สิทธิการรักษา",
            "finance payment fee cost budget refund reimbursement salary compensation",
            "การเงิน ค่าธรรมเนียม ค่าใช้จ่าย เงินเดือน การเบิกจ่าย คืนเงิน",
            "accident emergency incident safety insurance risk force majeure",
            "อุบัติเหตุ เหตุฉุกเฉิน ความปลอดภัย ประกัน เหตุสุดวิสัย",
            "SLA service level agreement response time resolution IT support system issue network ticket downtime severity",
            "ข้อตกลงระดับบริการ ระยะเวลาตอบสนอง การแก้ปัญหา ไอที ซัพพอร์ต ระบบ เครือข่าย แจ้งซ่อม ความรุนแรง ระดับวิกฤต",
        ]

        self.topic_categories = [
            "กฎระเบียบ / นโยบาย",
            "กฎระเบียบ / นโยบาย",
            "บริการ / คำร้อง / เอกสาร",
            "บริการ / คำร้อง / เอกสาร",
            "สิทธิ์ / สวัสดิการ / การลา",
            "สิทธิ์ / สวัสดิการ / การลา",
            "การเงิน / เงินเดือน / การเบิกจ่าย",
            "การเงิน / เงินเดือน / การเบิกจ่าย",
            "อุบัติเหตุ / ความปลอดภัย / ประกัน",
            "อุบัติเหตุ / ความปลอดภัย / ประกัน",
            "IT / SLA / ระบบ / แจ้งซ่อม",
            "IT / SLA / ระบบ / แจ้งซ่อม",
        ]

        self.topic_vectors = self.embed_model.encode(self.allowed_topics, convert_to_tensor=True)

        # whitelist คำที่ LLM Guard มักบล็อกผิดในบริบท IT/HR
        self.output_whitelist_patterns = [
            "critical", "severity", "incident", "outage", "downtime", "problem", "issue",
            "วิกฤต", "ปัญหา", "เหตุฉุกเฉิน", "ความรุนแรง", "ระดับ", "แจ้งซ่อม",
            "ประกัน", "อุบัติเหตุ", "เสียชีวิต", "บาดเจ็บ", "ค่าชดเชย",
        ]

        logger.info("✅ Guardrail Service Ready! (Thai/English Supported)")

    # --- Layer 1: Greeting Fast Track ---
    def check_greeting(self, text: str) -> bool:
        greetings = [
            "สวัสดี", "ดีครับ", "ดีค่ะ", "หวัดดี", "ทักทาย", "เฮ้", "ว่าไง", "เทส",
            "hi", "hello", "hey", "morning", "afternoon", "evening", "yo", "sup", "test", "hola"
        ]
        text_clean = text.lower().strip()
        if len(text_clean) > 25:
            return False
        return any(w.lower() in text_clean for w in greetings)

    # --- Extract Topic ---
    def extract_topic(self, question: str) -> str:
        try:
            query_vec = self.embed_model.encode(question, convert_to_tensor=True)
            scores    = util.cos_sim(query_vec, self.topic_vectors)[0]
            best_idx  = int(scores.argmax())
            topic     = self.topic_categories[best_idx]
            logger.info(f"📌 Topic: '{question[:40]}' → '{topic}' (score={float(scores[best_idx]):.4f})")
            return topic
        except Exception as e:
            logger.error(f"❌ extract_topic error: {e}", exc_info=True)
            return question[:50]

    # --- Layer 2: Scope Check ---
    def check_policy_scope(self, user_input: str, threshold: float = 0.25) -> Dict:
        if not user_input.strip():
            return {"in_scope": False, "reason": "Empty Input", "best_idx": 0}
        try:
            query_vec     = self.embed_model.encode(user_input, convert_to_tensor=True)
            cosine_scores = util.cos_sim(query_vec, self.topic_vectors)[0]
            best_score    = float(cosine_scores.max())
            best_idx      = int(cosine_scores.argmax())
            matched_topic = self.allowed_topics[best_idx]
            in_scope      = best_score >= threshold
            logger.info(f"🔍 GUARDRAIL: Input='{user_input[:50]}' | Match='{matched_topic[:40]}' | Score={best_score:.4f}")
            return {
                "in_scope":      in_scope,
                "score":         f"{best_score:.4f}",
                "matched_topic": matched_topic,
                "best_idx":      best_idx,
                "reason":        "เนื้อหาเกี่ยวข้องกับงาน" if in_scope else f"เนื้อหาไม่เกี่ยวข้อง (Score: {best_score:.2f})"
            }
        except Exception as e:
            logger.error(f"❌ Scope Check Error: {e}")
            return {"in_scope": True, "reason": "Error Bypassed", "best_idx": 0}

    # --- Layer 3: Input Safety ---
    def check_input_safety(self, user_input: str) -> Dict:
        try:
            prompt = f"""<|begin_of_text|><|start_header_id|>user<|end_header_id|>

Task: Check if the user question is safe and appropriate.

User question: {user_input}

Rules:
1. If the question asks for hacking, illegal acts, violence, or creating weapons (e.g., bombs), answer 'unsafe'.
2. If the question mixes normal company topics with harmful topics, you MUST answer 'unsafe'.
3. Otherwise, answer 'safe'.

Is this question safe? Answer ONLY 'safe' or 'unsafe'.<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

            response = self._client.generate(model=self._safety_model, prompt=prompt, stream=False)
            result   = response['response'].strip().lower()
            logger.info(f"🛡️ Input Safety: {result[:50]}")
            return {"is_safe": "unsafe" not in result, "details": result}
        except Exception as e:
            logger.error(f"❌ Safety Check Error: {e}")
            return {"is_safe": True, "details": "Error Bypassed"}

    # --- Layer 4: Output Safety (ป้องกันบล็อกมั่ว) ---
    def check_output_safety(self, user_input: str, model_output: str) -> Dict:
        # whitelist pass ก่อน ไม่ต้องเรียก LLM
        output_lower = model_output.lower()
        for pattern in self.output_whitelist_patterns:
            if pattern.lower() in output_lower:
                logger.info(f"✅ Output Whitelist Pass: matched '{pattern}'")
                return {"is_safe": True, "details": "Whitelist Bypass"}

        try:
            prompt = f"""<|begin_of_text|><|start_header_id|>user<|end_header_id|>

Task: Check if the AI response is safe and appropriate for a company policy assistant.

User question: {user_input}
AI response: {model_output}

Context: This is a company HR/IT policy chatbot. Responses about IT incidents, SLA, accidents, insurance, salary, and leave policies are ALL safe and expected.

Rules:
1. Business and IT terms like "critical", "incident", "problem", "outage", "severity", "วิกฤต", "ปัญหา", "อุบัติเหตุ", "ประกัน", "ค่าชดเชย" are SAFE in this context.
2. Only flag as 'unsafe' if it EXPLICITLY promotes violence, illegal acts, or severe toxicity unrelated to company policy.
3. When in doubt, answer 'safe'.

Is this response safe? Answer ONLY 'safe' or 'unsafe'.<|eot_id|><|start_header_id|>assistant<|end_header_id|>"""

            response = self._client.generate(model=self._safety_model, prompt=prompt, stream=False)
            result   = response['response'].strip().lower()
            logger.info(f"🛡️ Output Safety: {result[:50]}")
            return {"is_safe": "unsafe" not in result, "details": result}
        except Exception as e:
            logger.error(f"❌ Output Safety Check Error: {e}")
            return {"is_safe": True, "details": "Error Bypassed"}

    # --- Main Entry Point ---
    def check_comprehensive(self, user_input: str) -> Dict:
        blacklist = [
            "แฮก", "hack", "เจาะระบบ", "ระเบิด", "bomb", "ขโมย", "steal",
            "ฆ่า", "kill", "ทำร้าย", "ลืมคำสั่ง", "ignore previous instructions",
            "bypass", "jailbreak", "prompt injection", "system prompt"
        ]
        if any(bad in user_input.lower() for bad in blacklist):
            logger.warning(f"🚫 Hard Blacklist | Input='{user_input[:50]}'")
            return {
                "allowed":      False,
                "block_reason": "Hard Blacklist",
                "message":      self._get_safety_message(user_input),
                "details":      "Contains strictly prohibited keywords",
                "topic":        "ไม่เกี่ยวข้อง",
            }

        scope = self.check_policy_scope(user_input)
        if not scope["in_scope"]:
            return {
                "allowed":      False,
                "block_reason": "Out of Scope",
                "message":      self._get_rejection_message(user_input),
                "details":      scope,
                "topic":        "ไม่เกี่ยวข้อง",
            }

        # ดึง topic จาก best_idx ที่ scope check คำนวณไว้แล้ว ไม่ encode ซ้ำ
        topic = self.topic_categories[scope["best_idx"]]

        safety = self.check_input_safety(user_input)
        if not safety["is_safe"]:
            return {
                "allowed":      False,
                "block_reason": "Unsafe Content",
                "message":      self._get_safety_message(user_input),
                "details":      safety,
                "topic":        topic,
            }

        return {
            "allowed":      True,
            "block_reason": "Pass",
            "message":      "OK",
            "topic":        topic,
        }

    def _detect_language(self, text: str) -> str:
        thai_chars = sum(1 for c in text if '\u0e00' <= c <= '\u0e7f')
        return 'th' if thai_chars > 0 else 'en'

    def _get_rejection_message(self, user_input: str) -> str:
        lang = self._detect_language(user_input)
        return ("ขอโทษค่ะ ดิฉันตอบได้เฉพาะเรื่องระเบียบการและสวัสดิการของบริษัทเท่านั้นค่ะ"
                if lang == 'th' else
                "I apologize, but I can only answer questions about company policies and benefits.")

    def _get_safety_message(self, user_input: str) -> str:
        lang = self._detect_language(user_input)
        return ("ขอโทษด้วยนะคะ คำถามของคุณมีเนื้อหาที่ไม่เหมาะสมและขัดต่อกฎระเบียบด้านความปลอดภัย"
                if lang == 'th' else
                "I apologize, but your question contains inappropriate content and violates safety guidelines.")


_instance = None

def get_guardrail_service():
    global _instance
    if _instance is None:
        _instance = GuardrailService()
    return _instance