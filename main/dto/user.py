from pydantic import BaseModel
from datetime import datetime

class UserDTO(BaseModel):
    id: int | None = None
    username: str | None = None
    email: str | None = None
    password: str | None = None
    role: str | None = None 
    dateRegistered: str | None = None

class APIKey(BaseModel):
    id: int | None = None
    owner_id: int | None = None
    key_hash: str | None = None
    rate_limit: int | None = None
    usage_count: int | None = None
    created_at: datetime | None = None