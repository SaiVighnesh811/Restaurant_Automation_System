# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
from werkzeug.security import generate_password_hash
from functools import wraps
from datetime import datetime, timedelta
import json
import logging
import traceback
import os

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# ---------------------------------
# MySQL Configuration for Railway
# ---------------------------------
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST', 'crossover.proxy.rlwy.net')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', 'ydQXLgRRESemchLhQbKDoHVGBWXsbGyY')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB', 'railway')
app.config['MYSQL_PORT'] = int(os.getenv('MYSQL_PORT', 33448))

mysql = MySQL(app)

# basic logger
logging.basicConfig(level=logging.INFO)

# -----------------------
# Small helper
# -----------------------
def dict_from_row(cursor, row):
    """Convert a MySQL row tuple to dict using cursor.description.
       If description is None, return an empty dict to avoid crashes."""
    if not cursor.description:
        return {}
    cols = [c[0] for c in cursor.description]
    return dict(zip(cols, row))

# ---------------------------------
# Database Initialization
# ---------------------------------
def init_database():
    """Initialize all required database tables"""
    cursor = mysql.connection.cursor()
    try:
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role ENUM('customer', 'owner', 'chef', 'clerk') DEFAULT 'customer',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        # Orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INT AUTO_INCREMENT PRIMARY KEY,
                customer_id INT,
                customer_name VARCHAR(255),
                customer_email VARCHAR(255),
                subtotal DECIMAL(10,2) DEFAULT 0,
                discount_amount DECIMAL(10,2) DEFAULT 0,
                discount_percent DECIMAL(5,2) DEFAULT 0,
                final_total DECIMAL(10,2) DEFAULT 0,
                currency VARCHAR(10) DEFAULT 'INR',
                payment_provider VARCHAR(50),
                provider_payment_id VARCHAR(255),
                payment_status ENUM('pending', 'paid', 'failed') DEFAULT 'pending',
                current_status ENUM('placed', 'preparing', 'ready', 'served', 'delivered', 'cancelled') DEFAULT 'placed',
                table_no VARCHAR(50),
                meta JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        # Order items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_id INT,
                item_name VARCHAR(255) NOT NULL,
                qty INT NOT NULL,
                unit_price DECIMAL(10,2) NOT NULL,
                total_price DECIMAL(10,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Employees table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                role ENUM('chef', 'waiter', 'clerk') NOT NULL,
                status ENUM('active', 'inactive') DEFAULT 'active',
                hire_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        # Ingredients table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ingredients (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                current_stock DECIMAL(10,2) DEFAULT 0,
                unit VARCHAR(50) NOT NULL,
                reorder_level DECIMAL(10,2) DEFAULT 0,
                initial_stock DECIMAL(10,2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        # Inventory transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                ingredient_id INT,
                transaction_type ENUM('purchase', 'usage', 'restock', 'initial', 'adjustment') NOT NULL,
                quantity DECIMAL(10,2) NOT NULL,
                note TEXT,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Purchase orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_orders (
                id INT AUTO_INCREMENT PRIMARY KEY,
                po_number VARCHAR(100) UNIQUE NOT NULL,
                status ENUM('pending', 'ordered', 'received', 'cancelled') DEFAULT 'pending',
                total_amount DECIMAL(10,2) DEFAULT 0,
                supplier_info JSON,
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        # Purchase order items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_order_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                po_id INT,
                ingredient_id INT,
                quantity DECIMAL(10,2) NOT NULL,
                unit_price DECIMAL(10,2) NOT NULL,
                total_price DECIMAL(10,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Expenses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                expense_number VARCHAR(50) UNIQUE,
                expense_date DATE NOT NULL,
                expense_type VARCHAR(100) NOT NULL,
                supplier_name VARCHAR(255),
                payee VARCHAR(255),
                description TEXT,
                amount DECIMAL(10,2) NOT NULL,
                payment_mode VARCHAR(50) DEFAULT 'Cash',
                created_by INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        mysql.connection.commit()
        print("Database tables initialized successfully")
        
    except Exception as e:
        mysql.connection.rollback()
        print(f"Error initializing database: {e}")
        raise e
    finally:
        cursor.close()

def create_default_owner():
    """Create a default owner account for testing"""
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE email = 'owner@restaurant.com'")
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
                ('Restaurant Owner', 'owner@restaurant.com', 'owner123', 'owner')
            )
            mysql.connection.commit()
            print("Default owner account created")
    except Exception as e:
        print(f"Error creating default owner: {e}")
    finally:
        cursor.close()

# Initialize database on first request
@app.before_first_request
def initialize_app():
    try:
        init_database()
        create_default_owner()
    except Exception as e:
        print(f"Initialization error: {e}")

# ---------------------------------
# HOME PAGE
# ---------------------------------
@app.route('/')
def home():
    return render_template('landing.html')

# ---------------------------------
# Logout (safe route)
# ---------------------------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ---------------------------------
# SIGNUP PAGE
# ---------------------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # Get form values
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role')

        # Basic validation
        if not username or not email or not password or not role:
            flash("Please fill all fields", "danger")
            return redirect(url_for('signup'))

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('signup'))

        cursor = mysql.connection.cursor()
        try:
            # Check if email already exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash("Email already registered", "danger")
                return redirect(url_for('signup'))

            cursor.execute(
                "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
                (username, email, password, role)
            )
            mysql.connection.commit()
            
            # Auto-login after signup
            cursor.execute("SELECT id, username, email, role FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            
            if user:
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['email'] = user[2]
                session['role'] = user[3]

            flash("Account created successfully!", "success")

            # Check if there's a return URL from payment page
            return_url = request.args.get('return_url') or request.form.get('return_url')
            if return_url:
                return redirect(return_url)
                
            return redirect(url_for('login'))
                
        except Exception as e:
            mysql.connection.rollback()
            app.logger.exception("Error creating account")
            flash("Error creating account: " + str(e), "danger")
            return redirect(url_for('signup'))
        finally:
            cursor.close()

    # For GET request, check if there's a return URL
    return_url = request.args.get('return_url')
    return render_template('signup.html', return_url=return_url)

# ---------------------------------
# LOGIN PAGE
# ---------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # Validate inputs
        if not email or not password:
            flash("Provide email and password", "danger")
            return redirect(url_for('login'))

        cursor = mysql.connection.cursor()
        try:
            cursor.execute("SELECT id, username, email, password, role FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
        finally:
            cursor.close()

        if user:
            user_id, username, db_email, db_password, role = user

            # DIRECT comparison (plain text)
            if password == db_password:
                # successful login
                session['user_id'] = user_id
                session['username'] = username
                session['email'] = db_email
                session['role'] = role

                flash("Login successful", "success")

                # Check if there's a return URL from payment page
                return_url = request.args.get('return_url') or request.form.get('return_url')
                if return_url:
                    return redirect(return_url)
                
                # redirect by role
                if role and role.lower() == 'customer':
                    return redirect(url_for('show_menu'))
                elif role and role.lower() == 'owner':
                    return redirect(url_for('owner_dashboard'))
                elif role and role.lower() == 'chef':
                    return redirect(url_for('chef_dashboard'))
                elif role and role.lower() == 'clerk':
                    return redirect(url_for('clerk_dashboard'))
                else:
                    return redirect(url_for('home'))
            else:
                flash("Incorrect password", "danger")
                return redirect(url_for('login'))
        else:
            flash("Email not registered", "danger")
            return redirect(url_for('login'))

    # For GET request, check if there's a return URL
    return_url = request.args.get('return_url')
    return render_template('login.html', return_url=return_url)

# ---------------------------------
# FORGOT PASSWORD PAGE
# ---------------------------------
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email:
            flash("Please enter your email.", "danger")
            return render_template('forgot_password.html')

        cursor = mysql.connection.cursor()
        try:
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            
            if user:
                # Email exists, redirect to reset password page
                return redirect(url_for('reset_password', email=email))
            else:
                # Email doesn't exist
                flash("Email not found. Please check your email address.", "danger")
                return render_template('forgot_password.html')
                
        except Exception as e:
            app.logger.exception("forgot_password error")
            flash("An error occurred. Please try again.", "danger")
            return render_template('forgot_password.html')
        finally:
            cursor.close()

    return render_template('forgot_password.html')

# ---------------------------------
# RESET PASSWORD PAGE
# ---------------------------------
@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    email = request.args.get('email', '') or request.form.get('email', '')
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not email or not new_password or not confirm_password:
            flash("All fields are required.", "danger")
            return render_template('reset_password.html', email=email)

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('reset_password.html', email=email)

        if len(new_password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template('reset_password.html', email=email)

        cursor = mysql.connection.cursor()
        try:
            # Update password
            cursor.execute(
                "UPDATE users SET password = %s WHERE email = %s",
                (new_password, email)
            )
            mysql.connection.commit()

            flash("Password reset successfully! Please login with your new password.", "success")
            return redirect(url_for('login'))
                
        except Exception as e:
            mysql.connection.rollback()
            app.logger.exception("reset_password error")
            flash("An error occurred. Please try again.", "danger")
            return render_template('reset_password.html', email=email)
        finally:
            cursor.close()

    # GET request - show reset password form
    return render_template('reset_password.html', email=email)

# ---------------------------------
# MENU PAGE
# ---------------------------------
@app.route('/menupage')
def show_menu():
    return render_template('menu1.html')

# ---------------------------------
# OWNER DASHBOARD PAGE (open access)
# ---------------------------------
@app.route('/owner-dashboard')
def owner_dashboard():
    return render_template('manager_dash.html', logout_url=url_for('logout'),user_role=session.get('role'))

# ---------------------------------
# CHEF DASHBOARD (open access)
# ---------------------------------
@app.route('/chef-dashboard')
def chef_dashboard():
    return render_template('chef-dashboard.html', logout_url=url_for('logout'),user_role=session.get('role'))

# ---------------------------------
# WAITER DASHBOARD (open access)
# ---------------------------------
@app.route('/clerk-dashboard')
def clerk_dashboard():
    return render_template('waiter-dashboard.html', logout_url=url_for('logout'),user_role=session.get('role'))

# ---------------------------------
# Manager Menu Page (open access)
# ---------------------------------
@app.route('/manager-menu')
def manager_menu():
    return render_template('manager_menu.html', logout_url=url_for('logout'), user_role=session.get('role'))

# ---------------------------------
# Manager Employees Page (open access)
# ---------------------------------
@app.route('/manager-employees')
def manager_employees():
    return render_template('manager_employees.html', logout_url=url_for('logout'), user_role=session.get('role'))

# ---------------------------------
# Inventory Pages (open access)
# ---------------------------------
@app.route("/owner-dashboard/ingredient_stock")
def ingredient_stock():
    return render_template("ingredient_stock.html", logout_url=url_for('logout'))

@app.route("/owner-dashboard/low_stock")
def low_stock():
    return render_template("lowstock.html", logout_url=url_for('logout'))

# ---------------------------------
# Purchase Order Pages (open)
# ---------------------------------
@app.route("/owner-dashboard/generate_po")
def generate_po():
    return render_template("generate_po.html", logout_url=url_for('logout'))

@app.route("/owner-dashboard/purchase_order")
def purchase_order():
    return render_template("purchase_order.html", logout_url=url_for('logout'))

# ---------------------------------
# Reports Pages (open)
# ---------------------------------
@app.route("/owner-dashboard/daily_sales")
def daily_sales():
    return render_template("daily_sales.html", logout_url=url_for('logout'))

@app.route("/owner-dashboard/monthly_sales")
def monthly_sales():
    return render_template("monthly_sales.html", logout_url=url_for('logout'))

@app.route("/owner-dashboard/expense_report")
def expense_report():
    return render_template("expense_report.html", logout_url=url_for('logout'))

# ---------------------------------
# Analytics Page (open)
# ---------------------------------
@app.route("/owner-dashboard/analytics")
def analytics():
    return render_template("analytics.html", logout_url=url_for('logout'))

# ---------------------------------
# Payment Page (open)
# ---------------------------------
@app.route("/payment")
def payment():
    return render_template("paymentpage.html", logout_url=url_for('logout'))

# -----------------------
# Order lifecycle endpoints (open)
# -----------------------

# Create Order endpoint (called from payment page)
@app.route('/create_order', methods=['POST'])
def create_order():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid JSON"}), 400

    cart = data.get('cart', [])
    subtotal = float(data.get('subtotal', 0) or 0)
    discount_amount = float(data.get('discount_amount', 0) or 0)
    discount_percent = float(data.get('discount_percent', 0) or 0)
    final_total = float(data.get('final_total', subtotal) or subtotal)
    customer_id = data.get('customer_id') or session.get('user_id')
    customer_name = data.get('customer_name') or session.get('username')
    customer_email = data.get('customer_email') or session.get('email')
    currency = data.get('currency', 'INR')
    payment_provider = data.get('payment_provider')
    provider_payment_id = data.get('provider_payment_id')
    payment_status = data.get('payment_status', 'pending')
    table_no = data.get('table_no')
    meta = data.get('meta') or {}

    if not cart or len(cart) == 0:
        return jsonify({"success": False, "message": "Cart is empty"}), 400

    # Optional: server-side verify totals (recommended)
    try:
        computed_subtotal = 0.0
        for it in cart:
            qty = int(it.get('qty', 1))
            unit_price = float(it.get('price', 0))
            computed_subtotal += round(unit_price * qty, 2)
        computed_subtotal = round(computed_subtotal, 2)
        # we accept client's subtotal if matches computed (allow small floating diff)
        if abs(computed_subtotal - subtotal) > 0.01:
            # keep server computed value to avoid tampering
            subtotal = computed_subtotal
            # recompute final_total from discount (server authoritative)
            final_total = round(subtotal - discount_amount, 2)
    except Exception:
        return jsonify({"success": False, "message": "Invalid cart format"}), 400

    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            """INSERT INTO orders
               (customer_id, customer_name, customer_email, subtotal, discount_amount, discount_percent,
                final_total, currency, payment_provider, provider_payment_id, payment_status,
                current_status, table_no, meta)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (customer_id, customer_name, customer_email, subtotal, discount_amount, discount_percent,
             final_total, currency, payment_provider, provider_payment_id, payment_status,
             'placed', table_no, json.dumps(meta))
        )
        order_id = cursor.lastrowid

        # Insert order_items (matching your schema: qty, unit_price, total_price)
        for item in cart:
            name = item.get('name')[:255] if item.get('name') else ''
            qty = int(item.get('qty', 1))
            unit_price = float(item.get('price', 0))
            total_price = round(unit_price * qty, 2)

            cursor.execute(
                "INSERT INTO order_items (order_id, item_name, qty, unit_price, total_price) VALUES (%s,%s,%s,%s,%s)",
                (order_id, name, qty, unit_price, total_price)
            )

        mysql.connection.commit()

    except Exception as e:
        mysql.connection.rollback()
        cursor.close()
        app.logger.exception("create_order DB error")
        return jsonify({"success": False, "message": "DB error: " + str(e)}), 500
    finally:
        cursor.close()

    return jsonify({"success": True, "order_id": order_id}), 201

# Chef: list orders by status (uses current_status). Accepts status=all to return all orders.
@app.route('/chef/orders', methods=['GET'])
def chef_list_orders():
    status = request.args.get('status', 'placed')
    cursor = mysql.connection.cursor()
    try:
        if status == 'all':
            cursor.execute(
                "SELECT id, customer_name, subtotal, final_total, payment_status, current_status, created_at FROM orders ORDER BY created_at ASC"
            )
        else:
            cursor.execute(
                "SELECT id, customer_name, subtotal, final_total, payment_status, current_status, created_at FROM orders WHERE current_status = %s ORDER BY created_at ASC",
                (status,)
            )
        rows = cursor.fetchall()
        orders = [dict_from_row(cursor, r) for r in rows]

        # Attach items for each order (safe: if there are none, set empty list)
        for o in orders:
            cursor.execute("SELECT id, item_name, qty, unit_price, total_price FROM order_items WHERE order_id = %s", (o['id'],))
            item_rows = cursor.fetchall()
            items = [dict_from_row(cursor, row) for row in item_rows]
            o['items'] = items

        return jsonify({"success": True, "orders": orders})
    except Exception as e:
        app.logger.exception("chef_list_orders error")
        return jsonify({"success": False, "message": "Server error fetching orders: " + str(e)}), 500
    finally:
        cursor.close()

# Chef: update order status (uses current_status) — improved error handling
@app.route('/chef/update_order_status', methods=['POST'])
def chef_update_order_status():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid JSON"}), 400

    order_id = data.get('order_id')
    new_status = data.get('new_status')

    allowed = {'placed','preparing','ready','served','delivered','cancelled'}
    if not order_id or not new_status or new_status not in allowed:
        return jsonify({"success": False, "message": "Invalid parameters"}), 400

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("UPDATE orders SET current_status = %s, updated_at = NOW() WHERE id = %s", (new_status, order_id))
        if cursor.rowcount == 0:
            mysql.connection.rollback()
            return jsonify({"success": False, "message": "Order not found"}), 404
        mysql.connection.commit()
        return jsonify({"success": True, "order_id": order_id, "new_status": new_status})
    except Exception as e:
        mysql.connection.rollback()
        app.logger.exception("chef_update_order_status error")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

# Clerk / Waiter: mark delivered and collect payment (uses current_status)
@app.route('/clerk/complete_order', methods=['POST'])
def clerk_complete_order():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid JSON"}), 400

    order_id = data.get('order_id')
    payment_status = data.get('payment_status', 'paid')
    if not order_id:
        return jsonify({"success": False, "message": "order_id required"}), 400

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("UPDATE orders SET current_status = %s, payment_status = %s, updated_at = NOW() WHERE id = %s",
                       ('delivered', payment_status, order_id))
        mysql.connection.commit()
    except Exception as e:
        mysql.connection.rollback()
        cursor.close()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

    return jsonify({"success": True, "order_id": order_id})

# Owner: orders report (uses current_status)
@app.route('/owner/orders_report', methods=['GET'])
def owner_orders_report():
    start = request.args.get('start')  # e.g. 2025-11-01
    end = request.args.get('end')      # e.g. 2025-11-08

    if not start or not end:
        end_dt = datetime.utcnow().date()
        start_dt = end_dt - timedelta(days=7)
        start = start_dt.isoformat()
        end = end_dt.isoformat()

    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            "SELECT id, customer_name, current_status, payment_status, subtotal, discount_amount, final_total, created_at "
            "FROM orders WHERE DATE(created_at) BETWEEN %s AND %s ORDER BY created_at DESC",
            (start, end)
        )
        rows = cursor.fetchall()
        orders = [dict_from_row(cursor, r) for r in rows]
    finally:
        cursor.close()

    return jsonify({"success": True, "start": start, "end": end, "orders": orders})

# Owner: sales summary
@app.route('/owner/sales_summary', methods=['GET'])
def owner_sales_summary():
    days = int(request.args.get('days', 30))
    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            "SELECT DATE(created_at) as day, COUNT(*) as orders_count, SUM(final_total) as total_sales "
            "FROM orders WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY) GROUP BY DATE(created_at) ORDER BY DATE(created_at) ASC",
            (days,)
        )
        rows = cursor.fetchall()
        summary = [dict_from_row(cursor, r) for r in rows]
    finally:
        cursor.close()

    return jsonify({"success": True, "days": days, "summary": summary})

# Generic 500 handler to avoid raw tracebacks in browser (useful while testing)
@app.errorhandler(500)
def internal_error(e):
    # log traceback for debugging
    app.logger.error("Server Error: %s", traceback.format_exc())
    return "Internal server error (see console).", 500

# ---------------------------------
# Manager: metrics endpoint (for manager_dash.html)
# ---------------------------------
@app.route('/owner/manager_metrics', methods=['GET'])
def owner_manager_metrics():
    cursor = mysql.connection.cursor()
    try:
        # Total sales & orders for today
        cursor.execute(
            "SELECT COALESCE(SUM(final_total),0) AS total_sales, COUNT(*) AS total_orders "
            "FROM orders WHERE DATE(created_at) = CURDATE()"
        )
        row = cursor.fetchone() or (0, 0)
        if cursor.description:
            cols = [c[0] for c in cursor.description]
            mapped = dict(zip(cols, row))
            total_sales_today = float(mapped.get('total_sales') or 0)
            total_orders_today = int(mapped.get('total_orders') or 0)
        else:
            total_sales_today = float(row[0] or 0)
            total_orders_today = int(row[1] or 0)

        # Get low stock count from ingredients
        cursor.execute("SELECT COUNT(*) FROM ingredients WHERE current_stock <= reorder_level")
        low_stock_count = int(cursor.fetchone()[0] or 0)

        # Get pending purchase orders count
        cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE status = 'pending'")
        pending_pos = int(cursor.fetchone()[0] or 0)

        return jsonify({
            "success": True,
            "total_sales_today": total_sales_today,
            "total_orders_today": total_orders_today,
            "low_stock_count": low_stock_count,
            "pending_pos": pending_pos
        })
    except Exception as e:
        app.logger.exception("owner_manager_metrics error")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

# ---------------------------------
# Manager: ingredient / item usage (top sold items)
# ---------------------------------
@app.route('/owner/ingredient_usage', methods=['GET'])
def owner_ingredient_usage():
    days = int(request.args.get('days', 30))
    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            """
            SELECT oi.item_name AS item, SUM(oi.qty) AS qty
              FROM order_items oi
              JOIN orders o ON o.id = oi.order_id
             WHERE o.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
             GROUP BY oi.item_name
             ORDER BY qty DESC
             LIMIT 25
            """,
            (days,)
        )
        rows = cursor.fetchall()
        usage = [dict_from_row(cursor, r) for r in rows]
        # Normalize qty to int
        for u in usage:
            if 'qty' in u:
                try:
                    u['qty'] = int(u['qty'])
                except Exception:
                    u['qty'] = float(u['qty'] or 0)
        return jsonify({"success": True, "days": days, "usage": usage})
    except Exception as e:
        app.logger.exception("owner_ingredient_usage error")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

# ---------------------------------
# EMPLOYEE MANAGEMENT API ROUTES
# ---------------------------------

@app.route('/api/employees')
def get_employees():
    """Get all employees with details from both users and employees tables"""
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            SELECT 
                e.id as employee_id,
                e.user_id,
                e.name,
                e.email,
                e.role,
                e.status,
                e.hire_date,
                u.username,
                u.role as user_role
            FROM employees e
            LEFT JOIN users u ON e.user_id = u.id
            ORDER BY e.role, e.name
        """)
        employees = cursor.fetchall()
        
        employee_list = []
        for emp in employees:
            employee_list.append({
                'id': emp[0],  # employee_id
                'user_id': emp[1],
                'name': emp[2],
                'email': emp[3],
                'role': emp[4].capitalize() if emp[4] else '',
                'status': emp[5],
                'hire_date': emp[6].strftime('%Y-%m-%d') if emp[6] else '',
                'username': emp[7],
                'user_role': emp[8]
            })
        
        return jsonify({'success': True, 'employees': employee_list})
        
    except Exception as e:
        app.logger.exception("Error fetching employees")
        return jsonify({'success': False, 'message': 'Error fetching employees'})
    finally:
        cursor.close()

@app.route('/api/employees', methods=['POST'])
def add_employee():
    """Add new employee - creates entry in both users and employees tables"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'message': 'Invalid JSON'}), 400
    
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    role = data.get('role', '').strip().lower()
    
    if not name or not email or not role:
        return jsonify({'success': False, 'message': 'All fields are required'}), 400
    
    # Validate role
    allowed_roles = ['chef', 'waiter', 'clerk']
    if role.lower() not in allowed_roles:
        return jsonify({'success': False, 'message': 'Invalid role'}), 400
    
    cursor = mysql.connection.cursor()
    try:
        # Check if email already exists in users table
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            return jsonify({'success': False, 'message': 'Email already registered'}), 400
        
        # Generate a temporary password (employees can reset later)
        temp_password = "temp123"  # In production, generate a random password
        
        # Create user account first
        cursor.execute(
            "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
            (name, email, temp_password, role)
        )
        user_id = cursor.lastrowid
        
        # Create employee record
        cursor.execute(
            "INSERT INTO employees (user_id, name, email, role, status) VALUES (%s, %s, %s, %s, %s)",
            (user_id, name, email, role, 'active')
        )
        
        mysql.connection.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Employee added successfully. Temporary password: {temp_password}',
            'employee_id': cursor.lastrowid
        })
        
    except Exception as e:
        mysql.connection.rollback()
        app.logger.exception("Error adding employee")
        return jsonify({'success': False, 'message': 'Error adding employee: ' + str(e)}), 500
    finally:
        cursor.close()

@app.route('/api/employees/<int:employee_id>', methods=['DELETE'])
def delete_employee(employee_id):
    """Delete employee - removes from both tables"""
    cursor = mysql.connection.cursor()
    try:
        # Get user_id before deletion
        cursor.execute("SELECT user_id FROM employees WHERE id = %s", (employee_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'success': False, 'message': 'Employee not found'}), 404
        
        user_id = result[0]
        
        # Delete from employees table
        cursor.execute("DELETE FROM employees WHERE id = %s", (employee_id,))
        
        # Delete from users table
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        
        mysql.connection.commit()
        
        return jsonify({'success': True, 'message': 'Employee deleted successfully'})
        
    except Exception as e:
        mysql.connection.rollback()
        app.logger.exception("Error deleting employee")
        return jsonify({'success': False, 'message': 'Error deleting employee'})
    finally:
        cursor.close()

@app.route('/api/employees/<int:employee_id>/status', methods=['PUT'])
def update_employee_status(employee_id):
    """Update employee status (active/inactive)"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'message': 'Invalid JSON'}), 400
    
    new_status = data.get('status')
    if new_status not in ['active', 'inactive']:
        return jsonify({'success': False, 'message': 'Invalid status'}), 400
    
    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            "UPDATE employees SET status = %s WHERE id = %s",
            (new_status, employee_id)
        )
        mysql.connection.commit()
        
        return jsonify({'success': True, 'message': f'Employee status updated to {new_status}'})
        
    except Exception as e:
        mysql.connection.rollback()
        app.logger.exception("Error updating employee status")
        return jsonify({'success': False, 'message': 'Error updating status'})
    finally:
        cursor.close()

@app.route('/api/employees/<int:employee_id>/reset-password', methods=['POST'])
def reset_employee_password(employee_id):
    """Reset employee password to temporary value"""
    cursor = mysql.connection.cursor()
    try:
        # Get user_id from employee
        cursor.execute("SELECT user_id FROM employees WHERE id = %s", (employee_id,))
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'success': False, 'message': 'Employee not found'}), 404
        
        user_id = result[0]
        temp_password = "temp123"  # Generate a new temporary password
        
        # Update password in users table
        cursor.execute(
            "UPDATE users SET password = %s WHERE id = %s",
            (temp_password, user_id)
        )
        mysql.connection.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Password reset successfully. New temporary password: {temp_password}'
        })
        
    except Exception as e:
        mysql.connection.rollback()
        app.logger.exception("Error resetting password")
        return jsonify({'success': False, 'message': 'Error resetting password'})
    finally:
        cursor.close()

