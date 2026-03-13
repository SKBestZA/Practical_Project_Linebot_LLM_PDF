import chromadb
import os
import logging
from typing import List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from src.utils.embedding_model import get_chroma_embedding_fn
load_dotenv(dotenv_path=Path("/config/.env"))

logger = logging.getLogger(__name__)

current_dir  = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
CHROMA_DB_PATH = os.path.join(project_root, "data", "chromadb")


class ChromaDBService:
    def __init__(self):
        self.host = os.getenv("CHROMA_HOST")
        self.port = int(os.getenv("CHROMA_PORT", 8000))

        self.embedding_fn = get_chroma_embedding_fn()

        if self.host:
            self.client = chromadb.HttpClient(host=self.host, port=self.port)
            logger.info(f"🌐 ChromaDB connected via API: {self.host}:{self.port}")
        else:
            os.makedirs(CHROMA_DB_PATH, exist_ok=True)
            self.client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
            logger.info(f"📦 ChromaDB Storage at: {CHROMA_DB_PATH}")

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────
    def get_collection_name(self, company: str, department: str) -> str:
        company_clean    = str(company).strip().lower()    if company    else "default"
        department_clean = str(department).strip().lower() if department else "all"
        return f"{company_clean}_{department_clean}"

    def _clean_metadata(self, meta: Dict) -> Dict:
        return {
            str(k): (v if isinstance(v, (int, float, bool)) else str(v))
            for k, v in meta.items()
        }

    def _get_or_create_collection(self, name: str):
        return self.client.get_or_create_collection(
            name=name,
            embedding_function=self.embedding_fn,
        )

    def _get_collection(self, name: str):
        return self.client.get_collection(
            name=name,
            embedding_function=self.embedding_fn,
        )

    # ──────────────────────────────────────────────
    # Write
    # ──────────────────────────────────────────────
    def add_documents(self, documents_list: List[Dict[str, Any]]) -> bool:
        try:
            docs_by_col: Dict[str, Dict] = {}

            for doc in documents_list:
                meta     = doc["metadata"]
                company  = meta.get("company", "default")
                dept     = meta.get("department", "all")
                col_name = self.get_collection_name(company, dept)

                if col_name not in docs_by_col:
                    docs_by_col[col_name] = {"ids": [], "contents": [], "metadatas": []}

                docs_by_col[col_name]["ids"].append(str(doc["id"]))
                docs_by_col[col_name]["contents"].append(doc["content"])
                docs_by_col[col_name]["metadatas"].append(self._clean_metadata(meta))

            for col_name, data in docs_by_col.items():
                collection = self._get_or_create_collection(col_name)
                collection.add(
                    ids=data["ids"],
                    documents=data["contents"],
                    metadatas=data["metadatas"],
                )
                logger.info(f"✅ Saved {len(data['ids'])} docs → [{col_name}]")

            return True

        except Exception as e:
            logger.error(f"❌ ChromaDB Add Error: {e}")
            return False

    # ──────────────────────────────────────────────
    # Read
    # ──────────────────────────────────────────────
    def get_unique_filenames(self, company: str, dept_list: List[str]) -> List[str]:
        search_depts = list(set(dept_list + ["all"]))
        filenames = set()

        for dept in search_depts:
            col_name = self.get_collection_name(company, dept)
            try:
                collection = self._get_collection(col_name)
                results = collection.get(include=["metadatas"])
                for meta in results["metadatas"]:
                    fn = meta.get("original_filename")
                    if fn:
                        filenames.add(fn)
            except Exception:
                continue

        logger.info(f"📂 Found {len(filenames)} unique files in [{company}] {search_depts}")
        return list(filenames)

    def query_by_filename(
        self,
        question: str,
        company: str,
        dept_list: List[str],
        filename: str,
        top_k: int = 2,
    ) -> List[Dict[str, Any]]:
        search_depts = list(set(dept_list + ["all"]))
        results = []

        for dept in search_depts:
            col_name = self.get_collection_name(company, dept)
            try:
                collection = self._get_collection(col_name)
                res = collection.query(
                    query_texts=[question],
                    n_results=top_k,
                    where={"original_filename": filename},
                )
                if res["ids"] and res["ids"][0]:
                    for i in range(len(res["ids"][0])):
                        results.append({
                            "id":       res["ids"][0][i],
                            "content":  res["documents"][0][i],
                            "metadata": {
                                **res["metadatas"][0][i],
                                "from_col": col_name,
                            },
                            "score": res["distances"][0][i] if res["distances"] else 1.0,
                        })
            except Exception as e:
                logger.error(f"❌ query_by_filename error [{col_name}]: {e}")
                continue

        # dedup by id หลัง collect ครบ
        seen_ids = set()
        deduped = []
        for r in results:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                deduped.append(r)

        deduped.sort(key=lambda x: x["score"])
        return deduped[:top_k]

    def query_multiple_collections(
        self,
        question: str,
        company: str,
        dept_list: List[str],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        search_depts = list(set(dept_list + ["all"]))
        target_cols  = [self.get_collection_name(company, d) for d in search_depts]
        all_results  = []

        for col_name in target_cols:
            try:
                collection = self._get_collection(col_name)
                results    = collection.query(query_texts=[question], n_results=top_k)

                if results["ids"] and results["ids"][0]:
                    for i in range(len(results["ids"][0])):
                        all_results.append({
                            "id":      results["ids"][0][i],
                            "content": results["documents"][0][i],
                            "metadata": {
                                **results["metadatas"][0][i],
                                "from_col": col_name,
                            },
                            "score": results["distances"][0][i] if results["distances"] else 1.0,
                        })
            except Exception as e:
                logger.error(f"❌ query_multiple_collections error [{col_name}]: {e}")
                continue

        # dedup by id หลัง collect ครบ
        seen_ids = set()
        deduped = []
        for r in all_results:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                deduped.append(r)

        deduped.sort(key=lambda x: x["score"])
        return deduped[:top_k]

    def list_collections(self) -> List[str]:
        try:
            return [col.name for col in self.client.list_collections()]
        except Exception as e:
            logger.error(f"❌ List Collections Error: {e}")
            return []

    # ──────────────────────────────────────────────
    # Delete — 3 ระดับ
    # ──────────────────────────────────────────────
    def delete_document_by_source(
        self, company: str, department: str, source: str
    ) -> bool:
        try:
            col_name   = self.get_collection_name(company, department)
            collection = self._get_collection(col_name)
            results    = collection.get(where={"source": source})

            if not results["ids"]:
                logger.warning(f"⚠️ ไม่พบ source='{source}' ใน [{col_name}]")
                return False

            collection.delete(ids=results["ids"])
            logger.info(f"🗑️ Deleted {len(results['ids'])} chunks | source='{source}' | [{col_name}]")
            return True

        except Exception as e:
            logger.error(f"❌ Delete Document Error: {e}")
            return False

    def delete_document_all_collections(self, company: str, source: str) -> int:
        total_deleted = 0
        prefix = f"{company.strip().lower()}_"

        for col in self.client.list_collections():
            if not col.name.startswith(prefix):
                continue
            try:
                collection = self._get_collection(col.name)
                results    = collection.get(where={"source": source})
                if results["ids"]:
                    collection.delete(ids=results["ids"])
                    total_deleted += len(results["ids"])
                    logger.info(f"🗑️ [{col.name}] deleted {len(results['ids'])} chunks")
            except Exception as e:
                logger.error(f"❌ [{col.name}] Delete Error: {e}")

        logger.info(f"✅ Total deleted: {total_deleted} chunks | source='{source}'")
        return total_deleted

    def reset_company_data(self, company: str) -> bool:
        try:
            prefix = f"{company.strip().lower()}_"
            for col in self.client.list_collections():
                if col.name.startswith(prefix):
                    self.client.delete_collection(name=col.name)
                    logger.info(f"🗑️ Deleted collection: {col.name}")
            return True
        except Exception as e:
            logger.error(f"❌ Reset Company Error: {e}")
            return False

    def reset_all_data(self) -> bool:
        try:
            for col in self.client.list_collections():
                self.client.delete_collection(name=col.name)
            logger.info("🗑️ All ChromaDB data reset.")
            return True
        except Exception as e:
            logger.error(f"❌ Reset All Error: {e}")
            return False


# Singleton
_chroma_instance = None

def get_chroma_service() -> ChromaDBService:
    global _chroma_instance
    if _chroma_instance is None:
        _chroma_instance = ChromaDBService()
    return _chroma_instance