# src/routers/admin_router.py

from fastapi import APIRouter, HTTPException, Query, Depends, Header
from pydantic import BaseModel
from src.config.db import supabase
from src.services.admin_service import admin_service
from datetime import date
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


# ============================================================
#  Dependency: ตรวจสอบ Admin Token
# ============================================================
def verify_admin_token(authorization: str = Header(..., description="Bearer <token>")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header ต้องเป็น Bearer token")

    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="ไม่พบ Token")

    return admin_service.verify_admin_token(token)


# ============================================================
#  MODELS
# ============================================================
class AddEmployeeRequest(BaseModel):
    empNo:     int
    title:     str
    fname:     str
    lname:     str
    birthday:  date
    sex:       str
    sdpCode:   str
    startDate: date


class UpdateEmployeeRequest(BaseModel):
    title:    str | None = None
    fname:    str | None = None
    lname:    str | None = None
    birthday: date | None = None
    sex:      str | None = None
    sdpCode:  str | None = None
    endDate:  date | None = None


class ChangePasswordRequest(BaseModel):
    adminCode:       str
    currentPassword: str
    newPassword:     str


class UpdateDocMetaRequest(BaseModel):
    name: str | None = None


# ============================================================
#  1. DASHBOARD
# ============================================================
@router.get("/dashboard")
def get_dashboard(
    scpCode: str = Query(...),
    admin:   dict = Depends(verify_admin_token),
):
    return {"status": "success", "data": admin_service.get_dashboard(scpCode)}  # ← ส่ง scpCode


# ============================================================
#  2. TOP QUERIES
# ============================================================
@router.get("/top-queries")
def get_top_queries(
    scpCode: str = Query(...),
    limit:   int = Query(10),
    admin:   dict = Depends(verify_admin_token),
):
    return {"status": "success", "data": admin_service.get_top_queries(scpCode, limit)}  # ← ส่ง scpCode


# ============================================================
#  3. DOCUMENTS
# ============================================================
@router.get("/documents")
def get_documents(
    scpCode: str = Query(...),
    admin:   dict = Depends(verify_admin_token),
):
    try:
        result = supabase().table("document").select("*").eq("scpcode", scpCode).execute()
        docs = result.data or []
        return {"status": "success", "data": {"totalPolicies": len(docs), "documents": docs}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/documents/{docId}/meta")
def update_doc_meta(
    docId:   str,
    request: UpdateDocMetaRequest,
    admin:   dict = Depends(verify_admin_token),
):
    try:
        update_data = {k: v for k, v in {"name": request.name}.items() if v is not None}
        supabase().table("document").update(update_data).eq("docid", docId).execute()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
#  4. EMPLOYEES
# ============================================================
@router.get("/employees")
def get_employees(
    scpCode: str = Query(...),
    admin:   dict = Depends(verify_admin_token),
):
    try:
        dept_result = supabase().table("setdepartment").select(
            "sdpcode, sdpname"
        ).eq("scpcode", scpCode).execute()
        departments = dept_result.data or []
        dept_codes  = [d["sdpcode"] for d in departments]

        result = supabase().table("employee").select(
            "empno, title, fname, lname, birthday, sex, workstatus, loginstatus, startdate, enddate, sdpcode, "
            "setdepartment(sdpcode, sdpname)"
        ).in_("sdpcode", dept_codes).execute()

        employees = result.data or []

        for emp in employees:
            dept = emp.pop("setdepartment", {}) or {}
            emp["sdpname"] = dept.get("sdpname", "")

        dept_count: dict = {}
        for emp in employees:
            dept_name = emp.get("sdpname", "Unknown")
            dept_count[dept_name] = dept_count.get(dept_name, 0) + 1

        return {
            "status": "success",
            "data": {
                "totalEmployees": len(employees),
                "byDepartment":   [{"dept": k, "count": v} for k, v in dept_count.items()],
                "departments":    departments,
                "employees":      employees,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/employees")
def add_employee(
    request: AddEmployeeRequest,
    admin:   dict = Depends(verify_admin_token),
):
    emp_data = {
        "empno":     request.empNo,
        "title":     request.title,
        "fname":     request.fname,
        "lname":     request.lname,
        "birthday":  str(request.birthday),
        "sex":       request.sex,
        "sdpcode":   request.sdpCode,
        "startdate": str(request.startDate),
    }
    result = admin_service.add_employee(emp_data, admin["code"])
    return {"status": "success", **result}


@router.put("/employees/{empNo}")
def update_employee(
    empNo:   int,
    request: UpdateEmployeeRequest,
    admin:   dict = Depends(verify_admin_token),
):
    try:
        update_data = {k: v for k, v in {
            "title":     request.title,
            "fname":     request.fname,
            "lname":     request.lname,
            "birthday":  str(request.birthday) if request.birthday else None,
            "sex":       request.sex,
            "sdpcode":   request.sdpCode,
            "enddate":   str(request.endDate) if request.endDate else None,
        }.items() if v is not None}

        result = supabase().table("employee").update(update_data).eq("empno", empNo).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="ไม่พบพนักงาน")

        logger.info(f"✅ Updated EmpNo={empNo} by AdminCode={admin['code']}")
        return {"status": "success", "message": "อัพเดตพนักงานสำเร็จ"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/employees/{empNo}")
def delete_employee(
    empNo: int,
    admin: dict = Depends(verify_admin_token),
):
    try:
        result = supabase().table("employee").delete().eq("empno", empNo).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="ไม่พบพนักงาน")

        logger.info(f"✅ Deleted EmpNo={empNo} by AdminCode={admin['code']}")
        return {"status": "success", "message": f"ลบพนักงาน {empNo} สำเร็จ"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
#  5. CHANGE PASSWORD
# ============================================================
@router.put("/password")
def change_password(
    request: ChangePasswordRequest,
    admin:   dict = Depends(verify_admin_token),
):
    if request.adminCode != admin["code"]:
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์เปลี่ยนรหัสผ่านของ admin อื่น")

    result = admin_service.change_password(
        request.adminCode,
        request.currentPassword,
        request.newPassword,
    )
    return {"status": "success", **result}