# -----------------------
# Ingredient Stock Routes
# -----------------------

# Get all ingredients with stock status
@app.route('/api/ingredients', methods=['GET'])
def get_ingredients():
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            SELECT id, name, current_stock, unit, reorder_level, initial_stock,
                   CASE 
                       WHEN current_stock <= reorder_level THEN 'low'
                       WHEN current_stock <= reorder_level * 1.5 THEN 'warning'
                       ELSE 'sufficient'
                   END as status
            FROM ingredients 
            ORDER BY name
        """)
        ingredients = [dict_from_row(cursor, row) for row in cursor.fetchall()]
        return jsonify({"success": True, "ingredients": ingredients})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

# Update ingredient stock (used by chef)
@app.route('/api/ingredients/<int:ingredient_id>/use', methods=['POST'])
def use_ingredient(ingredient_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid JSON"}), 400
    
    quantity = float(data.get('quantity', 0))
    note = data.get('note', '')
    
    if quantity <= 0:
        return jsonify({"success": False, "message": "Quantity must be positive"}), 400
    
    cursor = mysql.connection.cursor()
    try:
        # Check current stock
        cursor.execute("SELECT current_stock FROM ingredients WHERE id = %s", (ingredient_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({"success": False, "message": "Ingredient not found"}), 404
        
        current_stock = float(result[0])
        if current_stock < quantity:
            return jsonify({"success": False, "message": "Insufficient stock"}), 400
        
        # Update stock
        new_stock = current_stock - quantity
        cursor.execute(
            "UPDATE ingredients SET current_stock = %s WHERE id = %s",
            (new_stock, ingredient_id)
        )
        
        # Record transaction - FIXED: Use shorter transaction types
        cursor.execute(
            "INSERT INTO inventory_transactions (ingredient_id, transaction_type, quantity, note, created_by) VALUES (%s, %s, %s, %s, %s)",
            (ingredient_id, 'usage', quantity, note, session.get('user_id', 1))
        )
        
        mysql.connection.commit()
        return jsonify({"success": True, "new_stock": new_stock})
        
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

# Get low stock ingredients
@app.route('/api/ingredients/low-stock', methods=['GET'])
def get_low_stock():
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            SELECT id, name, current_stock, unit, reorder_level,
                   (reorder_level - current_stock) as needed_quantity
            FROM ingredients 
            WHERE current_stock <= reorder_level
            ORDER BY (reorder_level - current_stock) DESC
        """)
        low_stock = [dict_from_row(cursor, row) for row in cursor.fetchall()]
        return jsonify({"success": True, "low_stock": low_stock})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

