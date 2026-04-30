from pydantic import BaseModel

class CVDTO(BaseModel):
    id: int
    title: str
    content: str
    grade: float
    feedback: str
    state: str
    date: str
    