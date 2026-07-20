import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from repository.document_repository import DocumentRepository
import io
from typing import Any

load_dotenv()

async def save_document(file_name: str, bytes_data: io.BytesIO, key_id: int | None) -> dict[str, Any] | None:
    if not bytes_data:
        return None
    
    clean_name = file_name.replace(".md", ".pdf")
    response = cloudinary.uploader.upload(
        bytes_data,
        public_id=clean_name,
        resource_type="raw"
    )
    
    url = response.get("url") if isinstance(response, dict) else None
    if not url:
        return None
        
    res = await DocumentRepository.save_doc_url(url, key_id)
    return {
        "res": res,
        "url": url
    }