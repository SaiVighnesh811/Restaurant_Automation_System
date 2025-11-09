from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
from werkzeug.security import generate_password_hash

app = Flask(__name__)
app.secret_key = 'supersecret'

# ---------------------------------
# MySQL Configuration
# ---------------------------------

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'example_user'
app.config['MYSQL_PASSWORD'] = 'password'
app.config['MYSQL_DB'] = 'restaurent_db'
app.config['MYSQL_PORT'] = 3306

mysql = MySQL(app)

# ---------------------------------
# HOME PAGE
# ---------------------------------
@app.route('/')
def home():
    return render_template('landing.html')


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

        # Validate password match
        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('signup'))

        # Hash the password for security
        #hashed_password = generate_password_hash(password)

        # Insert into MySQL
        cursor = mysql.connection.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
            (username, email,password, role)
        )
        mysql.connection.commit()
        cursor.close()

        flash("Account created successfully! Please login.", "success")
        return redirect(url_for('login'))  # redirect to login page

    return render_template('signup.html')
# ---------------------------------
# LOGIN PAGE
# ---------------------------------
# LOGIN (compare submitted password to DB's password directly)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')  # user-entered password

        # Validate inputs
        if not email or not password:
            flash("Provide email and password", "danger")
            return redirect(url_for('login'))

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, username, email, password, role FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
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

                # redirect by role (example)
                if role.lower() == 'customer':
                    return redirect(url_for('show_menu'))
                elif role.lower() == 'owner':
                    return redirect(url_for('owner_dashboard'))
                elif role.lower() == 'chef':
                    return redirect(url_for('chef_dashboard'))
                elif role.lower() == 'clerk':
                    return redirect(url_for('clerk_dashboard'))
                else:
                    return redirect(url_for('home'))
            else:
                flash("Incorrect password", "danger")
                return redirect(url_for('login'))
        else:
            flash("Email not registered", "danger")
            return redirect(url_for('login'))

    return render_template('login.html')


# ---------------------------------
# MENU PAGE
# ---------------------------------
@app.route('/menupage')
def show_menu():
    
    return render_template('menu1.html')


# ---------------------------------
# FORGOT PASSWORD PAGE
# ---------------------------------
@app.route('/loginpage/forgot')
def forgot_password():
    return render_template('forgot-password.html')

# ---------------------------------
# OWNER DASHBOARD PAGE
# ---------------------------------

@app.route('/owner-dashboard')
def owner_dashboard():
    
    
    return render_template('manager_dash.html')

# ---------------------------------
# CHEF DASHBOARD
# ---------------------------------

@app.route('/chef-dashboard')
def chef_dashboard():
    return render_template('chef-dashboard.html')


# ---------------------------------
# WAITER DASHBOARD
# ---------------------------------
@app.route('/clerk-dashboard')
def clerk_dashboard():
    return render_template('waiter-dashboard.html')

# ---------------------------------
# Inventory Pages
# ---------------------------------
@app.route("/owner-dashboard/ingredient_stock")
def ingredient_stock():
    return render_template("ingredient_stock.html")

@app.route("/owner-dashboard/low_stock")
def low_stock():
    return render_template("lowstock.html")


# ---------------------------------
# Purchase Order Pages
# ---------------------------------
@app.route("/owner-dashboard/generate_po")
def generate_po():
    return render_template("generate_po.html")

@app.route("/owner-dashboard/purchase_order")
def purchase_order():
    return render_template("purchase_order.html")


# ---------------------------------
# Reports Pages
# ---------------------------------
@app.route("/owner-dashboard/daily_sales")
def daily_sales():
    return render_template("daily_sales.html")

@app.route("/owner-dashboard/monthly_sales")
def monthly_sales():
    return render_template("monthly_sales.html")

@app.route("/owner-dashboard/expense_report")
def expense_report():
    return render_template("expense_report.html")


# ---------------------------------
# Analytics Page
# ---------------------------------
@app.route("/owner-dashboard/analytics")
def analytics():
    return render_template("analytics.html")


# ---------------------------------
# Payment Page
# ---------------------------------
@app.route("/payment")
def payment():
    def create_order():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "Invalid JSON"}), 400

    cart = data.get('cart', [])
    subtotal = float(data.get('subtotal', 0) or 0)
    discount_amount = float(data.get('discount_amount', 0) or 0)
    final_total = float(data.get('final_total', subtotal) or subtotal)
    customer_name = data.get('customer_name') or None
    customer_email = data.get('customer_email') or None
    payment_status = data.get('payment_status') or 'pending'
    meta = data.get('meta') or {}

    if not cart or len(cart) == 0:
        return jsonify({"success": False, "message": "Cart is empty"}), 400

    cursor = mysql.connection.cursor()
    try:
        # Insert order
        cursor.execute(
            "INSERT INTO orders (customer_name, customer_email, subtotal, discount_amount, final_total, currency, payment_status, order_status, meta) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (customer_name, customer_email, subtotal, discount_amount, final_total, "INR", payment_status, "pending", json.dumps(meta))
        )
        order_id = cursor.lastrowid

        # Insert order items
        for item in cart:
            name = item.get('name')
            qty = int(item.get('qty', 1))
            unit_price = float(item.get('price', 0))
            line_total = round(unit_price * qty, 2)
            note = item.get('notes') if isinstance(item.get('notes'), str) else None

            cursor.execute(
            "INSERT INTO order_items (order_id, item_name, unit_price, qty, line_total, notes) VALUES (%s,%s,%s,%s,%s,%s)",
                (order_id, name, unit_price, qty, line_total, note)
            )

        mysql.connection.commit()

    except Exception as e:
        mysql.connection.rollback()
        cursor.close()
        return jsonify({"success": False, "message": "DB error: " + str(e)}), 500

    cursor.close()
    return jsonify({"success": True, "order_id": order_id}), 201

        # -----------------------
        # Chef: list orders by status (pending or preparing)
        # GET /chef/orders?status=pending
        # -----------------------
    
    
    return render_template("paymentpage.html")

# ---------------------------------
if __name__ == '__main__':
    app.run( host='0.0.0.0' , debug=True,port=5050)
