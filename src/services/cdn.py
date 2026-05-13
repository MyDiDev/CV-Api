import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from data.db import save_doc_url
import io

load_dotenv()

async def save_document(file_name: str, bytes: io.BytesIO, key_id: int | None) -> dict[str, bool | None | str] | None:
    if not bytes:
        print("[!] - Invalid file bytes to save into CDN")
        return
    
    response = cloudinary.uploader.upload(
        bytes,
        public_id=f"{file_name.replace(".md", ".pdf")}",
        resource_type="raw"
    )
    
    res = await save_doc_url(response["url"], key_id)
    return {
        "res": res,
        "url":response.get("url")
    }