import pytest
from app import app as flask_app
from database.db import get_db, create_expense
import sqlite3
import os

@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    # Use a separate test database file
    import database.db
    database.db.DB_PATH = "test_spendly.db"

    with flask_app.app_context():
        from database.db import init_db
        init_db()
        # Create a test user
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                ("Test User", "test@example.com", "hashed_password")
            )
            conn.commit()

    with flask_app.test_client() as client:
        yield client

    # Cleanup - avoid PermissionError on Windows by ensuring connections are closed
    try:
        if os.path.exists("test_spendly.db"):
            os.remove("test_spendly.db")
    except PermissionError:
        pass

def test_insert_expense_db():
    """Test the database helper directly."""
    import database.db
    database.db.DB_PATH = "test_spendly.db"
    with get_db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, category TEXT, date TEXT, description TEXT, created_at TEXT DEFAULT (datetime('now')))")
        conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT, password_hash TEXT)")
        conn.execute("INSERT INTO users (name, email, password_hash) VALUES ('Test', 't@e.com', 'pw')")
        user_id = conn.execute("SELECT id FROM users").fetchone()[0]

    create_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")

    with get_db() as conn:
        row = conn.execute("SELECT * FROM expenses WHERE user_id = ?", (user_id,)).fetchone()
        assert row is not None
        assert row["amount"] == 50.0
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Lunch"

def test_add_expense_unauthenticated(client):
    """GET /expenses/add should redirect to login when not authenticated."""
    response = client.get("/expenses/add")
    assert response.status_code == 302
    assert response.location == "/login"

def test_add_expense_authenticated_get(client):
    """GET /expenses/add should render the form when authenticated."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    response = client.get("/expenses/add")
    assert response.status_code == 200
    assert b"Add New Expense" in response.data
    assert b"Food" in response.data
    assert b"Transport" in response.data
    assert b"Bills" in response.data
    assert b"Health" in response.data
    assert b"Entertainment" in response.data
    assert b"Shopping" in response.data
    assert b"Other" in response.data

def test_add_expense_valid_post(client):
    """POST /expenses/add should save a valid expense and redirect to profile."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    data = {
        "amount": "50.0",
        "category": "Food",
        "date": "2026-03-20",
        "description": "Lunch"
    }
    response = client.post("/expenses/add", data=data, follow_redirects=False)
    assert response.status_code == 302
    assert response.location == "/profile"

def test_add_expense_invalid_amount(client):
    """POST /expenses/add should fail with negative or non-numeric amount."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    # Negative amount
    response = client.post("/expenses/add", data={
        "amount": "-10", "category": "Food", "date": "2026-03-20"
    })
    assert response.status_code == 200
    assert b"Amount must be greater than zero" in response.data

    # Non-numeric amount
    response = client.post("/expenses/add", data={
        "amount": "abc", "category": "Food", "date": "2026-03-20"
    })
    assert response.status_code == 200
    assert b"Amount must be a valid number" in response.data

def test_add_expense_invalid_category(client):
    """POST /expenses/add should fail with an invalid category."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    response = client.post("/expenses/add", data={
        "amount": "10", "category": "InvalidCat", "date": "2026-03-20"
    })
    assert response.status_code == 200
    assert b"Please select a valid category" in response.data

def test_add_expense_invalid_date(client):
    """POST /expenses/add should fail with an invalid date."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    response = client.post("/expenses/add", data={
        "amount": "10", "category": "Food", "date": "not-a-date"
    })
    assert response.status_code == 200
    assert b"Invalid date format" in response.data

def test_add_expense_optional_description(client):
    """POST /expenses/add should succeed without a description."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    data = {
        "amount": "20.0",
        "category": "Transport",
        "date": "2026-03-21",
        "description": ""
    }
    response = client.post("/expenses/add", data=data)
    assert response.status_code == 302
    assert response.location == "/profile"
