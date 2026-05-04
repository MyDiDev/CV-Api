from dotenv import load_dotenv
from os import getenv, urandom
from dto.user import UserDTO, APIKey
from pwdlib import PasswordHash
from dto.logs import Log
import psycopg
import hashlib

load_dotenv()
password_hash = PasswordHash.recommended()

def connect_to_db():
    try:
        global conn, cursor
        
        CONN_STR: str | None = getenv("POSTGRES_CONNECTION_STRING")
        if not CONN_STR: 
            raise Exception("Invalid connection string to DB")

        conn = psycopg.connect(CONN_STR) 
        cursor = conn.cursor()
        print("[+] - Connection to DB successfully")
    except Exception as ex:
        print("[!] - Error while connecting to DB")
        return

connect_to_db()

def hash_password(pwd: str) -> str:
    hash = password_hash.hash(pwd)
    return hash

def verify_password_hash(pwd: str, hash: str) -> bool:
    return password_hash.verify(pwd, hash)


def hash_api_key(key: str):
    return hashlib.sha256(key.encode()).hexdigest()

def compare_api_keys(key:str, db_hash:str) -> bool:
    return hash_api_key(key) == db_hash

def create_api_key() -> str:
    hash = hashlib.sha256(urandom(32)).hexdigest()
    return hash


async def create_user(user: UserDTO) -> bool | None:
    if not user.username or not user.password or not user.email:
        print("[!] - Credentials missing")
        return
 
    if not user.email.endswith("@gmail.com") and not user.email.endswith("@hotmail.com"):
        print("[!] Invalid email to register")
        return
    
    created_user = await get_user(user)
    if created_user: 
        print("[!] - User already registered")
        return True
 
    user.password = hash_password(user.password)
    cursor.execute("INSERT INTO Users(username, email, password_hash) VALUES (%s, %s, %s)", [user.username, user.email, user.password])    
    conn.commit()
    return True

async def remove_user(user: UserDTO) -> bool | None:
    if not user.id:
        print("[!] - ID missing to remove user")
        return 
    
    cursor.execute("DELETE FROM ApiKeys where ownter_id=%s", [user.id])
    cursor.execute("DELETE FROM Users WHERE user_id=%s", [user.id])
    conn.commit()
    return True
    
async def update_user(user: UserDTO) -> bool | None:
    if not user.id or not user.username or not user.password:
        print("[!] - Credentials missing to update user")
        return
    
    user.password = hash_password(user.password)
    cursor.execute("UPDATE Users SET username=%s, password=%s, role=%s WHERE user_id=%s", [user.username, user.password, user.role, user.id]) 
    conn.commit()
    return True

async def get_user(user: UserDTO) -> dict | None:
    if not (user.username or user.email) or not user.password:
        print("[!] - Credentials missing to get user")
        return 
    
    if not user.username:
        cursor.execute("SELECT * FROM Users WHERE email=%s", [user.email])
    else:
        cursor.execute("SELECT * FROM Users WHERE username=%s", [user.username])
    res = cursor.fetchone()
        
    if res == None:
        print("[!] - Invalid user found")
        return
    
    user_password = res[2]
    if verify_password_hash(user.password, user_password):
        return {"id":res[0], "username":user.username, "password":user.password}


async def register_log(log: Log) -> dict | None:
    if not log.api_key_id or not log.tokens_used:
        print("[!] - Log information missing")
        return
    
    cursor.execute("SELECT * FROM ApiKeys WHERE key_id=%s", [log.api_key_id])
    res = cursor.fetchone()
    
    if not res or len(res) == 0:
        print("[!] - Invalid api key to register log")
        return 
    
    cursor.execute("INSERT INTO apilogusage(api_key_id, tokens_used, response_time) VALUES(%s, %s, %s)", [log.api_key_id, log.tokens_used, 0])
    
    cursor.execute("SELECT * FROM apilogusage")
    res = cursor.fetchall()[-1]
    
    conn.commit()
    return {"log": res}

async def update_log(log: Log) -> bool | None:
    if not log.id or not log.status:
        print("[!] - Log ID and Status Missing to update")
        return
    
    cursor.execute("UPDATE apilogusage SET status = %s WHERE log_id = %s", [log.status, log.id])
    conn.commit()
    return True

async def validate_api_key(key: str) -> dict | None:
    if not key:
        print("[!] - Invalid API Key")
        return
    
    cursor.execute("SELECT * FROM ApiKeys WHERE key_hash=%s", [key])
    res = cursor.fetchone()
    
    try:
        data = {"api_key":res}
        return data
    except TypeError as ex:
        print("[!] - Invalid api key to access")
        return 

async def get_user_api_keys(user: UserDTO) -> str | None:
    if not user.username or not user.password:
        print("[!] - Invalid credentials from user to create api key")
        return  
    
    usr = await get_user(user)
    if not usr:
        print("[!] - Invalid user to create api key")
        return  
        
    cursor.execute("SELECT key_hash FROM ApiKeys WHERE owner_id = %s", [usr["id"]])
    res = cursor.fetchone()
    if res == None: return 
    
    return str(res[0])

async def save_api_key(user: UserDTO) -> tuple | str | None:
    if not user.username or not user.password:
        print("[!] - Invalid credentials from user to create api key")
        return  

    usr = await get_user(user)
    if not usr:
        print("[!] - Invalid user to create api key")
        return  
    
    user_api_key = await get_user_api_keys(user)
    if user_api_key != None and len(user_api_key) > 0:
        print("[!] - API key already created on this user")
        return user_api_key
    
    api_key = APIKey(owner_id=usr["id"], key_hash=create_api_key(), usage_count=0)
    
    cursor.execute("INSERT INTO ApiKeys(owner_id, key_hash, usage_count) VALUES(%s, %s, %s)", [api_key.owner_id, api_key.key_hash, api_key.usage_count])
    
    cursor.execute("SELECT * FROM ApiKeys WHERE key_hash=%s", [api_key.key_hash])
    res = cursor.fetchone()

    conn.commit()
    return res[2] if res != None else None 

async def remove_api_key(key: APIKey) -> bool | None:
    if not key.owner_id or not key.key_hash:
        print("[!] - Invalid credentials from key to remove api key")
        return  

    cursor.execute("DELETE FROM ApiKeys WHERE owner_id = %s and hash_key = %s", [key.owner_id, key.key_hash])
    conn.commit()
    return True

