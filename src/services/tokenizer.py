from jwt.exceptions import InvalidTokenError
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.exceptions import HTTPException
from fastapi import Depends
from dotenv import load_dotenv
from os import getenv
from typing import Any
import datetime
import jwt

load_dotenv()

SECRET_KEY: str | None = getenv("SECRET_KEY")
EXPIRE_TIME: int = int(getenv("EXPIRE_TIME") or "60")
ALGORITHM: str = getenv("ALGORITHM") or getenv("ALGORITHIM") or "HS256"

security = HTTPBearer()

async def get_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict[str, Any]:
    token = str(credentials.credentials)
    res = decode_token(token)
    
    if not res or res.get("expired") is True:
        raise HTTPException(status_code=401, detail="Invalid auth token or expired")
    
    return res

def create_token(payload: dict[str, Any]) -> str:
    if not SECRET_KEY:
        raise HTTPException(status_code=500, detail="JWT configuration error")
    
    payload_copy = payload.copy()
    payload_copy["iat"] = datetime.datetime.now(tz=datetime.timezone.utc)
    payload_copy["exp"] = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(minutes=EXPIRE_TIME)
    return jwt.encode(payload_copy, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict[str, Any] | None:
    try:
        if not SECRET_KEY:
            return None
        decode = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return decode
    except InvalidTokenError:
        return {"expired": True}

