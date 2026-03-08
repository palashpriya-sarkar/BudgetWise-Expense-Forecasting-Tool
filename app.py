from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import sqlite3
import hashlib
import re
import os
from datetime import datetime, date, timedelta
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

app = Flask(__name__)
app.secret_key = "budgetwise-super-secret-2026"
app.config["TEMPLATES_FOLDER"] = "templates"
app.config["STATIC_FOLDER"] = "static"

DB_NAME = "budgetwise.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            month_year TEXT NOT NULL,
            budget_amount REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, month_year)
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS incomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            source TEXT NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    """)
    conn.commit()
    conn.close()
    print(f"SUCCESS: Database '{DB_NAME}' created/initialized!")

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def valid_password(password):
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"""[!@#$%^&*(),.?":{}|<>]""", password):
        return False
    return True

# ML forecasting functions

def prepare_features_for_forecast(expenses_data):
    """
    Prepare features from daily expense data for ML model
    Returns: X (features), y (targets), feature names
    """
    if len(expenses_data) < 7:  # Need at least a week of data
        return None, None, None

    # Convert to daily aggregates
    daily_expenses = {}
    for exp in expenses_data:
        exp_date = exp['date']
        amount = exp['amount']
        if exp_date in daily_expenses:
            daily_expenses[exp_date] += amount
        else:
            daily_expenses[exp_date] = amount

    # Sort by date
    sorted_dates = sorted(daily_expenses.keys())
    daily_amounts = [daily_expenses[d] for d in sorted_dates]

    if len(daily_amounts) < 7:
        return None, None, None

    # Feature engineering
    features = []
    targets = []

    for i in range(7, len(daily_amounts)):
        # Features: rolling statistics
        window = daily_amounts[i-7:i]

        feature_vector = [
            np.mean(window),           # 7-day average
            np.std(window),            # 7-day std deviation
            np.max(window),            # 7-day max
            np.min(window),            # 7-day min
            window[-1],                # Previous day
            np.mean(window[-3:]),      # 3-day average
            i % 7,                     # Day of week pattern
        ]

        features.append(feature_vector)
        targets.append(daily_amounts[i])

    return np.array(features), np.array(targets), sorted_dates

def calculate_monthly_forecast(user_id):
    """
    Calculate next month's expense forecast using Random Forest
    Returns: forecast_amount, confidence, insights
    """
    conn = get_db()
    cur = conn.cursor()

    # Get last 90 days of expenses
    ninety_days_ago = (date.today() - timedelta(days=90)).strftime('%Y-%m-%d')
    cur.execute("""
        SELECT date, amount, category 
        FROM expenses 
        WHERE user_id = ? AND date >= ?
        ORDER BY date ASC
    """, (user_id, ninety_days_ago))

    expenses_data = [dict(row) for row in cur.fetchall()]
    conn.close()

    if len(expenses_data) < 7:
        return 0, 0, {
            "status": "insufficient_data",
            "message": "Need at least 7 days of expense data for forecasting"
        }

    # Prepare features
    X, y, dates = prepare_features_for_forecast(expenses_data)

    if X is None or len(X) < 5:
        return 0, 0, {
            "status": "insufficient_data",
            "message": "Need more historical data for accurate forecasting"
        }

    # Train Random Forest model
    try:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        model = RandomForestRegressor(
            n_estimators=50,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        model.fit(X_scaled, y)

        # Predict next 30 days
        last_window = y[-7:]
        predictions = []

        for day in range(30):
            # Create feature vector for prediction
            feature_vector = np.array([[
                np.mean(last_window),
                np.std(last_window),
                np.max(last_window),
                np.min(last_window),
                last_window[-1],
                np.mean(last_window[-3:]),
                day % 7
            ]])

            feature_scaled = scaler.transform(feature_vector)
            pred = model.predict(feature_scaled)[0]
            predictions.append(max(0, pred))  # No negative predictions

            # Update window
            last_window = np.append(last_window[1:], pred)

        # Calculate forecast
        monthly_forecast = sum(predictions)
        confidence = model.score(X_scaled, y) * 100

        # Calculate insights
        current_month_avg = np.mean(y[-30:]) if len(y) >= 30 else np.mean(y)
        trend = "increasing" if monthly_forecast > current_month_avg * 30 else "decreasing"

        insights = {
            "status": "success",
            "forecast": monthly_forecast,
            "confidence": confidence,
            "trend": trend,
            "daily_average": monthly_forecast / 30,
            "current_daily_avg": current_month_avg,
            "predictions": predictions[:7]  # Next 7 days
        }

        return monthly_forecast, confidence, insights

    except Exception as e:
        print(f"Forecast error: {e}")
        return 0, 0, {
            "status": "error",
            "message": str(e)
        }

def get_category_insights(user_id):
    """
    Analyze spending by category and provide insights
    """
    conn = get_db()
    cur = conn.cursor()

    # Get current month expenses by category
    today = date.today()
    current_month = today.strftime('%Y-%m')

    cur.execute("""
        SELECT category, SUM(amount) as total, COUNT(*) as count
        FROM expenses
        WHERE user_id = ? AND date LIKE ?
        GROUP BY category
        ORDER BY total DESC
    """, (user_id, f"{current_month}%"))

    categories = [dict(row) for row in cur.fetchall()]

    # Get previous month for comparison
    prev_month = (today.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    cur.execute("""
        SELECT category, SUM(amount) as total
        FROM expenses
        WHERE user_id = ? AND date LIKE ?
        GROUP BY category
    """, (user_id, f"{prev_month}%"))

    prev_categories = {row['category']: row['total'] for row in cur.fetchall()}
    conn.close()

    insights = []
    for cat in categories:
        category_name = cat['category']
        current_total = cat['total']
        prev_total = prev_categories.get(category_name, 0)

        if prev_total > 0:
            change_pct = ((current_total - prev_total) / prev_total) * 100
            if abs(change_pct) > 20:
                insights.append({
                    "category": category_name,
                    "current": current_total,
                    "previous": prev_total,
                    "change": change_pct,
                    "trend": "up" if change_pct > 0 else "down"
                })

    return categories, insights

def generate_budget_suggestions(user_id, forecast, current_expenses, budget):
    """
    Generate personalized budget management suggestions
    """
    suggestions = []

    # Get category breakdown
    categories, insights = get_category_insights(user_id)

    # Suggestion 1: Overall budget status
    if budget > 0:
        remaining = budget - current_expenses
        if remaining < 0:
            suggestions.append({
                "type": "warning",
                "title": "Budget Exceeded",
                "message": f"You've exceeded your budget by ₹{abs(remaining):.0f}. Consider reviewing your spending."
            })
        elif remaining < budget * 0.2:
            suggestions.append({
                "type": "caution",
                "title": "Low Budget Balance",
                "message": f"Only ₹{remaining:.0f} remaining this month. Be cautious with spending."
            })

    # Suggestion 2: Forecast vs Budget
    if forecast > 0 and budget > 0:
        if forecast > budget:
            overshoot = forecast - budget
            suggestions.append({
                "type": "alert",
                "title": "Forecast Exceeds Budget",
                "message": f"Next month's forecast (₹{forecast:.0f}) exceeds typical budget by ₹{overshoot:.0f}. Plan accordingly."
            })

    # Suggestion 3: Category-specific insights
    if categories:
        top_category = categories[0]
        total_expenses = sum(c['total'] for c in categories)
        top_pct = (top_category['total'] / total_expenses) * 100 if total_expenses > 0 else 0

        if top_pct > 40:
            suggestions.append({
                "type": "info",
                "title": f"High {top_category['category']} Spending",
                "message": f"{top_category['category']} accounts for {top_pct:.1f}% of expenses. Consider optimizing this category."
            })

    # Suggestion 4: Spending trend insights
    for insight in insights:
        if insight['trend'] == 'up' and insight['change'] > 30:
            suggestions.append({
                "type": "warning",
                "title": f"Rising {insight['category']} Costs",
                "message": f"{insight['category']} spending increased by {insight['change']:.1f}% from last month."
            })

    # Suggestion 5: Savings recommendation
    if budget > 0 and current_expenses > 0:
        savings_potential = budget * 0.2  # for 20% savings
        if current_expenses < budget - savings_potential:
            suggestions.append({
                "type": "success",
                "title": "Great Savings Progress!",
                "message": f"You're on track to save ₹{(budget - current_expenses):.0f} this month. Keep it up!"
            })

    return suggestions

# routes

@app.route("/signup", methods=["POST"])
def signup():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not all([name, email, password]):
        return jsonify({"status": "error", "message": "All fields required"}), 400

    if not valid_password(password):
        return jsonify({"status": "error", "message": "Password must be 8+ chars with uppercase, lowercase, number, special char"}), 400

    username = email.split("@")[0]

    conn = get_db()
    cur = conn.cursor()

    try:
        cur.execute("INSERT INTO users (name, email, username, password) VALUES (?, ?, ?, ?)",
                   (name, email, username, hash_password(password)))
        conn.commit()
        session["user_id"] = cur.lastrowid
        session["email"] = email
        session["name"] = name
        conn.close()
        return jsonify({"status": "success", "message": "Account created!", "redirect": "/dashboard"})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"status": "error", "message": "Email already exists"}), 400

@app.route("/login", methods=["POST"])
def login():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"status": "error", "message": "Email and password required"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, name, email FROM users WHERE email = ? AND password = ?",
               (email, hash_password(password)))
    user = cur.fetchone()
    conn.close()

    if user:
        session["user_id"] = user["id"]
        session["email"] = user["email"]
        session["name"] = user["name"]
        return jsonify({"status": "success", "message": "Login successful!", "redirect": "/dashboard"})
    else:
        return jsonify({"status": "error", "message": "Invalid credentials"}), 401

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("index"))

    user_id = session["user_id"]
    conn = get_db()
    cur = conn.cursor()

    today = date.today()
    current_month = today.strftime('%Y-%m')

    # Get budget
    cur.execute("SELECT budget_amount FROM budgets WHERE user_id = ? AND month_year = ?",
               (user_id, current_month))
    budget = cur.fetchone()
    budget_amount = budget["budget_amount"] if budget else 0

    # Get total expenses
    cur.execute("SELECT SUM(amount) as total FROM expenses WHERE user_id = ? AND date LIKE ?",
               (user_id, f"{current_month}%"))
    total_expenses = cur.fetchone()["total"] or 0

    # Get category breakdown
    cur.execute("""
        SELECT category, SUM(amount) as total 
        FROM expenses 
        WHERE user_id = ? AND date LIKE ? 
        GROUP BY category
    """, (user_id, f"{current_month}%"))
    categories = {row["category"]: row["total"] for row in cur.fetchall()}

    # Calculate forecast
    forecast_amount, confidence, insights = calculate_monthly_forecast(user_id)

    conn.close()

    return render_template("dashboard.html",
                         user=session.get("name", "User"),
                         total_expenses=total_expenses,
                         budget_amount=budget_amount,
                         forecast_amount=forecast_amount,
                         categories=categories)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/api/get-dashboard-data")
