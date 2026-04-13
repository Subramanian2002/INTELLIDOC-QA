import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT")
    )

def create_chat(user_id, title):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
                INSERT INTO chats (user_id,title)
                VALUES (%s,%s)
                RETURNING id """,(user_id,title))
    chat_id = cur.fetchone()[0]
    conn.commit()

    cur.close()
    conn.close()

    return chat_id

def get_user_chats(user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(""" SELECT id, title FROM chats
                WHERE user_id = %s
                ORDER BY created_at DESC """,(user_id,))
    chats = cur.fetchall()
    
    cur.close()
    conn.close()

    return chats

def save_message(chat_id, role, content):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(""" INSERT INTO messages (chat_id,role,content)
                VALUES (%s,%s,%s) """,(chat_id,role,content))
    
    conn.commit()
    cur.close()
    conn.close()


def update_chat_title(chat_id, title):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE chats SET title = %s WHERE id = %s
    """, (title, chat_id))

    conn.commit()
    cur.close()
    conn.close()

def get_messages(chat_id):
    conn =get_connection()
    cur = conn.cursor()

    cur.execute(""" SELECT role, content FROM messages
                WHERE chat_id = %s
                ORDER BY created_at
                 """,(chat_id,))
    messages = cur.fetchall()

    cur.close()
    conn.close()

    return messages




def save_files(chat_id, file_name, file_path):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(""" INSERT INTO files(chat_id, file_name, file_path)
                VALUES (%s,%s,%s) """,(chat_id,file_name,file_path))
    
    conn.commit()
    cur.close()
    conn.close()


def get_files(chat_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(""" SELECT file_name,file_path FROM files WHERE chat_id = %s """,(chat_id,))   

    files = cur.fetchall()
    cur.close()
    conn.close()

    return files


def delete_chat(chat_id):
    conn = get_connection()
    cur = conn.cursor()

    # 🔹 Delete messages first (FK dependency)
    cur.execute("DELETE FROM messages WHERE chat_id = %s", (chat_id,))

    # 🔹 Delete files records
    cur.execute("DELETE FROM files WHERE chat_id = %s", (chat_id,))

    # 🔹 Delete chat
    cur.execute("DELETE FROM chats WHERE id = %s", (chat_id,))

    conn.commit()
    cur.close()
    conn.close()    
 