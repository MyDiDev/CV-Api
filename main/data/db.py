import psycopg
from dotenv import load_dotenv
from os import getenv
from dto.user import UserDTO
from dto.logs import Log
from pwdlib import PasswordHash

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

def create_user(user: UserDTO) -> bool | None:
    if not user.username or not user.password:
        print("[!] - Credentials missing")
        return
 
    user.password = hash_password(user.password)
    cursor.execute("INSERT INTO Users(username, password_hash) VALUES (%s, %s)", [user.username, user.password])    
    conn.commit()
    return True

def remove_user(user: UserDTO) -> bool | None:
    if not user.id:
        print("[!] - ID missing to remove user")
        return 
    
    cursor.execute("DELETE FROM Users WHERE user_id=%s", [str(user.id)])
    conn.commit()
    return True
    
def update_user(user: UserDTO) -> bool | None:
    if not user.id or not user.username or not user.password:
        print("[!] - Credentials missing to update user")
        return
    
    user.password = hash_password(user.password)
    cursor.execute("UPDATE FROM Users SET username=%s, password=%s, role=%s WHERE user_id=%s", [user.username, user.password, user.role, user.id]) 
    conn.commit()
    return True

def get_user(user: UserDTO) -> dict | None:
    if not user.username or not user.password:
        print("[!] - Credentials missing to get user")
        return 
    
    cursor.execute("SELECT * FROM Users WHERE username=%s", [user.username])
    res = cursor.fetchone()
        
    if res == None:
        print("[!] - Invalid user found")
        return
    
    user_password = res[2]
    if verify_password_hash(user.password, user_password):
        return {"id":res[0], "username":user.username, "password":user.password}