# Generate Purchase Order
@app.route('/api/generate-po', methods=['POST'])
def generate_purchase_order():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid JSON"}), 400
    
    items = data.get('items', [])
    supplier_info = data.get('supplier_info', {})
    
    if not items:
        return jsonify({"success": False, "message": "No items selected"}), 400
    
    cursor = mysql.connection.cursor()
    try:
        # Generate PO number
        from datetime import datetime
        po_number = f"PO-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Create purchase order
        cursor.execute(
            "INSERT INTO purchase_orders (po_number, supplier_info, created_by) VALUES (%s, %s, %s)",
            (po_number, json.dumps(supplier_info), session.get('user_id', 1))
        )
        po_id = cursor.lastrowid
        
        total_amount = 0
        # Add PO items
        for item in items:
            ingredient_id = item['ingredient_id']
            quantity = float(item['quantity'])
            unit_price = float(item.get('unit_price', 0))
            total_price = quantity * unit_price
            total_amount += total_price
            
            cursor.execute(
                "INSERT INTO purchase_order_items (po_id, ingredient_id, quantity, unit_price, total_price) VALUES (%s, %s, %s, %s, %s)",
                (po_id, ingredient_id, quantity, unit_price, total_price)
            )
        
        # Update PO total
        cursor.execute(
            "UPDATE purchase_orders SET total_amount = %s WHERE id = %s",
            (total_amount, po_id)
        )
        
        mysql.connection.commit()
        return jsonify({"success": True, "po_id": po_id, "po_number": po_number})
        
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

