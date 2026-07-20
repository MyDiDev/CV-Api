from data.db import get_db, hash_api_key, create_api_key
from repository.user_repository import UserRepository
from dto.user import UserDTO, APIKey
from typing import Any

class ApiKeyRepository:
    @staticmethod
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

    @staticmethod
    async def get_user_api_key(user: UserDTO) -> str | None:
        if not user.username or not user.password:
            return None
        
        usr = await UserRepository.get_user(user)
        if not usr:
            return None
        
        with get_db() as (conn, cursor):    
            cursor.execute("SELECT key_hash FROM ApiKeys WHERE owner_id = %s", [usr["id"]])
            res = cursor.fetchone()
        if res is None: 
            return None
        
        return str(res[0])

    @staticmethod
    async def save_api_key(user: UserDTO) -> str | None:
        if not user.username or not user.password:
            return None

        usr = await UserRepository.get_user(user)
        if not usr:
            return None
        
        user_api_key = await ApiKeyRepository.get_user_api_key(user)
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

    @staticmethod
    async def remove_api_key(key: APIKey) -> bool | None:
        if not key.owner_id or not key.key_hash:
            return None
        
        with get_db() as (conn, cursor):
            cursor.execute("DELETE FROM ApiKeys WHERE owner_id = %s AND key_hash = %s", [key.owner_id, key.key_hash])
        return True

    @staticmethod
    async def get_api_information(user: UserDTO) -> dict[str, Any] | None:
        if not user.username or not user.password:
            return None
        
        key = await ApiKeyRepository.get_user_api_key(user)
        if not key:
            return None
        
        api_key_data = await ApiKeyRepository.validate_api_key(key)
        if api_key_data is None or not isinstance(api_key_data, dict) or not api_key_data.get("api_key"):
            return None
        
        with get_db() as (conn, cursor):
            cursor.execute("SELECT tokens_used, status, response_time FROM apilogusage WHERE api_key_id = %s", [api_key_data.get("api_key")[0]])
            logs_information = cursor.fetchall()
        return {"data": logs_information}
