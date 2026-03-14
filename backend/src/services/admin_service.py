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
                "code, token, expiredate, loginstatus, scpcode"
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
    def get_dashboard(self, scp_code: str) -> dict:
        try:
            db = supabase()

            # ── หา dept codes ของบริษัทนี้ ──
            dept_res   = db.table("setdepartment").select("sdpcode").eq("scpcode", scp_code).execute()
            dept_codes = [d["sdpcode"] for d in dept_res.data or []]

            # ── หา empno ของบริษัทนี้ ──
            emp_res   = db.table("employee").select("empno, loginstatus").in_("sdpcode", dept_codes).execute()
            emp_list  = emp_res.data or []
            emp_nos   = [e["empno"] for e in emp_list]

            total_conv = db.table("querylog").select("queryid", count="exact") \
                .eq("type", "query").in_("empno", emp_nos).execute()

            active_policies = db.table("document").select("docid", count="exact") \
                .eq("scpcode", scp_code).execute()

            active_emp = len([e for e in emp_list if e.get("loginstatus") == "active"])

            # ── Weekly Data — จัดกลุ่มรายวัน 7 วันย้อนหลัง ──
            since = date.today() - timedelta(days=6)
            weekly_res = db.table("querylog").select("timestamp") \
                .eq("type", "query") \
                .in_("empno", emp_nos) \
                .gte("timestamp", str(since)) \
                .execute()

            day_count: dict = {}
            for i in range(7):
                d = since + timedelta(days=i)
                day_count[d.strftime("%a")] = 0  # Mon, Tue, ...

            for row in weekly_res.data or []:
                ts  = row["timestamp"][:10]       # "2026-03-13"
                day = date.fromisoformat(ts).strftime("%a")
                if day in day_count:
                    day_count[day] += 1

            weekly_data = [{"day": k, "conversations": v} for k, v in day_count.items()]

            # ── Most Queried Policies — กรองตาม scpcode ──
            doc_res = db.table("document").select("docid, name").eq("scpcode", scp_code).execute()
            doc_name_map = {d["docid"]: d["name"] for d in doc_res.data or []}
            valid_doc_ids = set(doc_name_map.keys())

            detail_res = db.table("querydetail").select("docid").in_("docid", list(valid_doc_ids)).execute()

            doc_count: dict = {}
            for row in detail_res.data or []:
                doc_id = row.get("docid")
                if doc_id:
                    doc_count[doc_id] = doc_count.get(doc_id, 0) + 1

            most_queried_list = sorted(
                [
                    {
                        "policy":  doc_name_map.get(k, k),
                        "queries": v,
                    }
                    for k, v in doc_count.items()
                ],
                key=lambda x: x["queries"], reverse=True
            )[:5]

            return {
                "totalConversations":  total_conv.count or 0,
                "activePolicies":      active_policies.count or 0,
                "weeklyConversations": len(weekly_res.data or []),
                "activeEmployees":     active_emp,
                "weeklyData":          weekly_data,        # ← array รายวัน
                "mostQueriedPolicies": most_queried_list,
            }

        except Exception as e:
            logger.error(f"❌ get_dashboard error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    # --------------------------------------------------------
    # 4. Top Queries — กรองตาม scpcode
    # --------------------------------------------------------
    def get_top_queries(self, scp_code: str, limit: int = 10) -> list:
        try:
            db = supabase()

            # หา empno ของบริษัทนี้
            dept_res   = db.table("setdepartment").select("sdpcode").eq("scpcode", scp_code).execute()
            dept_codes = [d["sdpcode"] for d in dept_res.data or []]
            emp_res    = db.table("employee").select("empno").in_("sdpcode", dept_codes).execute()
            emp_nos    = [e["empno"] for e in emp_res.data or []]

            result = db.table("querylog").select("topic") \
                .eq("type", "query") \
                .in_("empno", emp_nos) \
                .not_.is_("topic", "null") \
                .execute()

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
    # 5. Add Employee
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