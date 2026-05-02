from pydantic import BaseModel

class CVDTO(BaseModel):
    id: int
    title: str | None = None
    content: str | None = None
    grade: float | None = None
    feedback: str | None = None
    state: str | None = None
    date: str | None = None

