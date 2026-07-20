from data.db import get_db
from dto.logs import Log
from typing import Any

class LogRepository:
    @staticmethod
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

    @staticmethod
    async def update_log(log: Log) -> bool | None:
        if not log.id or not log.status:
            return None
        
        with get_db() as (conn, cursor):    
            cursor.execute("UPDATE apilogusage SET status = %s, response_time = %s WHERE log_id = %s", [log.status, log.response_time, log.id])
            return True
