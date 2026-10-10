import sqlite3
import random
from datetime import datetime, timedelta
from database.db import get_db

def seed_expenses(user_id, count, months):
    categories = {
        "Food": (50, 800, 0.30, ["Lunch at Cafe", "Dinner with friends", "Grocery shopping", "Street food", "Coffee"]),
        "Transport": (20, 500, 0.20, ["Uber ride", "Auto rickshaw", "Petrol", "Metro recharge", "Bus fare"]),
        "Bills": (200, 3000, 0.15, ["Electricity bill", "Water bill", "Internet bill", "Phone recharge", "Rent"]),
        "Health": (100, 2000, 0.05, ["Pharmacy", "Doctor consultation", "Health checkup", "Vitamin supplements", "Dental care"]),
        "Entertainment": (100, 1500, 0.10, ["Movie ticket", "Streaming subscription", "Gaming", "Book purchase", "Concert"]),
        "Shopping": (200, 5000, 0.10, ["New clothes", "Electronics", "Home decor", "Gift", "Footwear"]),
        "Other": (50, 1000, 0.10, ["Gift wrap", "Postage", "Parking fee", "Donation", "Miscellaneous"]),
    }

    cat_list = list(categories.keys())
    weights = [categories[cat][2] for cat in cat_list]

    try:
        conn = get_db()
        
        # Verify user exists
        user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            print(f"No user found with id {user_id}.")
            return

        expenses = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)

        for _ in range(count):
            category = random.choices(cat_list, weights=weights)[0]
            min_amt, max_amt, _, descriptions = categories[category]
            
            amount = round(random.uniform(min_amt, max_amt), 2)
            description = random.choice(descriptions)
            
            # Random date within range
            delta_days = random.randint(0, months * 30)
            date = (end_date - timedelta(days=delta_days)).strftime("%Y-%m-%d")
            
            expenses.append((user_id, amount, category, date, description))

        with conn:
            conn.executemany(
                "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                expenses
            )
        
        print(f"Successfully inserted {len(expenses)} expenses.")
        print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        
        # Sample 5 records
        sample = conn.execute("SELECT date, category, amount, description FROM expenses WHERE user_id = ? ORDER BY RANDOM() LIMIT 5", (user_id,)).fetchall()
        print("\nSample records:")
        for row in sample:
            print(f"{row['date']} | {row['category']} | Rs.{row['amount']} | {row['description']}")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        print("Usage: python seed_expenses.py <user_id> <count> <months>")
    else:
        seed_expenses(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]))
