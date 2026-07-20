from data.db import get_db
from typing import Any

class DocumentRepository:
    @staticmethod
    async def save_doc_url(url: str, api_key_id: int | None) -> bool | None:
        if not url or not api_key_id:
            return None

        with get_db() as (conn, cursor):
            cursor.execute("INSERT INTO documents(api_key_id, file_url) VALUES (%s, %s)", [api_key_id, url])    
        return True

    @staticmethod
    async def get_documents(api_key_id: int | None) -> dict[str, list[Any] | None] | None:
        if not api_key_id:
            return None
        
        with get_db() as (conn, cursor):
            cursor.execute("SELECT file_url FROM documents WHERE api_key_id = %s", [api_key_id])
            res = cursor.fetchall()
        return {
            "documents": res
        }
