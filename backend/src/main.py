# main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.config.db import run_sql_file
import logging
import os

logger = logging.getLogger(__name__)


# ============================================================
#  Lifespan - รัน schema ตอน startup
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting up...")

    # root ของโปรเจกต์ใน container คือ /app
    base_dir = os.path.dirname(os.path.dirname(__file__))  
    # จาก src/config -> ขึ้น 2 ชั้น -> /app

    sql_dir = os.path.join(base_dir, "data", "sql")
    run_sql_file(os.path.join(sql_dir, "ddl.sql"))
    run_sql_file(os.path.join(sql_dir, "dml.sql"))

    yield
    logger.info("🛑 Shutting down...")


# ============================================================
#  App
# ============================================================
app = FastAPI(
    title="RAG LINE Bot API",
    version="1.0.0",
    lifespan=lifespan,
)

from src.routers.auth_router import router as auth_router
from src.routers.chat_router import router as chat_router
from src.routers.pdf_router  import router as pdf_router
from src.routers.admin_router import router as admin_router
from src.routers.webhook_router import router as webhook_router
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(pdf_router)
app.include_router(webhook_router)