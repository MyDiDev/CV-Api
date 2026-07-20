from dotenv import load_dotenv
from os import getenv
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

def verify_password_hash(pwd: str, hash_val: str) -> bool:
    return password_hash.verify(pwd, hash_val)

def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

def compare_api_keys(key: str, db_hash: str) -> bool:
    return secrets.compare_digest(hash_api_key(key), db_hash)

def create_api_key() -> str:
    return secrets.token_hex(32)

async def create_user(user: UserDTO) -> bool | None:
    from repository.user_repository import UserRepository
    return await UserRepository.create_user(user)

async def remove_user(user: UserDTO) -> bool | None:
    from repository.user_repository import UserRepository
    return await UserRepository.remove_user(user)

async def update_user(user: UserDTO) -> bool | None:
    from repository.user_repository import UserRepository
    return await UserRepository.update_user(user)

async def get_user(user: UserDTO) -> dict[str, Any] | None:
    from repository.user_repository import UserRepository
    return await UserRepository.get_user(user)

async def register_log(log: Log) -> dict[str, Any] | None:
    from repository.log_repository import LogRepository
    return await LogRepository.register_log(log)

async def update_log(log: Log) -> bool | None:
    from repository.log_repository import LogRepository
    return await LogRepository.update_log(log)

async def validate_api_key(key: str) -> dict[str, Any] | None:
    from repository.api_key_repository import ApiKeyRepository
    return await ApiKeyRepository.validate_api_key(key)

async def get_user_api_key(user: UserDTO) -> str | None:
    from repository.api_key_repository import ApiKeyRepository
    return await ApiKeyRepository.get_user_api_key(user)

async def save_api_key(user: UserDTO) -> str | None:
    from repository.api_key_repository import ApiKeyRepository
    return await ApiKeyRepository.save_api_key(user)

async def remove_api_key(key: APIKey) -> bool | None:
    from repository.api_key_repository import ApiKeyRepository
    return await ApiKeyRepository.remove_api_key(key)

async def get_api_information(user: UserDTO) -> dict[str, Any] | None:
    from repository.api_key_repository import ApiKeyRepository
    return await ApiKeyRepository.get_api_information(user)

async def save_doc_url(url: str, api_key_id: int | None) -> bool | None:
    from repository.document_repository import DocumentRepository
    return await DocumentRepository.save_doc_url(url, api_key_id)

async def get_documents(api_key_id: int | None) -> dict[str, list[Any] | None] | None:
    from repository.document_repository import DocumentRepository
    return await DocumentRepository.get_documents(api_key_id)