# -----------------------
# Purchase Order Routes
# -----------------------

# Get all purchase orders
@app.route('/api/purchase-orders', methods=['GET'])
def get_purchase_orders():
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            SELECT id, po_number, status, total_amount, supplier_info, created_at, updated_at
            FROM purchase_orders 
            ORDER BY created_at DESC
        """)
        purchase_orders = []
        for row in cursor.fetchall():
            po = dict_from_row(cursor, row)
            if po.get('supplier_info'):
                try:
                    po['supplier_info'] = json.loads(po['supplier_info'])
                except:
                    po['supplier_info'] = {}
            purchase_orders.append(po)
        
        return jsonify({"success": True, "purchase_orders": purchase_orders})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

# Get specific purchase order with items
@app.route('/api/purchase-orders/<int:po_id>', methods=['GET'])
def get_purchase_order(po_id):
    cursor = mysql.connection.cursor()
    try:
        # Get PO details
        cursor.execute("""
            SELECT id, po_number, status, total_amount, supplier_info, created_at, updated_at
            FROM purchase_orders WHERE id = %s
        """, (po_id,))
        po = cursor.fetchone()
        
        if not po:
            return jsonify({"success": False, "message": "Purchase order not found"}), 404
        
        po_dict = dict_from_row(cursor, po)
        if po_dict.get('supplier_info'):
            try:
                po_dict['supplier_info'] = json.loads(po_dict['supplier_info'])
            except:
                po_dict['supplier_info'] = {}
        
        # Get PO items
        cursor.execute("""
            SELECT poi.id, poi.ingredient_id, poi.quantity, poi.unit_price, poi.total_price,
                   i.name as ingredient_name, i.unit
            FROM purchase_order_items poi
            LEFT JOIN ingredients i ON poi.ingredient_id = i.id
            WHERE poi.po_id = %s
        """, (po_id,))
        items = [dict_from_row(cursor, row) for row in cursor.fetchall()]
        po_dict['items'] = items
        
        return jsonify({"success": True, "purchase_order": po_dict})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

# Update PO status
@app.route('/api/purchase-orders/<int:po_id>/status', methods=['PUT'])
def update_po_status(po_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid JSON"}), 400
    
    new_status = data.get('status')
    allowed_statuses = ['pending', 'ordered', 'received', 'cancelled']
    
    if new_status not in allowed_statuses:
        return jsonify({"success": False, "message": "Invalid status"}), 400
    
    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            "UPDATE purchase_orders SET status = %s, updated_at = NOW() WHERE id = %s",
            (new_status, po_id)
        )
        
        # If status is 'received', update ingredient stock
        if new_status == 'received':
            cursor.execute("""
                SELECT poi.ingredient_id, poi.quantity 
                FROM purchase_order_items poi 
                WHERE poi.po_id = %s
            """, (po_id,))
            items = cursor.fetchall()
            
            for ingredient_id, quantity in items:
                cursor.execute("""
                    UPDATE ingredients 
                    SET current_stock = current_stock + %s 
                    WHERE id = %s
                """, (quantity, ingredient_id))
                
                # Record inventory transaction - FIXED: Use shorter transaction type
                cursor.execute("""
                    INSERT INTO inventory_transactions 
                    (ingredient_id, transaction_type, quantity, note, created_by)
                    VALUES (%s, %s, %s, %s, %s)
                """, (ingredient_id, 'purchase', quantity, f'PO #{po_id} received', session.get('user_id', 1)))
        
        mysql.connection.commit()
        return jsonify({"success": True, "message": f"PO status updated to {new_status}"})
        
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

# -----------------------
# Expenses Report Routes
# -----------------------

# Get expenses with date range filtering
@app.route('/api/expenses', methods=['GET'])
def get_expenses():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({"success": False, "message": "Start date and end date are required"}), 400
    
    cursor = mysql.connection.cursor()
    try:
        # Get expenses within date range
        cursor.execute("""
            SELECT id, expense_number, expense_date, expense_type, supplier_name, 
                   payee, description, amount, payment_mode, created_at
            FROM expenses 
            WHERE expense_date BETWEEN %s AND %s
            ORDER BY expense_date DESC, created_at DESC
        """, (start_date, end_date))
        
        expenses = [dict_from_row(cursor, row) for row in cursor.fetchall()]
        
        # Get summary statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as expense_count,
                COALESCE(SUM(amount), 0) as total_amount,
                COALESCE(AVG(amount), 0) as average_amount
            FROM expenses 
            WHERE expense_date BETWEEN %s AND %s
        """, (start_date, end_date))
        
        summary_row = cursor.fetchone()
        summary = dict_from_row(cursor, summary_row) if summary_row else {
            "expense_count": 0,
            "total_amount": 0,
            "average_amount": 0
        }
        
        return jsonify({
            "success": True, 
            "expenses": expenses, 
            "summary": summary
        })
        
    except Exception as e:
        app.logger.exception("get_expenses error")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

