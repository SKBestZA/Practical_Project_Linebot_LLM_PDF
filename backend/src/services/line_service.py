# src/services/line_service.py
from datetime import date
from fastapi import HTTPException
from config.db import supabase
import logging

logger = logging.getLogger(__name__)


# ============================================================
#  MODELS
# ============================================================
class LineUser:
    def __init__(self, data: dict):
        self.is_bound  = data.get("isbound", False)
        self.emp_no    = data.get("empno")
        self.fname     = data.get("fname")
        self.name      = data.get("name")
        self.lname     = data.get("lname")
        self.status    = data.get("status")

    @property
    def full_name(self) -> str:
        if not self.fname:
            return ""
        return f"{self.fname} {self.name} {self.lname}"


class LoginResult:
    def __init__(self, data: dict):
        self.success = data.get("success", False)
        self.message = data.get("message")
        self.emp_no  = data.get("empno")
        self.fname   = data.get("fname")
        self.name    = data.get("name")
        self.lname   = data.get("lname")
        self.token   = data.get("token")


# ============================================================
#  LINE SERVICE
# ============================================================
class LineService:

    # ──────────────────────────────────────────────────────
    #  1. Check LINE User
    #     → เรียก fnCheckLineUser(pLineUserID)
    # ──────────────────────────────────────────────────────
    def check_line_user(self, line_user_id: str) -> LineUser:
        try:
            result = supabase().rpc(
                "fnchecklineuser",
                {"plineuserid": line_user_id}
            ).execute()

            if not result.data:
                return LineUser({"isbound": False})

            return LineUser(result.data[0])

        except Exception as e:
            logger.error(f"❌ check_line_user error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาดในการเช็ค LINE User")

    # ──────────────────────────────────────────────────────
    #  2. Employee Login + LINE Binding
    #     → เรียก fnEmployeeLogin(pLoginID, pPassword, pLineUserID)
    # ──────────────────────────────────────────────────────
    def employee_login(
        self,
        login_id:     str,
        password:     str,
        line_user_id: str = None
    ) -> LoginResult:
        try:
            result = supabase().rpc(
                "fnemployeelogin",
                {
                    "ploginid":    login_id,
                    "ppassword":   password,
                    "plineuserid": line_user_id,
                }
            ).execute()

            if not result.data:
                raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาด กรุณาลองใหม่")

            login_result = LoginResult(result.data[0])

            if not login_result.success:
                raise HTTPException(status_code=401, detail=login_result.message)

            return login_result

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ employee_login error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาดในการเข้าสู่ระบบ")

    # ──────────────────────────────────────────────────────
    #  3. Admin Login
    #     → เรียก fnAdminLogin(pUsername, pPassword)
    # ──────────────────────────────────────────────────────
    def admin_login(self, username: str, password: str) -> dict:
        try:
            result = supabase().rpc(
                "fnadminlogin",
                {
                    "pusername": username,
                    "ppassword": password,
                }
            ).execute()

            if not result.data:
                raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาด กรุณาลองใหม่")

            data = result.data[0]

            if not data["success"]:
                raise HTTPException(status_code=401, detail=data["message"])

            return data

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ admin_login error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาดในการเข้าสู่ระบบ")

    # ──────────────────────────────────────────────────────
    #  4. Verify Token
    #     → query ตาราง Login ตรงๆ
    # ──────────────────────────────────────────────────────
    def verify_token(self, token: str) -> dict:
        try:
            result = supabase().table("login").select(
                "loginid, empno, token, expiredate, status"
            ).eq("token", token).execute()

            if not result.data:
                raise HTTPException(status_code=401, detail="Token ไม่ถูกต้อง")

            login = result.data[0]

            if login["status"] == "INACTIVE":
                raise HTTPException(status_code=401, detail="Token หมดอายุแล้ว")

            if login["expiredate"] and date.fromisoformat(login["expiredate"]) < date.today():
                raise HTTPException(status_code=401, detail="Token หมดอายุแล้ว")

            return login

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ verify_token error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาดในการตรวจสอบ Token")

    # ──────────────────────────────────────────────────────
    #  5. Unbind LINE User
    #     → update ตาราง Login ตรงๆ
    # ──────────────────────────────────────────────────────
    def unbind_line_user(self, login_id: str) -> dict:
        try:
            result = supabase().table("login").update({
                "lineuserid": None,
                "isbound":    False,
                "token":      None,
            }).eq("loginid", login_id).execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="ไม่พบ Login ID")

            return {"success": True, "message": "ยกเลิกการผูก LINE สำเร็จ"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ unbind_line_user error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาดในการยกเลิกการผูก")

    # ──────────────────────────────────────────────────────
    #  6. Get LIFF URL
    # ──────────────────────────────────────────────────────
    def get_liff_login_url(self, line_user_id: str) -> str:
        import os
        liff_url = os.getenv("LIFF_URL", "https://your-liff-url.com/login")
        return f"{liff_url}?lineUserId={line_user_id}"


# Singleton
_instance = None

def get_line_service() -> LineService:
    global _instance
    if _instance is None:
        _instance = LineService()
    return _instance

line_service = get_line_service()