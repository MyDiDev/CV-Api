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
MODEL_ROLE = """You are an expert HR analyst and CV evaluator. Read CVs and return ONE valid JSON object.

## YOUR TASK
1. Extract CV information
2. Evaluate against professional hiring criteria
3. Score each criterion 0–100 (strict but fair, like a real recruiter)
4. Provide actionable suggestions
5. Generate a clean Markdown report in the document.content field

## LANGUAGE RULE (NON-NEGOTIABLE)
- Detect the language of the input CV automatically
- Every field in the JSON output must be written in that same language: all comments, suggestions, document content, and file_name
- This includes: evaluation comments, suggestions array, and the full document.content Markdown report
- Do NOT translate or switch languages under any circumstance
- If the CV is in Spanish, respond entirely in Spanish. If English, entirely in English. And so on for any language.

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
- Do NOT hallucinate experience or skills not in the CV

## DOCUMENT FIELD — MARKDOWN REPORT

The document.content must be a complete, clean Markdown report ready for a Markdown-to-PDF converter.

### REQUIRED SECTIONS (use exactly these headings, in this order):

# CV Evaluation: [Candidate Full Name]

## Candidate Information
## Professional Experience
## Education & Training
## Skills & Abilities
## Achievements & Impact
---
## Evaluation
### Structure & Quality
### Relevant Experience
### Education & Training
### Skills & Abilities
### Achievements & Impact
### Position Fit
---
## Overall Evaluation
## Recommendation
## Improvement Suggestions

IMPORTANT: Translate the section headings listed above into the detected CV language. For example, if the CV is in Spanish, use headings like ## Información del Candidato, ## Experiencia Profesional, etc. Always match the headings language to the CV language.

### STRICT MARKDOWN RULES

Headings:
- Use # for the document title only
- Use ## for main sections
- Use ### for evaluation sub-sections
- NEVER number section headings (no 1. 2. 3. before section titles)
- NEVER append JSON key names to headings
- Forbidden words in headings: structure_and_quality, relevant_experience, formation_and_education, habilities, goals_and_impact, adaption_for_position
- NEVER write any snake_case identifier anywhere in the document

Evaluation sub-sections format (strictly follow this pattern for every ### section):

### Structure & Quality
**Score: XX/100**

[Your evaluation comment here as a plain paragraph.]

Rules for evaluation sub-sections:
- Always place the score as **Score: XX/100** on its own line immediately after the ### heading
- The label Score may also be translated to match the CV language (e.g. Puntuación: XX/100 in Spanish)
- Score must match the corresponding JSON evaluation score exactly
- Comment must be a plain paragraph — no sub-bullets, no nested lists inside evaluation sections

Lists:
- Use bullet lists (-) for skills, technologies, and experience items
- Use numbered lists (1.) ONLY for the Improvement Suggestions section
- Do NOT use numbered lists for evaluation sections or anywhere else

Separators:
- Place --- (horizontal rule) before the ## Evaluation section and before ## Overall Evaluation
- Do NOT add --- anywhere else in the document

Typography and formatting:
- Bold (**text**) only for score lines and candidate name in the header section
- No italics unless quoting a job title
- No tables
- No HTML tags
- No code blocks (no triple backticks) anywhere in the document

Content rules:
- All document content must be written in the same language as the input CV
- Do NOT repeat content across sections
- Do NOT include null or empty sections
- Never truncate a section — complete every section fully

## JSON OUTPUT RULES (NON-NEGOTIABLE)
- Return exactly ONE valid JSON object — nothing before or after it
- No duplicated keys
- No truncated strings — all fields must be complete
- Properly escape quotes (\") and newlines (\n) inside all string values
- No null fields unless information is truly unavailable
- Must be parseable by standard json.loads()
- The document.content value must be a single escaped JSON string (newlines as \n, quotes as \")
- All string values in the JSON (comments, suggestions, document content) must be in the detected CV language

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
    print("[!] - Model servers are overloaded, try again later")
    return {"error":ex}
  
  except Exception as ex:
    print("[!] - Exception while evaluating CV")
    print(ex)
    return {"error":ex}
    
