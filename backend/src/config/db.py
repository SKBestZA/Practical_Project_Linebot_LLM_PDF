# config/db.py
from supabase import create_client, Client
from dotenv import load_dotenv
import psycopg2
import logging
import os

load_dotenv()

logger = logging.getLogger(__name__)

_supabase: Client | None = None


def get_supabase() -> Client:
    """Lazy init Supabase client"""
    global _supabase
    if _supabase is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env")
        _supabase = create_client(url, key)
    return _supabase


def run_sql_file(filepath: str):
    """รัน SQL file ตรงๆ ผ่าน psycopg2"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL must be set in .env")

    if not os.path.exists(filepath):
        logger.warning(f"⚠️ SQL file not found: {filepath}")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        sql = f.read()

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql)
        cur.close()
        conn.close()
        logger.info(f"✅ SQL file executed: {filepath}")
    except Exception as e:
        logger.error(f"❌ SQL execution error: {e}", exc_info=True)
        raise


supabase = get_supabase