from jwt.exceptions import InvalidTokenError
from dotenv import load_dotenv
from os import getenv
from typing import Any
import datetime
import jwt

load_dotenv()
SECRET_KEY: str | None = getenv("SECRET_KEY")
EXPIRE_TIME: int | None = int(getenv("EXPIRE_TIME") or "60")
ALGORITHIM: str | None = getenv("ALGORITHIM")


def create_token(payload: dict) -> str | None:
    if not SECRET_KEY or not ALGORITHIM or not EXPIRE_TIME:
        print("[!] - Invalid JWT enviroment variables")
        return 
    payload["iat"] = datetime.datetime.now(tz=datetime.timezone.utc)
    payload["exp"] = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(minutes=EXPIRE_TIME)
    print(payload, ALGORITHIM)
    return jwt.encode(payload, SECRET_KEY, ALGORITHIM)

def decode_token(token: str) -> dict[str, Any] | dict[str, bool] | None:
    try:
        if not SECRET_KEY or not ALGORITHIM or not EXPIRE_TIME:
            print("[!] - Invalid JWT enviroment variables")
            return 
        return jwt.decode(token, SECRET_KEY, [ALGORITHIM])
    except InvalidTokenError:
        return {"expired":True}