# src/routers/auth_router.py

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from src.services.line_service import line_service
from src.services.admin_service import admin_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


# ============================================================
#  MODELS
# ============================================================

class EmployeeLoginRequest(BaseModel):
    empNo:      int
    password:   str
    lineUserId: str | None = None


class CheckLineRequest(BaseModel):
    lineUserId: str


class UnbindRequest(BaseModel):
    empNo: int  # ✅ แก้จาก loginId: str


class AdminLoginRequest(BaseModel):
    username: str
    password: str


# ============================================================
#  ROUTES
# ============================================================

@router.post("/check-line")
def check_line_user(request: CheckLineRequest):
    if not request.lineUserId:
        raise HTTPException(status_code=400, detail="กรุณาระบุ lineUserId")

    user = line_service.check_line_user(request.lineUserId)

    return {
        "status":   "success",
        "isBound":  user.is_bound,
        "empNo":    user.emp_no,
        "fullName": user.full_name if user.is_bound else None,
        "liffUrl":  line_service.get_liff_login_url() if not user.is_bound else None,
    }


@router.post("/login")
def employee_login(request: EmployeeLoginRequest):
    logger.info(f"📥 Employee login: empNo={request.empNo}, lineUserId={request.lineUserId}")

    if not request.empNo or not request.password:
        raise HTTPException(status_code=400, detail="กรุณากรอก EmpNo และรหัสผ่าน")

    result = line_service.employee_login(
        emp_no       = request.empNo,
        password     = request.password,
        line_user_id = request.lineUserId,
    )

    return {
        "status":  "success",
        "message": result.message,
        "empNo":   result.emp_no,
    }


@router.post("/unbind")
def unbind_line(request: UnbindRequest):
    """ยกเลิกการผูก LINE"""
    logger.info(f"👋 Unbind empNo={request.empNo}")
    return line_service.unbind_line_user(request.empNo)  # ✅ แก้จาก request.loginId


# ============================================================
#  ADMIN AUTH
# ============================================================

@router.post("/admin/login")
def admin_login(request: AdminLoginRequest):
    if not request.username or not request.password:
        raise HTTPException(status_code=400, detail="กรุณากรอก Username และรหัสผ่าน")

    logger.info(f"🔐 Admin login: {request.username}")

    data = admin_service.admin_login(request.username, request.password)

    return {
        "status":    "success",
        "message":   data["res_message"],
        "adminCode": data["res_code"],
        "username":  data["res_username"],
        "token":     data["res_token"],
        "scpName":   data["res_scpname"],
        "scpCode":   data["res_scpcode"], 
    }


@router.post("/admin/logout")
def admin_logout(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header ต้องเป็น Bearer token")

    token = authorization.replace("Bearer ", "").strip()
    logger.info("👋 Admin logout")
    return admin_service.admin_logout(token)