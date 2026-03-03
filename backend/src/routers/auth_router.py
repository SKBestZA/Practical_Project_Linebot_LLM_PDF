# src/routers/auth_router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.services.line_service import line_service
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


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class CheckLineRequest(BaseModel):
    lineUserId: str


class UnbindRequest(BaseModel):
    loginId: str


# ============================================================
#  EMPLOYEE
# ============================================================

@router.post("/check-line")
def check_line_user(request: CheckLineRequest):
    """เช็คว่า LINE userId ผูกกับระบบแล้วหรือยัง"""
    if not request.lineUserId:
        raise HTTPException(status_code=400, detail="กรุณาระบุ lineUserId")

    user = line_service.check_line_user(request.lineUserId)

    return {
        "status":    "success",
        "isBound":   user.is_bound,
        "empNo":     user.emp_no,
        "fullName":  user.full_name if user.is_bound else None,
        "empStatus": user.status    if user.is_bound else None,
        "liffUrl":   line_service.get_liff_login_url(request.lineUserId) if not user.is_bound else None,
    }


@router.post("/login")
def employee_login(request: EmployeeLoginRequest):
    """Employee login ผ่าน LIFF + ผูก LINE"""
    if not request.empNo or not request.password:
        raise HTTPException(status_code=400, detail="กรุณากรอก EmpNo และรหัสผ่าน")

    logger.info(f"🔐 Employee login: EmpNo={request.empNo}")

    result = line_service.employee_login(
        login_id     = str(request.empNo).zfill(6),
        password     = request.password,
        line_user_id = request.lineUserId,
    )

    return {
        "status":  "success",
        "message": result.message,
        "empNo":   result.emp_no,
        "fname":   result.fname,
        "name":    result.name,
        "lname":   result.lname,
        "token":   result.token,
    }


@router.post("/unbind")
def unbind_line(request: UnbindRequest):
    """ยกเลิกการผูก LINE"""
    return line_service.unbind_line_user(request.loginId)


@router.post("/verify-token")
def verify_token(token: str):
    """ตรวจสอบ token"""
    return line_service.verify_token(token)


# ============================================================
#  ADMIN
# ============================================================

@router.post("/admin/login")
def admin_login(request: AdminLoginRequest):
    """Admin login"""
    if not request.username or not request.password:
        raise HTTPException(status_code=400, detail="กรุณากรอก Username และรหัสผ่าน")

    logger.info(f"🔐 Admin login: {request.username}")

    data = line_service.admin_login(request.username, request.password)

    return {
        "status":    "success",
        "message":   data["message"],
        "adminCode": data["admincode"],
        "username":  data["username"],
        "token":     data["token"],
    }