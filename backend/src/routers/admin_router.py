# src/routers/admin_router.py
from fastapi import APIRouter, HTTPException, Query, Depends, Header
from pydantic import BaseModel
from config.db import supabase
from src.services.line_service import get_line_service
from datetime import date
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


# ============================================================
#  Dependency: ตรวจสอบ Admin Token
# ============================================================
def verify_admin_token(authorization: str = Header(..., description="Bearer <token>")):
    """
    ตรวจสอบ token จาก AdminLogin table
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header ต้องเป็น Bearer token")

    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="ไม่พบ Token")

    try:
        result = supabase().table("adminlogin").select(
            "loginid, admincode, token, expiredate, status"
        ).eq("token", token).execute()

        if not result.data:
            raise HTTPException(status_code=401, detail="Token ไม่ถูกต้อง")

        admin_login = result.data[0]

        if admin_login["status"] == "INACTIVE":
            raise HTTPException(status_code=401, detail="Token หมดอายุแล้ว")

        if admin_login["expiredate"] and date.fromisoformat(admin_login["expiredate"]) < date.today():
            raise HTTPException(status_code=401, detail="Token หมดอายุแล้ว")

        return admin_login

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ verify_admin_token error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาดในการตรวจสอบ Token")


# ============================================================
#  MODELS
# ============================================================
class AddEmployeeRequest(BaseModel):
    empNo:     int
    fname:     str
    name:      str
    lname:     str
    birthday:  date
    sex:       str
    sdpCode:   str
    startDate: date
    password:  str


class UpdateEmployeeRequest(BaseModel):
    fname:    str | None = None
    name:     str | None = None
    lname:    str | None = None
    birthday: date | None = None
    sex:      str | None = None
    sdpCode:  str | None = None
    endDate:  date | None = None


# ============================================================
#  1. DASHBOARD
#     GET /admin/dashboard?scpCode=CP0001
# ============================================================
@router.get("/dashboard")
def get_dashboard(
    scpCode: str = Query(...),
    admin:   dict = Depends(verify_admin_token),
):
    try:
        db = supabase()

        total_conv     = db.table("querylog").select("queryid", count="exact").execute()
        active_policies = db.table("document").select("docid", count="exact").execute()
        weekly         = db.table("querylog").select("timestamp").gte(
            "timestamp", str(date.today().replace(day=date.today().day - 7))
        ).execute()

        most_queried = db.table("querydetail").select("docid, document(name)").execute()
        doc_count: dict = {}
        for row in most_queried.data or []:
            doc_id = row.get("docid")
            if doc_id:
                doc_count[doc_id] = doc_count.get(doc_id, 0) + 1

        most_queried_list = sorted(
            [{"docId": k, "count": v} for k, v in doc_count.items()],
            key=lambda x: x["count"], reverse=True
        )[:5]

        return {
            "status": "success",
            "data": {
                "totalConversations":  total_conv.count or 0,
                "activePolicies":      active_policies.count or 0,
                "weeklyConversations": len(weekly.data or []),
                "mostQueriedPolicies": most_queried_list,
            }
        }

    except Exception as e:
        logger.error(f"❌ get_dashboard error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
#  2. TOP QUERIES
#     GET /admin/top-queries?scpCode=CP0001&limit=10
# ============================================================
@router.get("/top-queries")
def get_top_queries(
    scpCode: str = Query(...),
    limit:   int = Query(10),
    admin:   dict = Depends(verify_admin_token),
):
    try:
        result = supabase().table("querylog").select("topic").not_.is_("topic", "null").execute()

        topic_count: dict = {}
        for row in result.data or []:
            topic = row.get("topic", "").strip()
            if topic:
                topic_count[topic] = topic_count.get(topic, 0) + 1

        total = sum(topic_count.values())
        top_list = sorted(
            [
                {
                    "topic":      k,
                    "count":      v,
                    "percentage": round(v / total * 100, 1) if total else 0,
                }
                for k, v in topic_count.items()
            ],
            key=lambda x: x["count"], reverse=True
        )[:limit]

        return {"status": "success", "data": top_list}

    except Exception as e:
        logger.error(f"❌ get_top_queries error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
#  3. DOCUMENTS (metadata เท่านั้น ไม่ยุ่งกับไฟล์จริง)
#     GET /admin/documents?scpCode=CP0001
# ============================================================
@router.get("/documents")
def get_documents(
    scpCode: str = Query(...),
    admin:   dict = Depends(verify_admin_token),
):
    try:
        result = supabase().table("document").select("*").execute()
        docs = result.data or []

        return {
            "status": "success",
            "data": {
                "totalPolicies": len(docs),
                "documents":     docs,
            }
        }

    except Exception as e:
        logger.error(f"❌ get_documents error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
#  4. EMPLOYEE DATABASE
# ============================================================

# GET /admin/employees?scpCode=CP0001
@router.get("/employees")
def get_employees(
    scpCode: str = Query(...),
    admin:   dict = Depends(verify_admin_token),
):
    try:
        result = supabase().table("employee").select(
            "empno, fname, name, lname, birthday, sex, status, startdate, enddate, "
            "setdepartment(sdpcode, sdpname, scpcode)"
        ).execute()

        employees = result.data or []

        dept_count: dict = {}
        for emp in employees:
            dept = emp.get("setdepartment", {})
            dept_name = dept.get("sdpname", "Unknown") if dept else "Unknown"
            dept_count[dept_name] = dept_count.get(dept_name, 0) + 1

        return {
            "status": "success",
            "data": {
                "totalEmployees": len(employees),
                "byDepartment":   [{"dept": k, "count": v} for k, v in dept_count.items()],
                "employees":      employees,
            }
        }

    except Exception as e:
        logger.error(f"❌ get_employees error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# POST /admin/employees
@router.post("/employees")
def add_employee(
    request: AddEmployeeRequest,
    admin:   dict = Depends(verify_admin_token),
):
    try:
        db = supabase()

        db.table("employee").insert({
            "empno":     request.empNo,
            "fname":     request.fname,
            "name":      request.name,
            "lname":     request.lname,
            "birthday":  str(request.birthday),
            "sex":       request.sex,
            "sdpcode":   request.sdpCode,
            "startdate": str(request.startDate),
        }).execute()

        login_id = f"LG{str(request.empNo).zfill(4)}"
        db.rpc("create_employee_login", {
            "p_login_id": login_id,
            "p_emp_no":   request.empNo,
            "p_password": request.password,
        }).execute()

        logger.info(f"✅ Added employee EmpNo={request.empNo} by AdminCode={admin['admincode']}")

        return {
            "status":  "success",
            "message": "เพิ่มพนักงานสำเร็จ",
            "empNo":   request.empNo,
            "loginId": login_id,
        }

    except Exception as e:
        logger.error(f"❌ add_employee error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# PUT /admin/employees/{empNo}
@router.put("/employees/{empNo}")
def update_employee(
    empNo:   int,
    request: UpdateEmployeeRequest,
    admin:   dict = Depends(verify_admin_token),
):
    try:
        update_data = {k: v for k, v in {
            "fname":     request.fname,
            "name":      request.name,
            "lname":     request.lname,
            "birthday":  str(request.birthday) if request.birthday else None,
            "sex":       request.sex,
            "sdpcode":   request.sdpCode,
            "enddate":   str(request.endDate) if request.endDate else None,
        }.items() if v is not None}

        result = supabase().table("employee").update(update_data).eq("empno", empNo).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="ไม่พบพนักงาน")

        logger.info(f"✅ Updated employee EmpNo={empNo} by AdminCode={admin['admincode']}")
        return {"status": "success", "message": "อัพเดตพนักงานสำเร็จ"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ update_employee error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# DELETE /admin/employees/{empNo}
@router.delete("/employees/{empNo}")
def delete_employee(
    empNo: int,
    admin: dict = Depends(verify_admin_token),
):
    try:
        db = supabase()
        db.table("login").delete().eq("empno", empNo).execute()
        result = db.table("employee").delete().eq("empno", empNo).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="ไม่พบพนักงาน")

        logger.info(f"✅ Deleted employee EmpNo={empNo} by AdminCode={admin['admincode']}")
        return {"status": "success", "message": f"ลบพนักงาน {empNo} สำเร็จ"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ delete_employee error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))