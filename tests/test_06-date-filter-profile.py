import pytest
import datetime
from app import app as flask_app
from database.db import init_db, create_user

@pytest.fixture
def app():
    flask_app.config.update({
        'TESTING': True,
        'DATABASE': ':memory:',
        'SECRET_KEY': 'test-secret',
        'WTF_CSRF_ENABLED': False,
    })
    # Override get_db in database.db to use memory db for tests
    import database.db
    original_get_db = database.db.get_db
    
    # Simple in-memory connection management for tests
    _conn = None
    def mock_get_db():
        nonlocal _conn
        if _conn is None:
            import sqlite3
            _conn = sqlite3.connect(':memory:')
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA foreign_keys = ON")
        return _conn

    database.db.get_db = mock_get_db
    
    with flask_app.app_context():
        init_db()
        yield flask_app
    
    database.db.get_db = original_get_db

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_client(client):
    """A test client that is already logged in."""
    from database.db import create_user
    # Ensure user is created in the mocked memory DB
    create_user("Test User", "test@example.com", "password123")
    
    client.post('/login', data={'email': 'test@example.com', 'password': 'password123'})
    return client

def seed_expenses(client, user_id, expenses):
    """Helper to insert expenses into the test DB."""
    import database.db
    conn = database.db.get_db()
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        expenses
    )
    conn.commit()

class TestDateFilterProfile:
    
    def test_profile_auth_guard(self, client):
        """Verify that unauthenticated requests to /profile are redirected to login."""
        response = client.get('/profile')
        assert response.status_code == 302
        assert '/login' in response.location

    def test_profile_all_time_unfiltered(self, auth_client):
        """Verify that visiting /profile without dates shows all expenses."""
        import database.db
        conn = database.db.get_db()
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        user_id = user['id']
        
        seed_expenses(auth_client, user_id, [
            (user_id, 100.0, "Food", "2023-01-01", "Old Expense"),
            (user_id, 200.0, "Rent", "2023-02-01", "Older Expense"),
        ])
        
        response = auth_client.get('/profile')
        assert response.status_code == 200
        assert b"\xe2\x82\xb9300.00" in response.data
        assert b"2" in response.data # Transaction count

    def test_profile_custom_date_range_filtering(self, auth_client):
        """Verify that specific date_from and date_to filter the results correctly."""
        import database.db
        conn = database.db.get_db()
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        user_id = user['id']
        
        seed_expenses(auth_client, user_id, [
            (user_id, 10.0, "Food", "2023-01-01", "Outside Range Before"),
            (user_id, 50.0, "Food", "2023-01-10", "Inside Range"),
            (user_id, 60.0, "Food", "2023-01-15", "Inside Range"),
            (user_id, 100.0, "Food", "2023-01-20", "Outside Range After"),
        ])
        
        # Filter between 10th and 15th inclusive
        response = auth_client.get('/profile?date_from=2023-01-10&date_to=2023-01-15')
        
        assert response.status_code == 200
        # Total should be 50 + 60 = 110
        assert b"\xe2\x82\xb9110.00" in response.data
        # Only 2 transactions should be listed
        assert b"Inside Range" in response.data
        assert b"Outside Range Before" not in response.data
        assert b"Outside Range After" not in response.data

    def test_profile_date_range_inversion_error(self, auth_client):
        """Verify that date_from > date_to triggers a flash error and unfiltered view."""
        import database.db
        conn = database.db.get_db()
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        user_id = user['id']
        
        seed_expenses(auth_client, user_id, [
            (user_id, 100.0, "Food", "2023-01-01", "Expense 1"),
        ])
        
        # Inverted dates
        response = auth_client.get('/profile?date_from=2023-01-10&date_to=2023-01-01')
        
        assert response.status_code == 200
        assert b"Start date must be before end date." in response.data
        # Should fall back to unfiltered view (showing the expense)
        assert b"\xe2\x82\xb9100.00" in response.data

    def test_profile_malformed_date_fallback(self, auth_client):
        """Verify that malformed date strings fall back to unfiltered view silently."""
        import database.db
        conn = database.db.get_db()
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        user_id = user['id']
        
        seed_expenses(auth_client, user_id, [
            (user_id, 100.0, "Food", "2023-01-01", "Expense 1"),
        ])
        
        # Malformed date
        response = auth_client.get('/profile?date_from=not-a-date&date_to=2023-01-01')
        
        assert response.status_code == 200
        # Should show the unfiltered data
        assert b"\xe2\x82\xb9100.00" in response.data

    def test_profile_empty_range_results(self, auth_client):
        """Verify that a range with no expenses returns zeroed totals without crashing."""
        import database.db
        conn = database.db.get_db()
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        user_id = user['id']
        
        seed_expenses(auth_client, user_id, [
            (user_id, 100.0, "Food", "2023-01-01", "Expense 1"),
        ])
        
        # Request range in 2024
        response = auth_client.get('/profile?date_from=2024-01-01&date_to=2024-01-31')
        
        assert response.status_code == 200
        assert b"\xe2\x82\xb90.00" in response.data
        assert b"0" in response.data # Transaction count
        # Category breakdown should be empty or show "None" as per spec
        assert b"None" in response.data or b"\xe2\x82\xb90.00" in response.data

    def test_profile_category_breakdown_filtering(self, auth_client):
        """Verify that category breakdown respects the date filter."""
        import database.db
        conn = database.db.get_db()
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        user_id = user['id']
        
        seed_expenses(auth_client, user_id, [
            (user_id, 100.0, "Food", "2023-01-01", "Food 1"),
            (user_id, 100.0, "Food", "2023-02-01", "Food 2"),
            (user_id, 50.0, "Transport", "2023-02-01", "Transport 1"),
        ])
        
        # Filter for February only
        response = auth_client.get('/profile?date_from=2023-02-01&date_to=2023-02-28')
        
        # Total should be 100 (Food) + 50 (Transport) = 150
        assert b"\xe2\x82\xb9150.00" in response.data
        # Food should be 100/150 = 67%
        assert b"67%" in response.data
        # Transport should be 50/150 = 33%
        assert b"33%" in response.data
        # January food expense should not be counted
        assert b"\xe2\x82\xb9200.00" not in response.data
