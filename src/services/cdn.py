import os
import io
import logging
from urllib.parse import urlparse
from typing import Any
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv, find_dotenv
from repository.document_repository import DocumentRepository

load_dotenv(find_dotenv())
logger = logging.getLogger("cdn")


def init_cloudinary() -> None:
    raw_url = os.getenv("CLOUDINARY_URL", "")
    if raw_url:
        try:
            parsed = urlparse(raw_url)
            cloudinary.config(
                cloud_name=parsed.hostname,
                api_key=parsed.username,
                api_secret=parsed.password,
                secure=True
            )
            logger.info("Cloudinary configured from CLOUDINARY_URL")
            return
        except Exception as e:
            logger.warning(f"Error parsing CLOUDINARY_URL: {e}")

    # Fallback to individual env vars
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    if cloud_name and api_key and api_secret:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )
        logger.info("Cloudinary configured from individual env vars")


init_cloudinary()


async def save_document(file_name: str, bytes_data: io.BytesIO, key_id: int | None) -> dict[str, Any] | None:
    if not bytes_data:
        return None

    try:
        clean_name = file_name.replace(".md", ".pdf")
        response = cloudinary.uploader.upload(
            bytes_data,
            public_id=clean_name,
            resource_type="raw"
        )

        url = response.get("url") if isinstance(response, dict) else None
        if not url:
            logger.error("Cloudinary upload failed: no URL in response")
            return None

        res = await DocumentRepository.save_doc_url(url, key_id)
        return {
            "res": res,
            "url": url
        }
    except Exception as e:
        logger.error(f"Error uploading document to Cloudinary: {e}", exc_info=True)
        return None