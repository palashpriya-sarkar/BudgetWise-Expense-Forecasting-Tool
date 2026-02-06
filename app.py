from flask import Flask, request, jsonify, render_template, redirect, url_for, session
import sqlite3
import hashlib
import re
import os
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = 'budgetwise-super-secret-2026'
app.config['TEMPLATES_FOLDER'] = 'templates'
app.config['STATIC_FOLDER'] = 'static'

DBNAME = 'budgetwise.db'

def get_db():
    conn = sqlite3.connect(DBNAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = sqlite3.connect(DBNAME)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.executescript('''
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
    ''')
    
    conn.commit()
    conn.close()
    print("SUCCESS: Database '{}' created/initialized!".format(DBNAME))

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def valid_password(password):
    if len(password) < 8: return False
    if not re.search(r'[A-Z]', password): return False
    if not re.search(r'[a-z]', password): return False
    if not re.search(r'\d', password): return False
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password): return False
    return True

# AUTH ROUTES (MUST HAVE THESE!)
@app.route('/signup', methods=['POST'])
def signup():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
        
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not all([name, email, password]):
        return jsonify({'status': 'error', 'message': 'All fields required'}), 400
    
    if not valid_password(password):
        return jsonify({'status': 'error', 'message': 'Password must be 8+ chars with uppercase, lowercase, number, special char'}), 400
    
    username = email.split('@')[0]
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('INSERT INTO users (name, email, username, password) VALUES (?, ?, ?, ?)',
                   (name, email, username, hash_password(password)))
        conn.commit()
        session['user_id'] = cur.lastrowid
        session['email'] = email
        session['name'] = name
        conn.close()
        return jsonify({'status': 'success', 'message': 'Account created!', 'redirect': '/dashboard'})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Email already exists'}), 400

@app.route('/login', methods=['POST'])
def login():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
        
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'status': 'error', 'message': 'Email and password required'}), 400
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('SELECT id, name, email FROM users WHERE email = ? AND password = ?',
               (email, hash_password(password)))
    user = cur.fetchone()
    
    conn.close()
    
    if user:
        session['user_id'] = user['id']
        session['email'] = user['email']
        session['name'] = user['name']
        return jsonify({'status': 'success', 'message': 'Login successful!', 'redirect': '/dashboard'})
    else:
        return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    user_id = session['user_id']
    conn = get_db()
    cur = conn.cursor()
    
    today = date.today()
    current_month = today.strftime('%Y-%m')
    
    cur.execute('SELECT budget_amount FROM budgets WHERE user_id = ? AND month_year = ?', 
                (user_id, current_month))
    budget = cur.fetchone()
    budget_amount = budget['budget_amount'] if budget else 0
    
    cur.execute('SELECT SUM(amount) as total FROM expenses WHERE user_id = ? AND date LIKE ?', 
                (user_id, f'{current_month}-%'))
    total_expenses = cur.fetchone()['total'] or 0
    
    cur.execute('SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? AND date LIKE ? GROUP BY category',
                (user_id, f'{current_month}-%'))
    categories = {row['category']: row['total'] for row in cur.fetchall()}
    
    forecast_amount = 0  # Will calculate when data exists
    
    conn.close()
    
    return render_template('dashboard.html', 
                         user=session.get('name', 'User'),
                         total_expenses=total_expenses,
                         budget_amount=budget_amount,
                         forecast_amount=forecast_amount,
                         categories=categories)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/get_dashboard_data')
def get_dashboard_data():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user_id = session['user_id']
    today = date.today()
    current_month = today.strftime('%Y-%m')
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('SELECT budget_amount FROM budgets WHERE user_id = ? AND month_year = ?', 
                (user_id, current_month))
    budget = cur.fetchone()
    budget_amount = budget['budget_amount'] if budget else 0
    
    cur.execute('SELECT SUM(amount) as total FROM expenses WHERE user_id = ? AND date LIKE ?', 
                (user_id, f'{current_month}-%'))
    total_expenses = cur.fetchone()['total'] or 0
    
    cur.execute('SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? AND date LIKE ? GROUP BY category',
                (user_id, f'{current_month}-%'))
    categories = {row['category']: row['total'] for row in cur.fetchall()}
    
    conn.close()
    
    return jsonify({
        'budget': budget_amount,
        'expenses': total_expenses,
        'forecast': 0,
        'categories': categories
    })

@app.route('/api/update_budget', methods=['POST'])
def update_budget():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    user_id = session['user_id']
    month_year = data['month_year']
    amount = float(data['amount'])
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('INSERT OR REPLACE INTO budgets (user_id, month_year, budget_amount) VALUES (?, ?, ?)',
                (user_id, month_year, amount))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'amount': amount})

@app.route('/api/add_expense', methods=['POST'])
def add_expense():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    user_id = session['user_id']
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('INSERT INTO expenses (user_id, category, amount, date, description) VALUES (?, ?, ?, ?, ?)',
                (user_id, data['category'], data['amount'], data['date'], data.get('description', '')))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
