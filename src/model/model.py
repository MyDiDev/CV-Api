from google import genai
from google.api_core.exceptions import ServiceUnavailable
from data.db import register_log, update_log
from dotenv import load_dotenv
from dto.user import APIKey
from dto.logs import Log
from markdown_pdf import MarkdownPdf, Section
import time, json, os, io
from services.cdn import save_document

load_dotenv()
MODEL_ROLE = """"
You are an expert HR analyst and CV evaluator. Read CVs and return ONE valid JSON object.

## YOUR TASK
1. Extract CV information
2. Evaluate against professional hiring criteria
3. Score each criterion 0–100 (strict but fair, like a real recruiter)
4. Provide actionable suggestions
5. Generate a Markdown report in the `document.content` field

## EVALUATION CRITERIA
- structure_and_quality — clarity and organization
- relevant_experience — depth and relevance of work history
- formation_and_education — academic and professional training
- habilities — technical and soft skills
- goals_and_impact — achievements, metrics, and impact
- adaption_for_position — fit for role (if job context provided; else evaluate general employability)

## SCORING RULES
- Each criterion: 0–100
- global_score: balanced/weighted average of all criteria
- Missing info → lower score + explanation in comment
- Do NOT hallucinate experience or skills not present in the CV

## DOCUMENT FIELD (MARKDOWN REPORT)
The `document.content` must be a complete Markdown report containing:
- Candidate Information
- Extracted CV Content (in the CV's original language)
- Professional Experience Summary
- Education and Training
- Skills and Abilities
- Achievements and Impact
- Evaluation by Criterion ← use plain section headings like "Structure & Quality", NOT the JSON key names (no snake_case, no bracketed labels)
- Final Overall Evaluation
- Recommendation

## STRICT MARKDOWN RULES:
- Never write JSON key names (e.g. `structure_and_quality`, `relevant_experience`) anywhere in the document
- Use human-readable headings only (e.g. "## Structure & Quality", "## Relevant Experience")
- Do not repeat content from other sections
- Preserve original language of CV content

## OUTPUT RULES (NON-NEGOTIABLE)
- Return exactly ONE valid JSON object, nothing else
- No text before or after the JSON
- No duplicated keys
- No truncated strings — complete all fields fully
- Properly escape quotes (\") and newlines (\n) inside strings
- No null fields unless info is truly unavailable
- Must be parseable by standard json.loads()

## JSON STRUCTURE
{
  "global_score": number,
  "evaluation": {
    "structure_and_quality": { "score": number, "comment": string },
    "relevant_experience":   { "score": number, "comment": string },
    "formation_and_education": { "score": number, "comment": string },
    "habilities":            { "score": number, "comment": string },
    "goals_and_impact":      { "score": number, "comment": string },
    "adaption_for_position": { "score": number, "comment": string }
  },
  "suggestions": [string, string, string],
  "document": {
    "file_name": string,
    "content": string
  }
}"""

async def create_and_save_document(file_name: str, document_content: str, api_key_id: int | None):
  pdf = MarkdownPdf()
  pdf.add_section(Section(document_content, paper_size="A4"))
  
  buf = io.BytesIO()
  pdf.save_bytes(buf)
  buf.seek(0)
  
  res = await save_document(file_name, buf, api_key_id)
  if res == True:
    print("[+] - Document saved successfully")
  
async def update_task_log(log_res):
  if log_res != None:
    res = await update_log(Log(id=log_res[0], status="done", response_time=int(end-start)))
    if res: 
      print("Log Updated Successfully")
  else:
    print("[!]- Invalid log updated")

async def evaluate_cv_document(content: str, api_key: APIKey) -> dict | None:
  if not content: raise Exception("Invalid CV document content to process")
  global start, end
  
  start = time.time()
  client = genai.Client(api_key=os.getenv("API_KEY"))
  
  try:
    tokens_count = client.models.count_tokens(model="gemini-2.5-flash",
      contents={"text":f"""
{MODEL_ROLE}

Evalutate this CV:

{content}          
      """})
    
    log_res = await register_log(Log(api_key_id=api_key.id, tokens_used=tokens_count.total_tokens))
    log_res = log_res.get("log") if log_res != None else None
    
    response = client.models.generate_content(
      model="gemini-2.5-flash",
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
    res_txt = str(response.text).strip() if response else None 
    
    if not res_txt:
      print("[!] - Invalid response error")
      await update_task_log(log_res)
      return {"error": "Invalid response or JSON from model", "raw":res_txt}

    if res_txt.startswith("```") or res_txt.endswith("```"): res_txt.replace("```", "")
    
    await update_task_log(log_res)
    data = json.loads(res_txt)
    
    document = data.get("document")
    if not document:
      print("[!] - Invalid document to save, check model response")
      print(data)
      return
    
    await create_and_save_document(document["file_name"], document["content"], api_key.id)
    
    data.pop("document")
    return data
  
  except ServiceUnavailable as ex:
    print("[!] - Serveres ar overloaded, try again later")
    return {"error":ex}
  
  except Exception as ex:
    print("[!] - Exception while evaluating CV")
    return {"error":ex}
    
