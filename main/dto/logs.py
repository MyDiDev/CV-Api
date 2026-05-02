from pydantic import BaseModel
from datetime import datetime

class Log(BaseModel):
    id: int | None = None
    api_key_id: int | None = None
    request_timestamp: datetime | None = None
    tokens_used: int | None = None
    status: str | None = None
    response_time: int | None = None