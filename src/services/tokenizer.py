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
EXPIRE_TIME: int | None = int(getenv("EXPIRE_TIME") or "60")
ALGORITHIM: str | None = getenv("ALGORITHIM")

security = HTTPBearer()
async def get_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict | None:
    token = str(credentials.credentials)
    res = decode_token(token)
    
    if not res or res.get("expired") == True: raise HTTPException(status_code=400, detail="Invalid auth token or expired")
    
    return res


def create_token(payload: dict) -> str | None:
    if not SECRET_KEY or not ALGORITHIM or not EXPIRE_TIME:
        print("[!] - Invalid JWT enviroment variables")
        return 
    payload["iat"] = datetime.datetime.now(tz=datetime.timezone.utc)
    payload["exp"] = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(minutes=EXPIRE_TIME)
    return jwt.encode(payload, SECRET_KEY, ALGORITHIM)

def decode_token(token: str) -> dict[str, Any] | dict[str, bool] | None:
    try:
        if not SECRET_KEY or not ALGORITHIM or not EXPIRE_TIME:
            print("[!] - Invalid JWT enviroment variables")
            return
        decode = jwt.decode(token, SECRET_KEY, [ALGORITHIM])
        print(decode)
        return decode
    except InvalidTokenError:
        return {"expired":True}

