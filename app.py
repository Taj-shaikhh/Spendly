import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from database.db import init_db, seed_db, create_user, get_user_by_email, get_category_breakdown, get_recent_transactions, get_user_details, get_spending_summary, insert_expense, EXPENSE_CATEGORIES
from werkzeug.security import check_password_hash
from functools import wraps
import datetime



app = Flask(__name__)
app.secret_key = "dev-secret-key-for-spendly"


# ------------------------------------------------------------------ #
# Helpers                                                                #
# ------------------------------------------------------------------ #

def _validate_dates(date_from, date_to):
    """Validates date strings and ensures start date is before end date."""
    if not date_from and not date_to:
        return None, None, True

    try:
        if date_from:
            datetime.datetime.strptime(date_from, "%Y-%m-%d")
        if date_to:
            datetime.datetime.strptime(date_to, "%Y-%m-%d")

        if date_from and date_to and date_from > date_to:
            return None, None, False
    except ValueError:
        return None, None, False

    return date_from, date_to, True

def _get_date_presets():
    """Calculates the fixed date ranges for the profile presets."""
    today = datetime.date.today()
    first_of_month = today.replace(day=1)

    return {
        "this_month": {
            "from": first_of_month.strftime("%Y-%m-%d"),
            "to": today.strftime("%Y-%m-%d")
        },
        "last_3_months": {
            "from": (today - datetime.timedelta(days=90)).strftime("%Y-%m-%d"),
            "to": today.strftime("%Y-%m-%d")
        },
        "last_6_months": {
            "from": (today - datetime.timedelta(days=180)).strftime("%Y-%m-%d"),
            "to": today.strftime("%Y-%m-%d")
        }
    }

# ------------------------------------------------------------------ #
# Auth Guards                                                         #
# ------------------------------------------------------------------ #

def guest_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id"):
            return redirect(url_for("profile"))
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
@guest_required
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
            return redirect(url_for("profile"))

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
    user_id = session.get("user_id")

    # 1. Date Filtering Logic
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    # Validate dates
    import datetime
    valid_dates = True
    if date_from or date_to:
        try:
            if date_from:
                datetime.datetime.strptime(date_from, "%Y-%m-%d")
            if date_to:
                datetime.datetime.strptime(date_to, "%Y-%m-%d")

            if date_from and date_to and date_from > date_to:
                flash("Start date must be before end date.", "error")
                date_from = date_to = None
                valid_dates = False
        except ValueError:
            date_from = date_to = None
            valid_dates = False

    # Calculate Presets
    today = datetime.date.today()
    first_of_month = today.replace(day=1)

    presets = {
        "this_month": {
            "from": first_of_month.strftime("%Y-%m-%d"),
            "to": today.strftime("%Y-%m-%d")
        },
        "last_3_months": {
            "from": (today - datetime.timedelta(days=90)).strftime("%Y-%m-%d"),
            "to": today.strftime("%Y-%m-%d")
        },
        "last_6_months": {
            "from": (today - datetime.timedelta(days=180)).strftime("%Y-%m-%d"),
            "to": today.strftime("%Y-%m-%d")
        }
    }

    # 2. Fetch User Details
    user_row = get_user_details(user_id)
    if not user_row:
        abort(404)

    # Format member_since (from 'YYYY-MM-DD HH:MM:SS' to 'Month YYYY')
    created_at = user_row["created_at"]
    dt = datetime.datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
    member_since = dt.strftime("%B %Y")

    user_data = {
        "name": user_row["name"],
        "email": user_row["email"],
        "member_since": member_since,
        "initials": "".join([n[0].upper() for n in user_row["name"].split()])
    }

    # 3. Fetch Spending Summary
    summary = get_spending_summary(user_id, date_from, date_to)
    stats = {
        "total_spent": f"₹{summary['total_spent']:,.2f}",
        "transaction_count": summary["transaction_count"],
        "top_category": summary["top_category"] or "None"
    }

    # 4. Fetch Recent Transactions
    transactions_rows = get_recent_transactions(user_id, date_from=date_from, date_to=date_to)
    transactions = [
        {
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": f"₹{row['amount']:,.2f}"
        }
        for row in transactions_rows
    ]

    # 5. Fetch Category Breakdown
    breakdown_rows = get_category_breakdown(user_id, date_from, date_to)
    total_spend = sum(row["total"] for row in breakdown_rows)

    categories = []
    for row in breakdown_rows:
        percentage = 0
        if total_spend > 0:
            percentage = round((row["total"] / total_spend) * 100)

        categories.append({
            "name": row["category"],
            "total": f"₹{row['total']:,.2f}",
            "percentage": percentage
        })

    context = {
        "user": user_data,
        "stats": stats,
        "transactions": transactions,
        "categories": categories,
        "date_from": date_from,
        "date_to": date_to,
        "presets": presets
    }
    return render_template("profile.html", **context)


@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense():
    if request.method == "POST":
        amount_str = request.form.get("amount")
        category = request.form.get("category")
        date_str = request.form.get("date")
        description = request.form.get("description", "").strip() or None

        # Validation
        errors = []
        amount = None

        try:
            amount = float(amount_str)
            if amount <= 0:
                errors.append("Amount must be greater than zero.")
        except (TypeError, ValueError):
            errors.append("Amount must be a valid number.")

        allowed_categories = EXPENSE_CATEGORIES
        if not category or category not in allowed_categories:
            errors.append("Please select a valid category.")

        if not date_str:
            errors.append("Date is required.")
        else:
            try:
                datetime.datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                errors.append("Invalid date format.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("add_expense.html",
                                   form_data=request.form,
                                   today=datetime.date.today().strftime("%Y-%m-%d"),
                                   categories=EXPENSE_CATEGORIES)

        # Success - Save to DB
        user_id = session.get("user_id")
        insert_expense(user_id, amount, category, date_str, description)
        flash("Expense added successfully!", "success")
        return redirect(url_for("profile"))

    return render_template("add_expense.html", today=datetime.date.today().strftime("%Y-%m-%d"), categories=EXPENSE_CATEGORIES)


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
