# src/services/line_service.py

from fastapi import HTTPException
from src.config.db import supabase
import logging
import os

logger = logging.getLogger(__name__)


# ============================================================
#  MODELS
# ============================================================

class LineUser:
    def __init__(self, data: dict):
        self.is_bound = data.get("res_isbound", False)
        self.emp_no   = data.get("res_empno")
        self.fname    = data.get("res_fname")
        self.name     = data.get("res_name")
        self.lname    = data.get("res_lname")

    @property
    def full_name(self) -> str:
        if not self.fname:
            return ""
        return f"{self.fname} {self.name} {self.lname}"


class LoginResult:
    def __init__(self, data: dict):
        self.success = data.get("res_success", False)
        self.message = data.get("res_message")
        self.emp_no  = data.get("res_empno")


# ============================================================
#  LINE SERVICE
# ============================================================

class LineService:

    # --------------------------------------------------------
    # 1. Check LINE User
    # --------------------------------------------------------
    def check_line_user(self, line_user_id: str) -> LineUser:
        try:
            result = supabase().rpc(
                "fnchecklineuser",
                {"plineuserid": line_user_id}
            ).execute()

            if not result.data:
                return LineUser({})

            return LineUser(result.data[0])

        except Exception as e:
            logger.error(f"❌ check_line_user error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาดในการเช็ค LINE User")

    # --------------------------------------------------------
    # 2. Employee Login + LINE Binding (LIFF one-time)
    # --------------------------------------------------------
    def employee_login(
        self,
        emp_no: int,
        password: str,
        line_user_id: str = None
    ) -> LoginResult:
        try:
            result = supabase().rpc(
                "fnemployeelogin",
                {
                    "pempno":      emp_no,
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

    # --------------------------------------------------------
    # 3. Unbind LINE User
    # --------------------------------------------------------
    def unbind_line_user(self, emp_no: int) -> dict:
        try:
            result = supabase().table("employee").update({
                "lineuserid":  None,
                "isbound":     False,
                "loginstatus": "inactive",
            }).eq("empno", emp_no).execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="ไม่พบพนักงาน")

            return {"success": True, "message": "ยกเลิกการผูก LINE สำเร็จ"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ unbind_line_user error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาดในการยกเลิกการผูก")

    # --------------------------------------------------------
    # 4. Get LIFF Login URL
    # --------------------------------------------------------
    def get_liff_login_url(self) -> str:
        liff_id = os.getenv("LIFF_ID")
        if not liff_id:
            raise HTTPException(status_code=500, detail="LIFF_ID not configured")
        return f"https://liff.line.me/{liff_id}"


# ============================================================
#  Singleton
# ============================================================

_instance = None

def get_line_service() -> LineService:
    global _instance
    if _instance is None:
        _instance = LineService()
    return _instance

line_service = get_line_service()