from google import genai
from google.api_core.exceptions import ServiceUnavailable
from data.db import register_log, update_log
from dotenv import load_dotenv
from services.cdn import save_document
from dto.user import APIKey
from dto.logs import Log
from markdown_pdf import MarkdownPdf, Section
from typing import Any
import time
import json
import os
import io

load_dotenv()
MODEL = os.getenv("MODEL") or "gemini-2.5-flash"

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

client = genai.Client(api_key=os.getenv("API_KEY"))

def count_tokens(content: str) -> Any:
    tokens_count = client.models.count_tokens(
        model=MODEL,
        contents={"text": content}
    )
    return tokens_count

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
        await update_log(Log(id=log_res[0], status="done", response_time=response_time))

async def evaluate_cv_document(content: str, api_key: APIKey) -> dict[str, Any]:
    if not content:
        return {"error": "Invalid CV document content to process"}
    
    start_time = time.time()
    
    try:
        prompt_text = f"{MODEL_ROLE}\n\nEvaluate this CV:\n\n{content}"
        tokens_count = count_tokens(prompt_text)
        
        log_entry = await register_log(Log(api_key_id=api_key.id, tokens_used=getattr(tokens_count, 'total_tokens', 0)))
        log_res = log_entry.get("log") if log_entry else None
        
        response = client.models.generate_content(
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
        company_requirements = f"\n\nCOMPANY REQUIREMENTS: \n{requirements}" if requirements else ""
        prompt_text = f"{MODEL_QUIZ_ROLE}\n\nGenerate a quiz for a person, whose information is:\n\n{data}{company_requirements}"
        
        tokens_count = count_tokens(prompt_text)
        
        log_entry = await register_log(Log(api_key_id=api_key.id, tokens_used=getattr(tokens_count, 'total_tokens', 0)))
        log_res = log_entry.get("log") if log_entry else None
        
        response = client.models.generate_content(
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
        return json.loads(res_txt)

    except ServiceUnavailable:
        return {"error": "Servers are overloaded to generate the quiz"}
        
    except Exception as ex:
        return {"error": str(ex)}
