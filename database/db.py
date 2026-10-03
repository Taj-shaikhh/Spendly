import sqlite3
from werkzeug.security import generate_password_hash

DB_PATH = "spendly.db"

def get_db():
    """Returns a SQLite connection with row_factory and foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Creates all tables using CREATE TABLE IF NOT EXISTS."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        conn.commit()

def create_user(name, email, password):
    """
    Hashes password and inserts a new user into the database.
    Returns the new user's ID.
    Raises sqlite3.IntegrityError if email already exists.
    """
    hashed_pw = generate_password_hash(password)
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, hashed_pw)
        )
        conn.commit()
        return cursor.lastrowid

def seed_db():
    """Inserts sample data for development if the database is empty."""
    with get_db() as conn:
        # Check if users table already contains data
        user_count = conn.execute("SELECT count(*) FROM users").fetchone()[0]
        if user_count > 0:
            return

        # Insert demo user
        hashed_pw = generate_password_hash("demo123")
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", hashed_pw)
        )
        user_id = cursor.lastrowid

        # Insert 8 sample expenses
        # Categories: Food, Transport, Bills, Health, Entertainment, Shopping, Other
        expenses = [
            (user_id, 12.50, "Food", "2026-10-01", "Lunch at Cafe"),
            (user_id, 45.00, "Transport", "2026-10-01", "Weekly fuel"),
            (user_id, 120.00, "Bills", "2026-10-02", "Internet Bill"),
            (user_id, 30.00, "Health", "2026-10-02", "Pharmacy"),
            (user_id, 15.00, "Entertainment", "2026-10-03", "Movie Ticket"),
            (user_id, 60.00, "Shopping", "2026-10-03", "New shirt"),
            (user_id, 10.00, "Other", "2026-10-04", "Gift wrap"),
            (user_id, 25.00, "Food", "2026-10-04", "Dinner"),
        ]

        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            expenses
        )
        conn.commit()