# ---------------------------------
# Analytics Data Endpoints
# ---------------------------------

@app.route('/api/analytics/monthly-sales')
def analytics_monthly_sales():
    """Get monthly sales data for the current year"""
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            SELECT 
                DATE_FORMAT(created_at, '%Y-%m') as month,
                SUM(final_total) as total_sales,
                COUNT(*) as order_count
            FROM orders 
            WHERE YEAR(created_at) = YEAR(CURDATE())
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
            ORDER BY month
        """)
        rows = cursor.fetchall()
        monthly_data = [dict_from_row(cursor, row) for row in rows]
        
        # Format for chart (all months, even if no data)
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        sales_data = [0] * 12
        order_counts = [0] * 12
        
        for data in monthly_data:
            month_num = int(data['month'].split('-')[1]) - 1
            sales_data[month_num] = float(data['total_sales'] or 0)
            order_counts[month_num] = int(data['order_count'] or 0)
        
        return jsonify({
            "success": True,
            "labels": months,
            "sales_data": sales_data,
            "order_counts": order_counts
        })
    except Exception as e:
        app.logger.exception("analytics_monthly_sales error")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

@app.route('/api/analytics/ingredient-stock')
def analytics_ingredient_stock():
    """Get current ingredient stock levels"""
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            SELECT name, current_stock, unit, reorder_level
            FROM ingredients 
            ORDER BY current_stock ASC
            LIMIT 10
        """)
        rows = cursor.fetchall()
        ingredients = [dict_from_row(cursor, row) for row in rows]
        
        labels = [ing['name'] for ing in ingredients]
        stock_data = [float(ing['current_stock']) for ing in ingredients]
        reorder_levels = [float(ing['reorder_level']) for ing in ingredients]
        
        return jsonify({
            "success": True,
            "labels": labels,
            "stock_data": stock_data,
            "reorder_levels": reorder_levels,
            "unit": ingredients[0]['unit'] if ingredients else 'units'
        })
    except Exception as e:
        app.logger.exception("analytics_ingredient_stock error")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