def get_dashboard_data():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session["user_id"]
    today = date.today()
    current_month = today.strftime('%Y-%m')

    conn = get_db()
    cur = conn.cursor()

    # Budget
    cur.execute("SELECT budget_amount FROM budgets WHERE user_id = ? AND month_year = ?",
               (user_id, current_month))
    budget = cur.fetchone()
    budget_amount = budget["budget_amount"] if budget else 0

    # Expenses
    cur.execute("SELECT SUM(amount) as total FROM expenses WHERE user_id = ? AND date LIKE ?",
               (user_id, f"{current_month}%"))
    total_expenses = cur.fetchone()["total"] or 0

    # Income
    cur.execute("SELECT SUM(amount) as total FROM incomes WHERE user_id = ? AND date LIKE ?",
               (user_id, f"{current_month}%"))
    total_income = cur.fetchone()["total"] or 0

    # Categories
    cur.execute("""
        SELECT category, SUM(amount) as total 
        FROM expenses 
        WHERE user_id = ? AND date LIKE ? 
        GROUP BY category
    """, (user_id, f"{current_month}%"))
    categories = {row["category"]: row["total"] for row in cur.fetchall()}

    conn.close()

    # Calculate forecast
    forecast_amount, confidence, insights = calculate_monthly_forecast(user_id)

    return jsonify({
        "budget": budget_amount,
        "expenses": total_expenses,
        "income": total_income,
        "forecast": forecast_amount,
        "forecast_confidence": confidence,
        "categories": categories
    })

