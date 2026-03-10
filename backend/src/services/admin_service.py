# src/services/admin_service.py

from fastapi import HTTPException
from src.config.db import supabase
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)


class AdminService:

    # --------------------------------------------------------
    # 1. Admin Login
    # --------------------------------------------------------
    def admin_login(self, username: str, password: str) -> dict:
        try:
            result = supabase().rpc(
                "fnadminlogin",
                {"pusername": username, "ppassword": password}
            ).execute()

            if not result.data:
                raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาด กรุณาลองใหม่")

            data = result.data[0]

            if not data["res_success"]:
                raise HTTPException(status_code=401, detail=data["res_message"])

            return data

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ admin_login error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาดในการเข้าสู่ระบบ")

    # --------------------------------------------------------
    # 2. Verify Admin Token
    # --------------------------------------------------------
    def verify_admin_token(self, token: str) -> dict:
        try:
            result = supabase().table("admin").select(
                "code, token, expiredate, loginstatus"
            ).eq("token", token).execute()

            if not result.data:
                raise HTTPException(status_code=401, detail="Token ไม่ถูกต้อง")

            admin = result.data[0]

            if admin["loginstatus"] == "inactive":
                raise HTTPException(status_code=401, detail="Token หมดอายุแล้ว")

            if admin["expiredate"] and date.fromisoformat(admin["expiredate"]) < date.today():
                raise HTTPException(status_code=401, detail="Token หมดอายุแล้ว")

            return admin

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ verify_admin_token error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาดในการตรวจสอบ Token")

    # --------------------------------------------------------
    # 3. Dashboard
    # --------------------------------------------------------
    def get_dashboard(self) -> dict:
        try:
            db = supabase()

            # นับเฉพาะ type='query' — ไม่รวม blocked
            total_conv      = db.table("querylog").select("queryid", count="exact").eq("type", "query").execute()
            active_policies = db.table("document").select("docid", count="exact").execute()
            weekly          = db.table("querylog").select("timestamp").eq("type", "query").gte(
                "timestamp", str(date.today() - timedelta(days=7))
            ).execute()

            # ✅ นับ employee ที่ loginstatus = 'active' (ผูก LINE แล้ว session ยังอยู่)
            active_emp = db.table("employee").select("empno", count="exact").eq("loginstatus", "active").execute()

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
                "totalConversations":  total_conv.count or 0,
                "activePolicies":      active_policies.count or 0,
                "weeklyConversations": len(weekly.data or []),
                "activeEmployees":     active_emp.count or 0,  # ✅
                "mostQueriedPolicies": most_queried_list,
            }

        except Exception as e:
            logger.error(f"❌ get_dashboard error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # --------------------------------------------------------
    # 4. Top Queries — กรองเฉพาะ type='query' ไม่รวม blocked
    # --------------------------------------------------------
    def get_top_queries(self, limit: int = 10) -> list:
        try:
            result = (
                supabase()
                .table("querylog")
                .select("topic")
                .eq("type", "query")
                .not_.is_("topic", "null")
                .execute()
            )

            topic_count: dict = {}
            for row in result.data or []:
                topic = row.get("topic", "").strip()
                if topic:
                    topic_count[topic] = topic_count.get(topic, 0) + 1

            total = sum(topic_count.values())
            return sorted(
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

        except Exception as e:
            logger.error(f"❌ get_top_queries error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # --------------------------------------------------------
    # 5. Add Employee (PasswordHash ถูก trigger ตั้งจาก birthday อัตโนมัติ)
    # --------------------------------------------------------
    def add_employee(self, emp_data: dict, admin_code: str) -> dict:
        try:
            supabase().table("employee").insert(emp_data).execute()

            logger.info(f"✅ Added employee EmpNo={emp_data['empno']} by AdminCode={admin_code}")

            return {
                "message": "เพิ่มพนักงานสำเร็จ",
                "empNo":   emp_data["empno"],
            }

        except Exception as e:
            error_msg = str(e).lower()
            if "duplicate key" in error_msg or "unique constraint" in error_msg:
                raise HTTPException(status_code=409, detail=f"รหัสพนักงาน {emp_data['empno']} มีอยู่ในระบบแล้ว")
            logger.error(f"❌ add_employee error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # --------------------------------------------------------
    # 6. Change Password
    # --------------------------------------------------------
    def change_password(self, admin_code: str, current_password: str, new_password: str) -> dict:
        try:
            result = supabase().rpc("fnadminchangepassword", {
                "padmincode":       admin_code,
                "pcurrentpassword": current_password,
                "pnewpassword":     new_password,
            }).execute()

            if not result.data:
                raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาด")

            data = result.data[0]
            if not data["res_success"]:
                raise HTTPException(status_code=400, detail=data["res_message"])

            logger.info(f"✅ Password changed for AdminCode={admin_code}")
            return {"message": "เปลี่ยนรหัสผ่านสำเร็จ"}

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ change_password error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))


# ============================================================
#  Singleton
# ============================================================

_instance = None

def get_admin_service() -> AdminService:
    global _instance
    if _instance is None:
        _instance = AdminService()
    return _instance

admin_service = get_admin_service()