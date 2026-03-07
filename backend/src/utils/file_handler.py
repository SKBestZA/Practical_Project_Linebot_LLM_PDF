import os
import shutil
import logging
from pathlib import Path
from fastapi import UploadFile

logger = logging.getLogger(__name__)

BASE_UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "data/uploads"))


def _get_upload_path(company: str, department: str) -> Path:
    """data/uploads/{company}/{department}/"""
    path = BASE_UPLOAD_DIR / company.lower() / department.lower()
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_uploaded_file(file: UploadFile, company: str, department: str) -> str | None:
    try:
        dest_dir  = _get_upload_path(company, department)
        file_path = dest_dir / file.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        logger.info(f"💾 Saved: {file_path}")
        return str(file_path)
    except Exception as e:
        logger.error(f"❌ Save file error: {e}")
        return None


def delete_file(file_path: str) -> bool:
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            logger.info(f"🗑️ Deleted: {file_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Delete file error: {e}")
        return False


def get_file_path(company: str, department: str, filename: str) -> Path | None:
    path = _get_upload_path(company, department) / filename
    return path if path.exists() else None


def list_files(company: str, department: str) -> list[dict]:
    try:
        upload_dir = _get_upload_path(company, department)
        files = []
        for f in sorted(upload_dir.glob("*.pdf"), key=lambda x: x.stat().st_mtime, reverse=True):
            stat = f.stat()
            files.append({
                files.append({
                    "name":         f.name,
                    "size":         stat.st_size,
                    "lastModified": stat.st_mtime * 1000,
                    "department":   department.upper(),
            })

            })
        return files
    except Exception as e:
        logger.error(f"❌ List files error: {e}")
        return []