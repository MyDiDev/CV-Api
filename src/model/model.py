from google import genai
from google.api_core.exceptions import ServiceUnavailable
from data.db import register_log, update_log
from dotenv import load_dotenv
from services.cdn import save_document
from dto.user import APIKey
from dto.logs import Log
from markdown_pdf import MarkdownPdf, Section
import time, json, os, io

load_dotenv()
MODEL = os.getenv("MODEL") or "gemini-2.5-flash"

def load_model_roles():
  global MODEL_ROLE, MODEL_QUIZ_ROLE
  
  with open("role.md", "r") as f: 
    MODEL_ROLE = f.read()
    print("[+] - Model role loaded successfully")
    
  with open("quiz_role.md", "r") as f:
    MODEL_QUIZ_ROLE = f.read()
    print("[+] - Model quiz role loaded successfully")

load_model_roles()

client = genai.Client(api_key=os.getenv("API_KEY"))

def count_tokens(content: str):
  tokens_count = client.models.count_tokens(model="gemini-2.5-flash",
    contents={"text":content})
  return tokens_count

async def create_and_save_document(file_name: str, document_content: str, api_key_id: int | None):
  pdf = MarkdownPdf()
  pdf.add_section(Section(document_content, paper_size="A4"))
  
  buf = io.BytesIO()
  pdf.save_bytes(buf)
  buf.seek(0)
  
  res = await save_document(file_name, buf, api_key_id)
  if res == True:
    print("[+] - Document saved successfully")
  
async def update_task_log(log_res, response_time: float):
  if log_res != None:
    res = await update_log(Log(id=log_res[0], status="done", response_time=response_time))
    if res: 
      print("Log Updated Successfully")
  else:
    print("[!]- Invalid log updated")

async def evaluate_cv_document(content: str, api_key: APIKey) -> dict:
  if not content: raise Exception("Invalid CV document content to process")
  global start, end
  
  start = time.time()
  
  try:
    
    tokens_count = count_tokens(f"""
{MODEL_ROLE}

Evalutate this CV:

{content}          
    """)
    
    log_res = await register_log(Log(api_key_id=api_key.id, tokens_used=tokens_count.total_tokens))
    log_res = log_res.get("log") if log_res else None
    
    response = client.models.generate_content(
      model=MODEL,
      contents={"text":f"""
{MODEL_ROLE}

Evalutate this CV:

{content}          
"""},
      config={
        "temperature":0.2,
        "response_mime_type":"application/json"
      }
    )
    end = time.time()
    res_txt = response.text.strip() if response.text is not None else None 
    
    if not res_txt:
      print("[!] - Invalid response error")
      await update_task_log(log_res, end-start)
      return {"error": "Invalid response or JSON from model", "raw":res_txt}

    if res_txt.startswith("```") or res_txt.endswith("```"): 
      res_txt.replace("```", "")
    
    await update_task_log(log_res, end-start)
    data = json.loads(res_txt)
    
    document = data.get("document")
    if not document:
      print("[!] - Invalid document to save, check model response")
      print(data)
      return {"error":"couldn't save PDF report"}
    
    await create_and_save_document(document["file_name"], document["content"], api_key.id)
    
    data.pop("document")
    return data
  
  except ServiceUnavailable as ex:
    print("[!] - Model servers are overloaded, try again later")
    print(ex)
    return {"error":ex}
  
  except Exception as ex:
    print("[!] - Exception while evaluating CV")
    print(ex)
    return {"error":ex}
    
async def generate_quiz(data: str, api_key: APIKey) -> dict[str, str | None | dict | Exception]:
  if not api_key or not api_key.id:
    print("Invalid API key to generate quiz")
    return {"error":"Invalid API key to generate quiz"}
  
  try:
    start = time.time()
    
    content = f"""
{MODEL_QUIZ_ROLE}

Generate a quiz for a person, which information is:

{data}  
    """
    tokens_count = count_tokens(content)
    
    log_res = await register_log(Log(api_key_id=api_key.id, tokens_used=tokens_count.total_tokens))
    log_res = log_res.get("log") if log_res else None
    
    response = client.models.generate_content(
      model=MODEL, 
      contents={
        "text":f"""
{MODEL_QUIZ_ROLE}

Generate a quiz for a person, which information is this:

{data}
""",
      },
      config={
        "temperature":0.2,
        "response_mime_type":"application/json"
      }
    )
    
    end = time.time()
    
    res_txt = response.text.strip() if response.text is not None else None 
    
    if not res_txt:
      print("[!] - Invalid response error")
      await update_task_log(log_res, end-start)
      return {"error": "Invalid response or JSON from model", "raw":res_txt}
    if res_txt.startswith("```") or res_txt.endswith("```"): 
      res_txt.replace("```", "")
    
    await update_task_log(log_res, end-start)
    print(res_txt)
    return json.loads(res_txt)
  except ServiceUnavailable as ex:
    print("[!] - Server are overloaded to generate the quiz")
    print(ex)
    return {'error':ex}
    
  except Exception as ex:
    print("[!] - Exception while generating quiz")
    print(ex)
    return {'error':ex}
