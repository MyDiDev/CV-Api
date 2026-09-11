from dotenv import load_dotenv
from os import getenv
from contextlib import contextmanager
from pwdlib import PasswordHash
from typing import Generator
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

def verify_password_hash(pwd: str, hash_val: str) -> bool:
    return password_hash.verify(pwd, hash_val)

def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

def compare_api_keys(key: str, db_hash: str) -> bool:
    return secrets.compare_digest(hash_api_key(key), db_hash)

def create_api_key() -> str:
    return secrets.token_hex(32)