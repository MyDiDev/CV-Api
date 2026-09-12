import hashlib
import json
import os
import io
import time
from typing import Any
from dotenv import load_dotenv, find_dotenv
from markdown_pdf import MarkdownPdf, Section
from google.api_core.exceptions import ServiceUnavailable
import logging

from dto.user import APIKey
from dto.logs import Log
from repository.log_repository import LogRepository
from services.cdn import save_document
from services.gemini_balancer import gemini_balancer
from services.redis_service import RedisService

load_dotenv(find_dotenv())
logger = logging.getLogger("model")
MODEL = os.getenv("MODEL") or "gemini-2.5-flash"
AI_CACHE_TTL = int(os.getenv("AI_CACHE_TTL", "86400"))

MODEL_ROLE = ""
MODEL_QUIZ_ROLE = ""

def load_model_roles() -> None:
    global MODEL_ROLE, MODEL_QUIZ_ROLE
    if os.path.exists("role.md"):
        with open("role.md", "r", encoding="utf-8") as f: 
            MODEL_ROLE = f.read()
    if os.path.exists("quiz_role.md"):
        with open("quiz_role.md", "r", encoding="utf-8") as f:
            MODEL_QUIZ_ROLE = f.read()

load_model_roles()

async def count_tokens(content: str) -> Any:
    return await gemini_balancer.count_tokens(
        model=MODEL,
        contents={"text": content}
    )

async def create_and_save_document(file_name: str, document_content: str, api_key_id: int | None) -> str | None:
    pdf = MarkdownPdf()
    pdf.add_section(Section(document_content, paper_size="A4"))
    
    buf = io.BytesIO()
    pdf.save_bytes(buf)
    buf.seek(0)
    
    res = await save_document(file_name, buf, api_key_id)
    if isinstance(res, dict) and res.get("res"):
        return str(res.get("url"))
    return None

async def update_task_log(log_res: Any, response_time: float) -> None:
    if log_res and isinstance(log_res, (list, tuple)) and len(log_res) > 0:
        await LogRepository.update_log(Log(id=log_res[0], status="done", response_time=response_time))

async def evaluate_cv_document(content: str, api_key: APIKey) -> dict[str, Any]:
    if not content:
        return {"error": "Invalid CV document content to process"}
    
    start_time = time.time()
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    cache_key = f"cache:ai:cv:{content_hash}"
    
    try:
        cached_data = await RedisService.get_json(cache_key)
        if cached_data is not None and isinstance(cached_data, dict):
            log_entry = await LogRepository.register_log(Log(api_key_id=api_key.id, tokens_used=0))
            log_res = log_entry.get("log") if log_entry else None
            await update_task_log(log_res, time.time() - start_time)
            return cached_data

        prompt_text = f"{MODEL_ROLE}\n\nEvaluate this CV:\n\n{content}"
        tokens_count = await count_tokens(prompt_text)
        
        log_entry = await LogRepository.register_log(Log(api_key_id=api_key.id, tokens_used=getattr(tokens_count, 'total_tokens', 0)))
        log_res = log_entry.get("log") if log_entry else None
        
        response = await gemini_balancer.generate_content(
            model=MODEL,
            contents={"text": prompt_text},
            config={
                "temperature": 0.2,
                "response_mime_type": "application/json"
            }
        )
        end_time = time.time()
        res_txt = response.text.strip() if response and response.text is not None else None 
        
        if not res_txt:
            await update_task_log(log_res, end_time - start_time)
            return {"error": "Invalid response or JSON from model"}

        if res_txt.startswith("```json"):
            res_txt = res_txt[7:]
        elif res_txt.startswith("```"):
            res_txt = res_txt[3:]
        if res_txt.endswith("```"):
            res_txt = res_txt[:-3]
        res_txt = res_txt.strip()
        
        await update_task_log(log_res, end_time - start_time)
        data = json.loads(res_txt)
        
        document = data.get("document")
        if not document or not isinstance(document, dict) or "file_name" not in document or "content" not in document:
            return {"error": "couldn't save PDF report due to invalid document format"}
        
        res_url = await create_and_save_document(document["file_name"], document["content"], api_key.id)
        data["document"] = res_url
        await RedisService.set_json(cache_key, data, ttl=AI_CACHE_TTL)
        return data
      
    except ServiceUnavailable:
        return {"error": "Model servers are overloaded, try again later"}
      
    except Exception as ex:
        return {"error": str(ex)}
        
async def generate_quiz(data: str, api_key: APIKey, requirements: str) -> dict[str, Any]:
    if not api_key or not api_key.id:
        return {"error": "Invalid API key to generate quiz"}
      
    try:
        start_time = time.time()
        prompt_hash = hashlib.sha256(f"{data}::{requirements}".encode("utf-8")).hexdigest()
        cache_key = f"cache:ai:quiz:{prompt_hash}"

        cached_data = await RedisService.get_json(cache_key)
        if cached_data is not None and isinstance(cached_data, dict):
            log_entry = await LogRepository.register_log(Log(api_key_id=api_key.id, tokens_used=0))
            log_res = log_entry.get("log") if log_entry else None
            await update_task_log(log_res, time.time() - start_time)
            return cached_data

        company_requirements = f"\n\nCOMPANY REQUIREMENTS: \n{requirements}" if requirements else ""
        prompt_text = f"{MODEL_QUIZ_ROLE}\n\nGenerate a quiz for a person, whose information is:\n\n{data}{company_requirements}"
        
        tokens_count = await count_tokens(prompt_text)
        
        log_entry = await LogRepository.register_log(Log(api_key_id=api_key.id, tokens_used=getattr(tokens_count, 'total_tokens', 0)))
        log_res = log_entry.get("log") if log_entry else None
        
        response = await gemini_balancer.generate_content(
            model=MODEL, 
            contents={"text": prompt_text},
            config={
                "temperature": 0.2,
                "response_mime_type": "application/json"
            }
        )
        
        end_time = time.time()
        res_txt = response.text.strip() if response and response.text is not None else None 
        
        if not res_txt:
            await update_task_log(log_res, end_time - start_time)
            return {"error": "Invalid response or JSON from model"}

        if res_txt.startswith("```json"):
            res_txt = res_txt[7:]
        elif res_txt.startswith("```"):
            res_txt = res_txt[3:]
        if res_txt.endswith("```"):
            res_txt = res_txt[:-3]
        res_txt = res_txt.strip()
        
        await update_task_log(log_res, end_time - start_time)
        parsed_json = json.loads(res_txt)
        await RedisService.set_json(cache_key, parsed_json, ttl=AI_CACHE_TTL)
        return parsed_json

    except ServiceUnavailable:
        return {"error": "Servers are overloaded to generate the quiz"}
        
    except Exception as ex:
        return {"error": str(ex)}
