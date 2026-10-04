import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from database.db import init_db, seed_db, create_user, get_user_by_email
from werkzeug.security import check_password_hash
from functools import wraps



app = Flask(__name__)
app.secret_key = "dev-secret-key-for-spendly"


# ------------------------------------------------------------------ #
# Auth Guards                                                         #
# ------------------------------------------------------------------ #

def guest_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id"):
            return redirect(url_for("landing"))
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# ------------------------------------------------------------------ #



# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
@guest_required
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not all([name, email, password, confirm_password]):
            flash("All fields are required", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match", "error")
            return render_template("register.html")

        try:
            create_user(name, email, password)
            flash("Account created successfully! Please sign in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered", "error")
            return render_template("register.html")
        except Exception:
            flash("An unexpected error occurred", "error")
            return render_template("register.html")


    return render_template("register.html")



@app.route("/login", methods=["GET", "POST"])
@guest_required
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            flash("Please provide both email and password", "error")
            return render_template("login.html")

        user = get_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("landing"))

        flash("Invalid email or password.", "error")
        return render_template("login.html")

    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("landing"))


@app.route("/profile")
@login_required
def profile():
    # Hardcoded data for UI design validation (Step 4)
    context = {
        "user": {
            "name": "Demo User",
            "email": "demo@spendly.com",
            "member_since": "October 2026",
            "initials": "DU"
        },
        "stats": {
            "total_spent": "₹12,450.00",
            "transaction_count": 42,
            "top_category": "Food"
        },
        "transactions": [
            {"date": "2026-10-04", "description": "Dinner at Italian Place", "category": "Food", "amount": "₹1,200.00"},
            {"date": "2026-10-03", "description": "Monthly Internet Bill", "category": "Bills", "amount": "₹850.00"},
            {"date": "2026-10-02", "description": "Weekly Grocery", "category": "Food", "amount": "₹2,400.00"},
            {"date": "2026-10-01", "description": "Uber Ride", "category": "Transport", "amount": "₹320.00"},
        ],
        "categories": [
            {"name": "Food", "total": "₹5,400.00", "percentage": 43},
            {"name": "Bills", "total": "₹3,200.00", "percentage": 25},
            {"name": "Transport", "total": "₹2,100.00", "percentage": 17},
            {"name": "Other", "total": "₹1,750.00", "percentage": 15},
        ]
    }
    return render_template("profile.html", **context)


@app.route("/expenses/add")
@login_required
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
@login_required
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
@login_required
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    with app.app_context():
        init_db()
        seed_db()
    app.run(debug=True, port=5001)
