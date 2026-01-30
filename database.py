import sqlite3

DB = "licenses.db"

def init_db():
    with sqlite3.connect(DB) as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            license TEXT PRIMARY KEY,
            session_id TEXT UNIQUE,
            expires TEXT
        )
        """)

def create_license(license_id, session_id, expires):
    with sqlite3.connect(DB) as con:
        con.execute(
            "INSERT OR IGNORE INTO licenses VALUES (?, ?, ?)",
            (license_id, session_id, expires)
        )

def get_license_by_session(session_id):
    with sqlite3.connect(DB) as con:
        r = con.execute(
            "SELECT license FROM licenses WHERE session_id=?",
            (session_id,)
        ).fetchone()
        return r[0] if r else None

def get_license_by_link(license_id):
    with sqlite3.connect(DB) as con:
        return con.execute(
            "SELECT * FROM licenses WHERE license=?",
            (license_id,)
        ).fetchone()
