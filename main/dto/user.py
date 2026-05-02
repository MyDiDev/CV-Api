from pydantic import BaseModel

class UserDTO(BaseModel):
    id: int | None = None
    username: str | None = None
    password: str | None = None
    role: str | None = None 
    dateRegistered: str | None = None