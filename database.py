import sqlite3
from pathlib import Path

DB_PATH = Path("data.db")

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    # Tabla de Licencias reforzada con consentimiento legal
    cur.execute("""
    CREATE TABLE IF NOT EXISTS licenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        link_id TEXT UNIQUE,
        session_id TEXT UNIQUE,
        expires_at TEXT,
        active_device TEXT,
        legal_accepted INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()

def create_license(link_id, session_id, expires_at):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO licenses (link_id, session_id, expires_at, active_device) VALUES (?,?,?,?)",
        (link_id, session_id, expires_at, None)
    )
    conn.commit()
    conn.close()

def get_license_by_link(link_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT link_id, expires_at, active_device FROM licenses WHERE link_id=?", (link_id,))
    row = cur.fetchone()
    conn.close()
    return row

def get_license_by_session(session_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT link_id FROM licenses WHERE session_id=?", (session_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def set_active_device(link_id, device_id):
    conn = get_conn()
    cur = conn.cursor()
    # El nuevo dispositivo toma el control total (Regla de May Roga LLC)
    cur.execute("UPDATE licenses SET active_device=?, legal_accepted=1 WHERE link_id=?", (device_id, link_id))
    conn.commit()
    conn.close()