@app.route("/api/update-budget", methods=["POST"])
def update_budget():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    user_id = session["user_id"]
    month_year = data["monthyear"]
    amount = float(data["amount"])

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO budgets (user_id, month_year, budget_amount) VALUES (?, ?, ?)",
               (user_id, month_year, amount))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "amount": amount})

@app.route("/api/add-expense", methods=["POST"])
def add_expense():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    user_id = session["user_id"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO expenses (user_id, category, amount, date, description) VALUES (?, ?, ?, ?, ?)",
               (user_id, data["category"], data["amount"], data["date"], data.get("description", "")))
    conn.commit()
    conn.close()

    return jsonify({"success": True})

@app.route("/api/add-income", methods=["POST"])
def add_income():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    user_id = session["user_id"]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO incomes (user_id, source, amount, date, description) VALUES (?, ?, ?, ?, ?)",
               (user_id, data["source"], data["amount"], data["date"], data.get("description", "")))
    conn.commit()
    conn.close()

    return jsonify({"success": True})

@app.route("/api/get-transactions")
def get_transactions():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session["user_id"]
    conn = get_db()
    cur = conn.cursor()

    # Get expenses
    cur.execute("""
        SELECT 'expense' as type, category as name, amount, date 
        FROM expenses 
        WHERE user_id = ? 
        ORDER BY date DESC, created_at DESC 
        LIMIT 5
    """, (user_id,))
    expenses = cur.fetchall()

    # Get incomes
    cur.execute("""
        SELECT 'income' as type, source as name, amount, date 
        FROM incomes 
        WHERE user_id = ? 
        ORDER BY date DESC, created_at DESC 
        LIMIT 5
    """, (user_id,))
    incomes = cur.fetchall()

    transactions = []
    for exp in expenses:
        transactions.append({
            "type": exp["type"],
            "name": exp["name"],
            "amount": exp["amount"],
            "date": exp["date"]
        })
    for inc in incomes:
        transactions.append({
            "type": inc["type"],
            "name": inc["name"],
            "amount": inc["amount"],
            "date": inc["date"]
        })

    transactions.sort(key=lambda x: x["date"], reverse=True)
    transactions = transactions[:5]

    conn.close()
    return jsonify(transactions)

