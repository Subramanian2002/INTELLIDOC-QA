import bcrypt
from db import get_connection


# 🔹 Create User (Signup)
def create_user(name, email, password):
    conn = get_connection()
    cur = conn.cursor()

    # Hash password
    hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    try:
        cur.execute("""
            INSERT INTO users (name, email, password_hash)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (name, email, hashed_pw.decode('utf-8')))

        user_id = cur.fetchone()[0]
        conn.commit()

        return user_id

    except Exception as e:
        conn.rollback()

        # Optional: handle duplicate email
        if "unique" in str(e).lower():
            return "EMAIL_EXISTS"

        return None

    finally:
        cur.close()
        conn.close()


# 🔹 Login User
def login_user(email, password):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, password_hash FROM users WHERE email=%s
    """, (email,))

    user = cur.fetchone()

    cur.close()
    conn.close()

    if user:
        user_id, stored_hash = user

        # Verify password
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
            return user_id

    return None