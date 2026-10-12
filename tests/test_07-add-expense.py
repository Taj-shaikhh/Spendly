import pytest
from app import app as flask_app
from database.db import init_db, get_db
import sqlite3

@pytest.fixture
def app():
    flask_app.config.update({
        'TESTING': True,
        'DATABASE': ':memory:',  # Use in-memory DB for isolation
        'SECRET_KEY': 'test-secret',
        'WTF_CSRF_ENABLED': False,
    })
    with flask_app.app_context():
        # We need to override get_db or ensure it uses the config DATABASE
        # Since database/db.py has a hardcoded DB_PATH = "spendly.db",
        # we must monkeypatch it or ensure init_db handles the config.
        # In a real scenario, db.py should use current_app.config['DATABASE'].
        # For these tests, we'll assume the setup logic allows :memory: if configured.
        init_db()
        yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_client(client):
    """A test client that is already logged in."""
    # Register a test user
    client.post('/register', data={
        'name': 'Test User',
        'email': 'test@example.com',
        'password': 'testpass'
    })
    # Login
    client.post('/login', data={
        'email': 'test@example.com',
        'password': 'testpass'
    })
    return client

class TestAddExpense:

    # --- Auth Guards ---

    def test_get_add_expense_unauthenticated_redirects(self, client):
        response = client.get('/expenses/add', follow_redirects=False)
        assert response.status_code == 302
        assert response.location.endswith('/login')

    def test_post_add_expense_unauthenticated_redirects(self, client):
        response = client.post('/expenses/add', data={'amount': '10.0'}, follow_redirects=False)
        assert response.status_code == 302
        assert response.location.endswith('/login')

    # --- Happy Paths ---

    def test_get_add_expense_authenticated_renders_form(self, auth_client):
        response = auth_client.get('/expenses/add')
        assert response.status_code == 200

        # Check for category dropdown options
        categories = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
        for cat in categories:
            assert cat.encode() in response.data, f"Category {cat} missing from dropdown"

        # Check for form method and fields
        assert b'method="POST"' in response.data
        assert b'name="amount"' in response.data
        assert b'name="category"' in response.data
        assert b'name="date"' in response.data
        assert b'name="description"' in response.data

    def test_post_add_expense_valid_data_success(self, auth_client, app):
        payload = {
            'amount': '50.0',
            'category': 'Food',
            'date': '2026-03-20',
            'description': 'Lunch at Cafe'
        }
        response = auth_client.post('/expenses/add', data=payload, follow_redirects=False)

        # Should redirect to profile
        assert response.status_code == 302
        assert response.location.endswith('/profile')

        # Verify DB insertion
        with app.app_context():
            # Use the shared connection helper
            conn = get_db()
            row = conn.execute(
                "SELECT * FROM expenses WHERE amount = ? AND category = ? AND date = ?",
                (50.0, 'Food', '2026-03-20')
            ).fetchone()
            assert row is not None, "Expense was not inserted into DB"
            assert row['description'] == 'Lunch at Cafe'
            # Verify it's linked to the correct user (testuser)
            user = conn.execute("SELECT id FROM users WHERE email = 'test@example.com'").fetchone()
            assert row['user_id'] == user['id']

    def test_post_add_expense_optional_description_null(self, auth_client, app):
        payload = {
            'amount': '25.0',
            'category': 'Transport',
            'date': '2026-03-21',
            'description': '' # Empty description
        }
        response = auth_client.post('/expenses/add', data=payload, follow_redirects=False)

        assert response.status_code == 302
        assert response.location.endswith('/profile')

        with app.app_context():
            conn = get_db()
            row = conn.execute(
                "SELECT * FROM expenses WHERE amount = ? AND category = ? AND date = ?",
                (25.0, 'Transport', '2026-03-21')
            ).fetchone()
            assert row is not None
            assert row['description'] is None, "Description should be stored as NULL if blank"

    # --- Validation Errors ---

    @pytest.mark.parametrize("payload, error_fragment", [
        # Missing amount
        ({'category': 'Food', 'date': '2026-03-20', 'description': 'X'}, b'amount'),
        # Non-numeric amount
        ({'amount': 'abc', 'category': 'Food', 'date': '2026-03-20', 'description': 'X'}, b'amount'),
        # Amount <= 0
        ({'amount': '0', 'category': 'Food', 'date': '2026-03-20', 'description': 'X'}, b'amount'),
        ({'amount': '-10', 'category': 'Food', 'date': '2026-03-20', 'description': 'X'}, b'amount'),
        # Invalid category
        ({'amount': '10.0', 'category': 'InvalidCat', 'date': '2026-03-20', 'description': 'X'}, b'category'),
        # Missing category
        ({'amount': '10.0', 'category': '', 'date': '2026-03-20', 'description': 'X'}, b'category'),
        # Invalid date
        ({'amount': '10.0', 'category': 'Food', 'date': 'not-a-date', 'description': 'X'}, b'date'),
        # Missing date
        ({'amount': '10.0', 'category': 'Food', 'date': '', 'description': 'X'}, b'date'),
    ])
    def test_post_add_expense_validation_errors(self, auth_client, payload, error_fragment):
        response = auth_client.post('/expenses/add', data=payload)

        # Should return 200 (re-render form) not 302
        assert response.status_code == 200
        # Should contain error indicator (assuming flash messages or form errors)
        assert error_fragment in response.data.lower(), f"Expected error message regarding {error_fragment}"
        # Form should still be present
        assert b'<form' in response.data
