from google import genai
from google.api_core.exceptions import ServiceUnavailable
from dotenv import load_dotenv
from data.db import register_log, update_log
from dto.logs import Log
from dto.user import APIKey
import json
import os

load_dotenv()
MODEL_ROLE = """"You are an expert HR analyst and CV evaluator.

Your task is to read and understand curriculum vitae (CV) documents submitted by users and return a structured evaluation in JSON format.

You must:
1. Extract relevant information from the CV.
2. Evaluate the CV based on professional hiring criteria.
3. Assign a global score from 0 to 100.
4. Provide detailed evaluation by criteria.
5. Suggest actionable improvements.

Evaluation criteria must include:
- claridad_y_estructura (clarity and organization)
- experiencia_relevante (relevant experience)
- educacion_y_formacion (education and training)
- habilidades (skills)
- logros_e_impacto (achievements and impact)
- adaptacion_al_puesto (fit for job, if job context is provided)

Scoring rules:
- Each criterion must have a score from 0 to 100.
- The global score must be a weighted or balanced summary of all criteria.
- Be strict but fair, like a real recruiter.

Suggestions:
- Must be specific, actionable, and concise.
- Focus on improving content, structure, and impact.

Output rules:
- Always return ONLY valid JSON.
- Do not include explanations outside JSON.
- Do not include markdown formatting.

JSON structure:

{
  "global_score": number,
  "evaluation": {
    "structure_and_quality": {
      "score": number,
      "comment": string
    },
    "relevant_experience": {
      "score": number,
      "comment": string
    },
    "formation_and_education": {
      "score": number,
      "comment": string
    },
    "habilities": {
      "score": number,
      "comment": string
    },
    "goals_and_impact": {
      "score": number,
      "comment": string
    },
    "adaption_for_position": {
      "score": number,
      "comment": string
    }
  },
  "suggestions": [
    string,
    string,
    string
  ]
}

Additional constraints:
- If information is missing, reflect it in the score and explain it in the comment.
- Do not hallucinate experience or skills not present in the CV.
- Keep language professional and neutral."""

async def update_task_log(log_res):
  if log_res != None:
    res = await update_log(Log(id=log_res[0], status="done"))
    if res: print("Log Updated Successfully")
  print("[!]- Invalid log updated")
  return

async def evaluate_cv_document(content: str, api_key: APIKey) -> dict | None:
  if not content: raise Exception("Invalid CV document content to process")
  
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
    
    res_txt = str(response.text).strip() if response else None 
    if not res_txt:
      print("[!] - Invalid response error")
      await update_task_log(log_res)
      return {"error": "Invalid response or JSON from model", "raw":res_txt}
    if res_txt.startswith("```"): res_txt.replace("```", "")
    
    await update_task_log(log_res)
    return json.loads(res_txt)    
  except ServiceUnavailable as ex:
    print("[!] - Serveres ar overloaded, try again later")
    return {"error":ex}
  except Exception as ex:
    print("[!] - Exception while evaluating CV")
    return