@app.route('/api/analytics/expense-distribution')
def analytics_expense_distribution():
    """Get expense distribution by category"""
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            SELECT 
                expense_type,
                SUM(amount) as total_amount,
                COUNT(*) as count
            FROM expenses 
            WHERE expense_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY expense_type
            ORDER BY total_amount DESC
        """)
        
        rows = cursor.fetchall()
        expenses = [dict_from_row(cursor, row) for row in rows]
        
        labels = [exp['expense_type'] for exp in expenses]
        amounts = [float(exp['total_amount']) for exp in expenses]
        
        return jsonify({
            "success": True,
            "labels": labels,
            "amounts": amounts
        })
    except Exception as e:
        app.logger.exception("analytics_expense_distribution error")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

@app.route('/api/analytics/sales-vs-expenses')
def analytics_sales_vs_expenses():
    """Compare sales vs expenses for the last 6 months"""
    cursor = mysql.connection.cursor()
    try:
        # Get sales data
        cursor.execute("""
            SELECT 
                DATE_FORMAT(created_at, '%Y-%m') as month,
                SUM(final_total) as sales
            FROM orders 
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
            ORDER BY month
        """)
        sales_rows = cursor.fetchall()
        sales_data = {row[0]: float(row[1] or 0) for row in sales_rows}
        
        # Get expense data
        cursor.execute("""
            SELECT 
                DATE_FORMAT(expense_date, '%Y-%m') as month,
                SUM(amount) as expenses
            FROM expenses 
            WHERE expense_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
            GROUP BY DATE_FORMAT(expense_date, '%Y-%m')
            ORDER BY month
        """)
        expense_rows = cursor.fetchall()
        expense_data = {row[0]: float(row[1] or 0) for row in expense_rows}
        
        # Generate last 6 months labels
        from datetime import datetime, timedelta
        months = []
        sales = []
        expenses = []
        
        for i in range(6):
            date = datetime.now() - timedelta(days=30*i)
            month_key = date.strftime('%Y-%m')
            month_label = date.strftime('%b')
            months.insert(0, month_label)
            sales.insert(0, sales_data.get(month_key, 0))
            expenses.insert(0, expense_data.get(month_key, 0))
        
        return jsonify({
            "success": True,
            "labels": months,
            "sales": sales,
            "expenses": expenses
        })
    except Exception as e:
        app.logger.exception("analytics_sales_vs_expenses error")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

@app.route('/api/analytics/top-selling-items')
def analytics_top_selling_items():
    """Get top selling menu items"""
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            SELECT 
                oi.item_name,
                SUM(oi.qty) as total_quantity,
                SUM(oi.total_price) as total_revenue,
                COUNT(DISTINCT oi.order_id) as order_count
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE o.created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY oi.item_name
            ORDER BY total_quantity DESC
            LIMIT 10
        """)
        rows = cursor.fetchall()
        top_items = [dict_from_row(cursor, row) for row in rows]
        
        return jsonify({
            "success": True,
            "top_items": top_items
        })
    except Exception as e:
        app.logger.exception("analytics_top_selling_items error")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

