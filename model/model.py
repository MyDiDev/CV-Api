from ollama import chat, ResponseError
import json

MODEL_ROLE = ""

def evaluate_cv_document(content: str) -> dict | None| ResponseError:
    if not content: raise Exception("Invalid CV document content to process")

    try:
        response = chat(model="qwen3.5:cloud", messages=[
            {
                "role":"{}".format(MODEL_ROLE),
                "content": "{}".format(content)
            }
        ])
        
        if not response:
            raise Exception("Invalid response content from model, check if model is avaiable or has reached its limit")
        
        if response.message.content is not None:
            return json.loads(response.message.content)
        return None 
    
    except ResponseError as ex:
        return ex
        