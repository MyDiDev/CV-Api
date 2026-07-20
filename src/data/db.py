from dotenv import load_dotenv
from os import getenv, urandom
from contextlib import contextmanager
from dto.user import UserDTO, APIKey
from pwdlib import PasswordHash
from dto.logs import Log
from typing import Any, Generator
import psycopg
import hashlib
import secrets

load_dotenv()
password_hash = PasswordHash.recommended()

@contextmanager
def get_db() -> Generator[tuple[psycopg.Connection, psycopg.Cursor], None, None]:
    conn = psycopg.connect(getenv("POSTGRES_CONNECTION_STRING") or "")
    cursor = conn.cursor()
    try:
        yield conn, cursor
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def hash_password(pwd: str) -> str:
    return password_hash.hash(pwd)

def verify_password_hash(pwd: str, hash: str) -> bool:
    return password_hash.verify(pwd, hash)

def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

def compare_api_keys(key: str, db_hash: str) -> bool:
    return secrets.compare_digest(hash_api_key(key), db_hash)

def create_api_key() -> str:
    return secrets.token_hex(32)

async def create_user(user: UserDTO) -> bool | None:
    if not user.username or not user.password:
        return None
 
    created_user = await get_user(user)
    if created_user: 
        return True
 
    hashed_pwd = hash_password(user.password)
    with get_db() as (conn, cursor):
        cursor.execute("INSERT INTO Users(username, password_hash) VALUES (%s, %s)", [user.username, hashed_pwd])    
    return True

async def remove_user(user: UserDTO) -> bool | None:
    if not user.id:
        return None
    
    with get_db() as (conn, cursor):
        cursor.execute("DELETE FROM ApiKeys WHERE owner_id=%s", [user.id])
        cursor.execute("DELETE FROM Users WHERE user_id=%s", [user.id])
    return True
    
async def update_user(user: UserDTO) -> bool | None:
    if not user.id or not user.username or not user.password:
        return None
    
    hashed_pwd = hash_password(user.password)
    
    with get_db() as (conn, cursor):
        cursor.execute("UPDATE Users SET username=%s, password_hash=%s, role=%s WHERE user_id=%s", [user.username, hashed_pwd, user.role, user.id]) 
    return True

async def get_user(user: UserDTO) -> dict[str, Any] | None:
    if not user.username or not user.password:
        return None
    
    with get_db() as (conn, cursor):
        cursor.execute("SELECT * FROM Users WHERE username=%s", [user.username])
        res = cursor.fetchone()
        
    if res is None:
        return None
    
    user_password = res[2]
    if verify_password_hash(user.password, user_password):
        return {"id": res[0], "username": user.username, "password": user.password}
    return None

async def register_log(log: Log) -> dict[str, Any] | None:
    if not log.api_key_id or log.tokens_used is None:
        return None
    
    with get_db() as (conn, cursor):
        cursor.execute("SELECT * FROM ApiKeys WHERE key_id=%s", [log.api_key_id])
        res = cursor.fetchone()
        
        if not res or len(res) == 0:
            return None
        
        cursor.execute("INSERT INTO apilogusage(api_key_id, tokens_used, response_time) VALUES(%s, %s, %s) RETURNING *", [log.api_key_id, log.tokens_used, 0])
        created_log = cursor.fetchone()
        
    return {"log": created_log}

async def update_log(log: Log) -> bool | None:
    if not log.id or not log.status:
        return None
    
    with get_db() as (conn, cursor):    
        cursor.execute("UPDATE apilogusage SET status = %s, response_time = %s WHERE log_id = %s", [log.status, log.response_time, log.id])
        return True

async def validate_api_key(key: str) -> dict[str, Any] | None:
    if not key:
        return None
    
    key_hash = hash_api_key(key)
    with get_db() as (conn, cursor):
        cursor.execute("SELECT * FROM ApiKeys WHERE key_hash=%s OR key_hash=%s", [key_hash, key])
        res = cursor.fetchone()
        
    if res is None:
        return None
        
    return {"api_key": res}

async def get_user_api_key(user: UserDTO) -> str | None:
    if not user.username or not user.password:
        return None
    
    usr = await get_user(user)
    if not usr:
        return None
    
    with get_db() as (conn, cursor):    
        cursor.execute("SELECT key_hash FROM ApiKeys WHERE owner_id = %s", [usr["id"]])
        res = cursor.fetchone()
    if res is None: 
        return None
    
    return str(res[0])

async def save_api_key(user: UserDTO) -> str | None:
    if not user.username or not user.password:
        return None

    usr = await get_user(user)
    if not usr:
        return None
    
    user_api_key = await get_user_api_key(user)
    if user_api_key is not None and len(user_api_key) > 0:
        return user_api_key
    
    raw_key = create_api_key()
    hashed_key = hash_api_key(raw_key)
    api_key = APIKey(owner_id=usr["id"], key_hash=hashed_key, usage_count=0)
    
    with get_db() as (conn, cursor):
        cursor.execute("INSERT INTO ApiKeys(owner_id, key_hash, usage_count) VALUES(%s, %s, %s)", [api_key.owner_id, api_key.key_hash, api_key.usage_count])
        cursor.execute("SELECT * FROM ApiKeys WHERE key_hash=%s", [api_key.key_hash])
        res = cursor.fetchone()

    return raw_key if res is not None else None 

async def remove_api_key(key: APIKey) -> bool | None:
    if not key.owner_id or not key.key_hash:
        return None
    
    with get_db() as (conn, cursor):
        cursor.execute("DELETE FROM ApiKeys WHERE owner_id = %s AND key_hash = %s", [key.owner_id, key.key_hash])
    return True

async def get_api_information(user: UserDTO) -> dict[str, Any] | None:
    if not user.username or not user.password:
        return None
    
    key = await get_user_api_key(user)
    if not key:
        return None
    
    api_key_data = await validate_api_key(key)
    if api_key_data is None or not isinstance(api_key_data, dict) or not api_key_data.get("api_key"):
        return None
    
    with get_db() as (conn, cursor):
        cursor.execute("SELECT tokens_used, status, response_time FROM apilogusage WHERE api_key_id = %s", [api_key_data.get("api_key")[0]])
        logs_information = cursor.fetchall()
    return {"data": logs_information}

async def save_doc_url(url: str, api_key_id: int | None) -> bool | None:
    if not url or not api_key_id:
        return None

    with get_db() as (conn, cursor):
        cursor.execute("INSERT INTO documents(api_key_id, file_url) VALUES (%s, %s)", [api_key_id, url])    
    return True

async def get_documents(api_key_id: int | None) -> dict[str, list[Any] | None] | None:
    if not api_key_id:
        return None
    
    with get_db() as (conn, cursor):
        cursor.execute("SELECT file_url FROM documents WHERE api_key_id = %s", [api_key_id])
        res = cursor.fetchall()
    return {
        "documents": res
    }