@app.route('/api/analytics/order-metrics')
def analytics_order_metrics():
    """Get key order metrics"""
    cursor = mysql.connection.cursor()
    try:
        # Today's metrics
        cursor.execute("""
            SELECT 
                COUNT(*) as today_orders,
                COALESCE(SUM(final_total), 0) as today_sales,
                AVG(final_total) as today_avg_order_value
            FROM orders 
            WHERE DATE(created_at) = CURDATE()
        """)
        today = cursor.fetchone()
        
        # Weekly metrics
        cursor.execute("""
            SELECT 
                COUNT(*) as weekly_orders,
                COALESCE(SUM(final_total), 0) as weekly_sales
            FROM orders 
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
        """)
        weekly = cursor.fetchone()
        
        # Monthly metrics
        cursor.execute("""
            SELECT 
                COUNT(*) as monthly_orders,
                COALESCE(SUM(final_total), 0) as monthly_sales
            FROM orders 
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        """)
        monthly = cursor.fetchone()
        
        # Popular hours
        cursor.execute("""
            SELECT 
                HOUR(created_at) as hour,
                COUNT(*) as order_count
            FROM orders 
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY HOUR(created_at)
            ORDER BY order_count DESC
            LIMIT 5
        """)
        popular_hours = cursor.fetchall()
        
        return jsonify({
            "success": True,
            "today": {
                "orders": today[0] or 0,
                "sales": float(today[1] or 0),
                "avg_order_value": float(today[2] or 0)
            },
            "weekly": {
                "orders": weekly[0] or 0,
                "sales": float(weekly[1] or 0)
            },
            "monthly": {
                "orders": monthly[0] or 0,
                "sales": float(monthly[1] or 0)
            },
            "popular_hours": [f"{row[0]}:00" for row in popular_hours]
        })
    except Exception as e:
        app.logger.exception("analytics_order_metrics error")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

# -----------------------
# Enhanced Ingredient Management Routes
# -----------------------

