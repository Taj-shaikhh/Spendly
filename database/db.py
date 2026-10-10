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

def get_user_by_email(email):
    """Retrieves a user by their email address. Returns a sqlite3.Row or None."""
    with get_db() as conn:
        return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

def get_user_details(user_id):
    """Retrieves basic profile details for a user. Returns a sqlite3.Row or None."""
    with get_db() as conn:
        return conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

def get_category_breakdown(user_id):
    """
    Returns a list of categories and their total spend for a given user.
    Returns a list of sqlite3.Row objects.
    """
    with get_db() as conn:
        return conn.execute(
            "SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? GROUP BY category",
            (user_id,)
        ).fetchall()

def get_recent_transactions(user_id, limit=5):
    """
    Returns a list of recent expenses for the user, ordered by date DESC.
    Returns a list of dictionaries.
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses WHERE user_id = ? ORDER BY date DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        return [dict(row) for row in rows]

def get_spending_summary(user_id):
    """
    Returns a summary of spending for a user.
    Returns a dictionary with total_spent, transaction_count, and top_category.
    """
    with get_db() as conn:
        # Total spent and transaction count
        summary = conn.execute(
            "SELECT SUM(amount) as total_spent, COUNT(*) as transaction_count FROM expenses WHERE user_id = ?",
            (user_id,)
        ).fetchone()

        # Top category
        top_cat = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            (user_id,)
        ).fetchone()

        return {
            "total_spent": summary["total_spent"] if summary["total_spent"] else 0.0,
            "transaction_count": summary["transaction_count"],
            "top_category": top_cat["category"] if top_cat else None
        }

