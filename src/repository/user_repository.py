from data.db import get_db, hash_password, verify_password_hash
from dto.user import UserDTO
from typing import Any

class UserRepository:
    @staticmethod
    async def create_user(user: UserDTO) -> bool | None:
        if not user.username or not user.password:
            return None
 
        created_user = await UserRepository.get_user(user)
        if created_user: 
            return True
 
        hashed_pwd = hash_password(user.password)
        with get_db() as (conn, cursor):
            cursor.execute("INSERT INTO Users(username, password_hash) VALUES (%s, %s)", [user.username, hashed_pwd])    
        return True

    @staticmethod
    async def remove_user(user: UserDTO) -> bool | None:
        if not user.id:
            return None
        
        with get_db() as (conn, cursor):
            cursor.execute("DELETE FROM ApiKeys WHERE owner_id=%s", [user.id])
            cursor.execute("DELETE FROM Users WHERE user_id=%s", [user.id])
        return True
        
    @staticmethod
    async def update_user(user: UserDTO) -> bool | None:
        if not user.id or not user.username or not user.password:
            return None
        
        hashed_pwd = hash_password(user.password)
        
        with get_db() as (conn, cursor):
            cursor.execute("UPDATE Users SET username=%s, password_hash=%s, role=%s WHERE user_id=%s", [user.username, hashed_pwd, user.role, user.id]) 
        return True

    @staticmethod
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