@app.route('/api/ingredients/add', methods=['POST'])
def add_ingredient():
    """Add new ingredient to inventory"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid JSON"}), 400
    
    name = data.get('name')
    current_stock = float(data.get('current_stock', 0))
    unit = data.get('unit')
    reorder_level = float(data.get('reorder_level', 0))
    
    if not name or not unit:
        return jsonify({"success": False, "message": "Name and unit are required"}), 400
    
    cursor = mysql.connection.cursor()
    try:
        # Check if ingredient already exists
        cursor.execute("SELECT id FROM ingredients WHERE name = %s", (name,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Ingredient with this name already exists"}), 400
        
        cursor.execute(
            "INSERT INTO ingredients (name, current_stock, unit, reorder_level, initial_stock) VALUES (%s, %s, %s, %s, %s)",
            (name, current_stock, unit, reorder_level, current_stock)
        )
        
        ingredient_id = cursor.lastrowid
        
        # Record initial stock transaction - FIXED: Use shorter transaction type
        if current_stock > 0:
            cursor.execute(
                "INSERT INTO inventory_transactions (ingredient_id, transaction_type, quantity, note, created_by) VALUES (%s, %s, %s, %s, %s)",
                (ingredient_id, 'initial', current_stock, 'Initial stock', session.get('user_id', 1))
            )
        
        mysql.connection.commit()
        return jsonify({"success": True, "message": "Ingredient added successfully", "ingredient_id": ingredient_id})
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

@app.route('/api/ingredients/<int:ingredient_id>/restock', methods=['POST'])
def restock_ingredient(ingredient_id):
    """Restock ingredient (add to current stock)"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid JSON"}), 400
    
    quantity = float(data.get('quantity', 0))
    note = data.get('note', 'Manual restock')
    
    if quantity <= 0:
        return jsonify({"success": False, "message": "Quantity must be positive"}), 400
    
    cursor = mysql.connection.cursor()
    try:
        # Check if ingredient exists
        cursor.execute("SELECT current_stock, name FROM ingredients WHERE id = %s", (ingredient_id,))
        result = cursor.fetchone()
        if not result:
            return jsonify({"success": False, "message": "Ingredient not found"}), 404
        
        current_stock = float(result[0])
        ingredient_name = result[1]
        new_stock = current_stock + quantity
        
        # Update stock
        cursor.execute(
            "UPDATE ingredients SET current_stock = %s WHERE id = %s",
            (new_stock, ingredient_id)
        )
        
        # Record transaction - FIXED: Use shorter transaction type
        cursor.execute(
            "INSERT INTO inventory_transactions (ingredient_id, transaction_type, quantity, note, created_by) VALUES (%s, %s, %s, %s, %s)",
            (ingredient_id, 'restock', quantity, note, session.get('user_id', 1))
        )
        
        mysql.connection.commit()
        return jsonify({
            "success": True, 
            "new_stock": new_stock,
            "message": f"Successfully restocked {ingredient_name} by {quantity} {data.get('unit', 'units')}"
        })
        
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

@app.route('/api/ingredients/<int:ingredient_id>/update', methods=['PUT'])
def update_ingredient(ingredient_id):
    """Update ingredient details"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid JSON"}), 400
    
    cursor = mysql.connection.cursor()
    try:
        # Check if ingredient exists
        cursor.execute("SELECT id, name FROM ingredients WHERE id = %s", (ingredient_id,))
        ingredient = cursor.fetchone()
        if not ingredient:
            return jsonify({"success": False, "message": "Ingredient not found"}), 404
        
        # Build update query dynamically based on provided fields
        update_fields = []
        update_values = []
        
        if 'name' in data and data['name']:
            update_fields.append("name = %s")
            update_values.append(data['name'])
        
        if 'unit' in data and data['unit']:
            update_fields.append("unit = %s")
            update_values.append(data['unit'])
        
        if 'reorder_level' in data:
            update_fields.append("reorder_level = %s")
            update_values.append(float(data['reorder_level']))
        
        if not update_fields:
            return jsonify({"success": False, "message": "No fields to update"}), 400
        
        update_values.append(ingredient_id)
        query = f"UPDATE ingredients SET {', '.join(update_fields)} WHERE id = %s"
        
        cursor.execute(query, update_values)
        mysql.connection.commit()
        
        return jsonify({"success": True, "message": "Ingredient updated successfully"})
        
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

@app.route('/api/ingredients/units', methods=['GET'])
def get_common_units():
    """Get common measurement units for suggestions"""
    common_units = [
        'kg', 'g', 'lb', 'oz', 'l', 'ml', 
        'pieces', 'packets', 'bottles', 'cans',
        'boxes', 'bags', 'dozen'
    ]
    return jsonify({"success": True, "units": common_units})

@app.route('/api/user/session')
def get_user_session():
    """Get current user session data"""
    if 'user_id' in session:
        cursor = mysql.connection.cursor()
        try:
            cursor.execute(
                "SELECT id, username, email, role FROM users WHERE id = %s", 
                (session['user_id'],)
            )
            user = cursor.fetchone()
            if user:
                user_data = {
                    'id': user[0],
                    'username': user[1],
                    'email': user[2],
                    'role': user[3]
                }
                return jsonify({'success': True, 'user': user_data})
        except Exception as e:
            app.logger.exception("Error fetching user session")
            return jsonify({'success': False, 'message': 'Error fetching session'})
        finally:
            cursor.close()
    
    return jsonify({'success': False, 'message': 'Not logged in'})

@app.route('/api/ingredients/<int:ingredient_id>', methods=['DELETE'])
def delete_ingredient(ingredient_id):
    """Delete ingredient and all related data"""
    cursor = mysql.connection.cursor()
    try:
        # Check if ingredient exists
        cursor.execute("SELECT name FROM ingredients WHERE id = %s", (ingredient_id,))
        ingredient = cursor.fetchone()
        
        if not ingredient:
            return jsonify({'success': False, 'message': 'Ingredient not found'}), 404
        
        ingredient_name = ingredient[0]
        
        # Delete related records first (to maintain referential integrity)
        
        # 1. Delete from purchase_order_items
        cursor.execute("DELETE FROM purchase_order_items WHERE ingredient_id = %s", (ingredient_id,))
        
        # 2. Delete from inventory_transactions
        cursor.execute("DELETE FROM inventory_transactions WHERE ingredient_id = %s", (ingredient_id,))
        
        # 3. Finally delete the ingredient itself
        cursor.execute("DELETE FROM ingredients WHERE id = %s", (ingredient_id,))
        
        mysql.connection.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Ingredient "{ingredient_name}" deleted successfully from all records'
        })
        
    except Exception as e:
        mysql.connection.rollback()
        app.logger.exception("Error deleting ingredient")
        return jsonify({'success': False, 'message': 'Error deleting ingredient: ' + str(e)}), 500
    finally:
        cursor.close()

# Initialize database tables
@app.route('/init-db')
def init_db():
    """Initialize database tables (run this once)"""
    try:
        init_database()
        create_default_owner()
        return "Database initialized successfully"
    except Exception as e:
        return f"Error initializing database: {str(e)}"

# ---------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False, port=int(os.getenv('PORT', 5050)))