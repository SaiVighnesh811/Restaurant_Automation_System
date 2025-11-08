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
    return render_template("paymentpage.html")






'''


# ---------- READ ----------
@app.route("/ingredient_stock")
def ingredient_stock():
    # --- FIX: Use the 'mysql' object and a DictCursor ---
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM ingredients")
    ingredients = cursor.fetchall()
    cursor.close() # --- FIX: Close the cursor ---

    for i in ingredients:
        if i["stock_quantity"] <= i["reorder_level"]:
            i["status"] = "⚠️ Low"
        else:
            i["status"] = "✅ Sufficient"

    return render_template("ingredient_stock.html", ingredients=ingredients)

# ---------- CREATE ----------
@app.route("/add_ingredient", methods=["GET", "POST"])
def add_ingredient():
    if request.method == "POST":
        name = request.form["name"]
        stock_quantity = request.form["stock_quantity"]
        unit = request.form["unit"]
        reorder_level = request.form["reorder_level"]

        # --- FIX: Use the 'mysql' object ---
        cursor = mysql.connection.cursor()
        cursor.execute(
            "INSERT INTO ingredients (name, stock_quantity, unit, reorder_level) VALUES (%s, %s, %s, %s)",
            (name, stock_quantity, unit, reorder_level)
        )
        mysql.connection.commit() # --- FIX: Commit using mysql.connection ---
        cursor.close() # --- FIX: Close the cursor ---
        
        flash("Ingredient added successfully!", "success")
        return redirect(url_for("ingredient_stock"))
    
    return render_template("ingredient_form.html", action="Add", ingredient=None) # Pass ingredient=None for safety

# ---------- UPDATE ----------
@app.route("/edit_ingredient/<int:id>", methods=["GET", "POST"])
def edit_ingredient(id):
    # --- FIX: Use the 'mysql' object and a DictCursor to fetch ---
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM ingredients WHERE id = %s", (id,))
    ingredient = cursor.fetchone()
    
    if request.method == "POST":
        name = request.form["name"]
        stock_quantity = request.form["stock_quantity"]
        unit = request.form["unit"]
        reorder_level = request.form["reorder_level"]

        # --- FIX: Use the same cursor (or a new one) for the update ---
        cursor.execute("""
            UPDATE ingredients 
            SET name=%s, stock_quantity=%s, unit=%s, reorder_level=%s 
            WHERE id=%s
        """, (name, stock_quantity, unit, reorder_level, id))
        mysql.connection.commit() # --- FIX: Commit using mysql.connection ---
        cursor.close() # --- FIX: Close the cursor ---
        
        flash("Ingredient updated successfully!", "success")
        return redirect(url_for("ingredient_stock"))

    cursor.close() # --- FIX: Close cursor if it was a GET request ---
    if not ingredient:
        flash("Ingredient not found!", "danger")
        return redirect(url_for("ingredient_stock"))
        
    return render_template("ingredient_form.html", ingredient=ingredient, action="Edit")

# ---------- DELETE ----------
@app.route("/delete_ingredient/<int:id>")
def delete_ingredient(id):
    # --- FIX: Use the 'mysql' object ---
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM ingredients WHERE id = %s", (id,))
    mysql.connection.commit() # --- FIX: Commit using mysql.connection ---
    cursor.close() # --- FIX: Close the cursor ---
    
    flash("Ingredient deleted successfully.", "success")
    return redirect(url_for("ingredient_stock"))









'''



'''
# ---------------------------------
# PAGE 1: New Order
# ---------------------------------
@app.route('/new_order', methods=['GET', 'POST'])
def new_order():
    if request.method == 'POST':
        customer_name = request.form['customer_name']

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO orders (customer_name) VALUES (%s)", [customer_name])
        mysql.connection.commit()
        order_id = cur.lastrowid
        cur.close()

        return redirect(url_for('add_items', order_id=order_id))

    return render_template('new_order.html')

# ---------------------------------
# PAGE 2: Add Items (AUTO PRICE)
# ---------------------------------
@app.route('/add_items/<int:order_id>', methods=['GET', 'POST'])
def add_items(order_id):
    cur = mysql.connection.cursor()

    # Fetch menu items for dropdown
    cur.execute("SELECT menu_id, item_name, price FROM menu_items")
    menu_items = cur.fetchall()

    if request.method == 'POST':
        menu_id = int(request.form['menu_item_id'])
        quantity = int(request.form['quantity'])

        # Get item details from menu_items
        cur.execute("SELECT item_name, price FROM menu_items WHERE menu_id = %s", [menu_id])
        item = cur.fetchone()
        item_name, price = item[0], float(item[1])

        # Insert into order_items
        cur.execute("""
            INSERT INTO order_items (order_id, item_name, quantity, price)
            VALUES (%s, %s, %s, %s)
        """, (order_id, item_name, quantity, price))
        mysql.connection.commit()

    # Fetch current items for display
    cur.execute("SELECT item_name, quantity, price FROM order_items WHERE order_id = %s", [order_id])
    items = cur.fetchall()
    cur.close()

    return render_template('add_items.html', order_id=order_id, items=items, menu_items=menu_items)

# ---------------------------------
# PAGE 3: Generate Bill
# ---------------------------------
@app.route('/generate_bill/<int:order_id>')
def generate_bill(order_id):
    cur = mysql.connection.cursor()

    # Order info
    cur.execute("SELECT customer_name, order_date FROM orders WHERE order_id = %s", [order_id])
    order = cur.fetchone()

    # Items
    cur.execute("SELECT item_name, quantity, price FROM order_items WHERE order_id = %s", [order_id])
    items = cur.fetchall()

    # Total calculation
    total = sum(q * p for _, q, p in items)
    cur.execute("UPDATE orders SET total_amount = %s WHERE order_id = %s", (total, order_id))
    mysql.connection.commit()

    # Daily sales
    today = date.today()
    cur.execute("""
        INSERT INTO daily_sales (date, total_sales)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE total_sales = total_sales + %s
    """, (today, total, total))
    mysql.connection.commit()
    cur.close()

    return render_template('generate_bill.html', order=order, items=items, total=total)

# ---------------------------------
# PAGE 4: Order History
# ---------------------------------
@app.route('/order_history')
def order_history():
    cur = mysql.connection.cursor()
    cur.execute("SELECT order_id, customer_name, order_date, total_amount FROM orders ORDER BY order_date DESC")
    orders = cur.fetchall()
    cur.close()
    return render_template('order_history.html', orders=orders)
    git token -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
    '''
# ---------------------------------
if __name__ == '__main__':
    app.run( host='0.0.0.0' , debug=True,port=5050)