@app.route("/api/get-total-income")
def get_total_income():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session["user_id"]
    today = date.today()
    current_month = today.strftime('%Y-%m')

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT SUM(amount) as total FROM incomes WHERE user_id = ? AND date LIKE ?",
               (user_id, f"{current_month}%"))
    total_income = cur.fetchone()["total"] or 0
    conn.close()

    return jsonify({"total": total_income})

#new analytics api endpoints

@app.route("/api/get-forecast-details")
def get_forecast_details():
    """
    Get detailed forecast information including insights and predictions
    """
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session["user_id"]
    forecast_amount, confidence, insights = calculate_monthly_forecast(user_id)

    return jsonify({
        "forecast": forecast_amount,
        "confidence": confidence,
        "insights": insights
    })

@app.route("/api/get-analytics-data")
def get_analytics_data():
    """
    Get comprehensive analytics data for the analytics page
    """
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session["user_id"]
    today = date.today()
    current_month = today.strftime('%Y-%m')

    conn = get_db()
    cur = conn.cursor()

    # Get budget
    cur.execute("SELECT budget_amount FROM budgets WHERE user_id = ? AND month_year = ?",
               (user_id, current_month))
    budget = cur.fetchone()
    budget_amount = budget["budget_amount"] if budget else 0

    # Get current month expenses
    cur.execute("SELECT SUM(amount) as total FROM expenses WHERE user_id = ? AND date LIKE ?",
               (user_id, f"{current_month}%"))
    current_expenses = cur.fetchone()["total"] or 0

    conn.close()

    # Get forecast
    forecast_amount, confidence, forecast_insights = calculate_monthly_forecast(user_id)

    # Get category insights
    categories, category_insights = get_category_insights(user_id)

    # Get budget suggestions
    suggestions = generate_budget_suggestions(user_id, forecast_amount, current_expenses, budget_amount)

    # Get weekly trend data (last 4 weeks)
    conn = get_db()
    cur = conn.cursor()

    weekly_data = []
    for week in range(4):
        week_start = today - timedelta(days=(week+1)*7)
        week_end = today - timedelta(days=week*7)

        cur.execute("""
            SELECT SUM(amount) as total 
            FROM expenses 
            WHERE user_id = ? AND date BETWEEN ? AND ?
        """, (user_id, week_start.strftime('%Y-%m-%d'), week_end.strftime('%Y-%m-%d')))

        week_total = cur.fetchone()["total"] or 0
        weekly_data.append({
            "week": f"Week {4-week}",
            "amount": week_total
        })

    conn.close()

    return jsonify({
        "forecast": {
            "amount": forecast_amount,
            "confidence": confidence,
            "insights": forecast_insights
        },
        "categories": categories,
        "category_insights": category_insights,
        "suggestions": suggestions,
        "weekly_trend": list(reversed(weekly_data)),
        "current_expenses": current_expenses,
        "budget": budget_amount
    })

@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("index"))
    return render_template("profile.html", 
                         user=session.get("name", "User"),
                         email=session.get("email"))

@app.route("/analytics")
def analytics():
    if "user_id" not in session:
        return redirect(url_for("index"))
    return render_template("analytics.html", user=session.get("name", "User"))

@app.route("/settings")
def settings():
    if "user_id" not in session:
        return redirect(url_for("index"))
    return render_template("settings.html", user=session.get("name", "User"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
