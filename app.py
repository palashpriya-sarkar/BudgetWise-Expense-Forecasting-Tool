from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask import Flask, request, jsonify
import sqlite3
import re
import hashlib
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-super-secret-key-change-in-production')
DBNAME = 'auth.db'

def get_db():
    """Database connection with row factory"""
    conn = sqlite3.connect(DBNAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with users table"""
    with app.app_context():
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

def valid_password(password):
    """Production-grade password validation"""
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'\d', password):
        return False
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False
    return True

def hash_password(password):
    """Secure SHA-256 hashing"""
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/')
def index():
    """Serve main auth page with sliding panels"""
    return render_template('index.html')

@app.route('/signup', methods=['POST'])
def signup():
    """Signup with auto-login and redirect"""
    # Handle both JSON and form data
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
        
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    # Validation
    if not all([name, email, password]):
        return jsonify({'status': 'error', 'message': 'All fields required'}), 400
    
    if not valid_password(password):
        return jsonify({'status': 'error', 'message': 'Password must be 8+ chars with uppercase, lowercase, number, special char'}), 400
    
    username = email.split('@')[0]
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # Insert user
        cur.execute('''
            INSERT INTO users (name, email, username, password) 
            VALUES (?, ?, ?, ?)
        ''', (name, email, username, hash_password(password)))
        conn.commit()
        
        # Auto-login by setting session
        session['user_id'] = cur.lastrowid
        session['email'] = email
        session['name'] = name
        
        conn.close()
        return jsonify({'status': 'success', 'message': 'Account created! Redirecting...', 'redirect': '/dashboard'})
        
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Email already exists'}), 400
    except Exception:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Server error'}), 500

@app.route('/login', methods=['POST'])
def login():
    """Login with session and redirect"""
    # Handle both JSON and form data
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
        # Set session
        session['user_id'] = user['id']
        session['email'] = user['email']
        session['name'] = user['name']
        return jsonify({'status': 'success', 'message': 'Login successful!', 'redirect': '/dashboard'})
    else:
        return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401

@app.route('/dashboard')
def dashboard():
    """Protected dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html', user=session.get('name', 'User'))

@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('index'))

# Initialize database on first run
with app.app_context():
    init_db()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
