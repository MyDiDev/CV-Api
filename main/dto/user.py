from pydantic import BaseModel

class UserDTO(BaseModel):
    id: int
    username: str
    password: str
    role: str 
    dateRegistered: str

class UserAuthDTO(BaseModel):
    username: str
    password: str
    
