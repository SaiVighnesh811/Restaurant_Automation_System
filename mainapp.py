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

app = Flask(__name__)
# small secret for sessions (change or remove if you want no session behavior)
app.secret_key = "dev-secret"

# ---------------------------------
# MySQL Configuration
# ---------------------------------
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'example_user'
app.config['MYSQL_PASSWORD'] = 'password'
app.config['MYSQL_DB'] = 'restaurent_db'
app.config['MYSQL_PORT'] = 3306

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
    # you can flash a message here if you want:
    # flash("Logged out", "success")
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
            # NOTE: currently storing plain password; change to hashed if desired:
            cursor.execute(
                "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
                (username, email, password, role)
            )
            mysql.connection.commit()
            flash("Account created successfully! Please login.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            mysql.connection.rollback()
            app.logger.exception("Error creating account")
            flash("Error creating account: " + str(e), "danger")
            return redirect(url_for('signup'))
        finally:
            cursor.close()

    return render_template('signup.html')


# ---------------------------------
# LOGIN PAGE
# ---------------------------------
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
        try:
            cursor.execute("SELECT id, username, email, password, role FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
        finally:
            cursor.close()

        if user:
            user_id, username, db_email, db_password, role = user

            # DIRECT comparison (plain text)
            if password == db_password:
                # successful login (session will work because secret_key is set)
                session['user_id'] = user_id
                session['username'] = username
                session['email'] = db_email
                session['role'] = role

                flash("Login successful", "success")

                # redirect by role (example)
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
    return render_template('forget_password.html')

@app.route('/loginpage/forgot/otp')
def forgot_password_otp():
    return render_template('forget_otp.html')
# ---------------------------------
# OWNER DASHBOARD PAGE (open access)
# ---------------------------------
@app.route('/owner-dashboard')
def owner_dashboard():
    # pass logout_url so templates never need to inspect globals()
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
    """
    Returns quick summary for today's totals:
      - total_sales_today (sum of final_total where DATE(created_at)=CURDATE())
      - total_orders_today (count)
      - low_stock_count (placeholder 0 unless you have an inventory table)
      - pending_pos (placeholder 0 unless you have a purchase_orders table)
    """
    cursor = mysql.connection.cursor()
    try:
        # Total sales & orders for today
        cursor.execute(
            "SELECT COALESCE(SUM(final_total),0) AS total_sales, COUNT(*) AS total_orders "
            "FROM orders WHERE DATE(created_at) = CURDATE()"
        )
        row = cursor.fetchone() or (0, 0)
        # cursor.fetchone returns a tuple; mapping via cursor.description safer:
        if cursor.description:
            cols = [c[0] for c in cursor.description]
            mapped = dict(zip(cols, row))
            total_sales_today = float(mapped.get('total_sales') or 0)
            total_orders_today = int(mapped.get('total_orders') or 0)
        else:
            total_sales_today = float(row[0] or 0)
            total_orders_today = int(row[1] or 0)

        # low_stock_count and pending_pos require inventory/po tables.
        # Return 0 by default and document how to replace with your own queries.
        low_stock_count = 0
        pending_pos = 0

        # Example (commented) - replace with your actual inventory table query:
        # cursor.execute("SELECT COUNT(*) FROM ingredients WHERE qty < reorder_level")
        # low_stock_count = int(cursor.fetchone()[0] or 0)

        # Example (commented) - replace with your actual purchase_orders table query:
        # cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE status = 'pending'")
        # pending_pos = int(cursor.fetchone()[0] or 0)

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
    """
    Returns top sold items for the given window.
    Query param:
      - days (int) default 30
    Response:
      { success: True, usage: [{item: "Burger", qty: 120}, ...] }
    """
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
        
        # Record transaction
        cursor.execute(
            "INSERT INTO inventory_transactions (ingredient_id, transaction_type, quantity, note, created_by) VALUES (%s, %s, %s, %s, %s)",
            (ingredient_id, 'usage', quantity, note, session['user_id'])
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
            (po_number, json.dumps(supplier_info), session['user_id'])
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
                po['supplier_info'] = json.loads(po['supplier_info'])
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
            po_dict['supplier_info'] = json.loads(po_dict['supplier_info'])
        
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
                
                # Record inventory transaction
                cursor.execute("""
                    INSERT INTO inventory_transactions 
                    (ingredient_id, transaction_type, quantity, note, created_by)
                    VALUES (%s, %s, %s, %s, %s)
                """, (ingredient_id, 'purchase', quantity, f'PO #{po_id} received', session['user_id']))
        
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
        # First, check if expenses table exists
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'restaurent_db' AND table_name = 'expenses'
        """)
        expenses_table_exists = cursor.fetchone() is not None
        
        if not expenses_table_exists:
            # Return sample data structure for demonstration
            sample_expenses = []
            sample_summary = {
                "total_amount": 0,
                "expense_count": 0,
                "average_amount": 0
            }
            return jsonify({
                "success": True, 
                "expenses": sample_expenses, 
                "summary": sample_summary,
                "message": "Expenses table not found - using sample data structure"
            })
        
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

# Create expenses table (run this once to set up the table)
def create_expenses_table():
    cursor = mysql.connection.cursor()
    try:
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
        print("Expenses table created successfully")
    except Exception as e:
        print(f"Error creating expenses table: {e}")
    finally:
        cursor.close()

# Add sample expenses data (optional - for testing)
def add_sample_expenses():
    cursor = mysql.connection.cursor()
    try:
        sample_expenses = [
            ('EXP001', '2025-10-01', 'Ingredient Purchase', 'ABC Foods', None, 'Monthly ingredient restock', 12000.00, 'Cheque'),
            ('EXP002', '2025-10-02', 'Utilities', None, 'Electricity Board', 'Monthly electricity bill', 5000.00, 'Bank Transfer'),
            ('EXP003', '2025-10-05', 'Ingredient Purchase', 'XYZ Supplies', None, 'Special order for weekend', 8500.00, 'Cash'),
            ('EXP004', '2025-10-10', 'Equipment Maintenance', 'Tech Services Ltd', None, 'Oven repair service', 3200.00, 'Online Payment'),
            ('EXP005', '2025-10-15', 'Rent', None, 'Property Owner', 'Monthly restaurant rent', 25000.00, 'Bank Transfer'),
            ('EXP006', '2025-10-20', 'Marketing', 'Digital Ads Co', None, 'Social media campaign', 7500.00, 'Online Payment'),
            ('EXP007', '2025-10-25', 'Staff Salary', None, 'Employee Payments', 'October staff salaries', 45000.00, 'Bank Transfer'),
            ('EXP008', '2025-10-28', 'Ingredient Purchase', 'Fresh Produce Co', None, 'Vegetables and fruits', 6800.00, 'Cash')
        ]
        
        for expense in sample_expenses:
            cursor.execute("""
                INSERT IGNORE INTO expenses 
                (expense_number, expense_date, expense_type, supplier_name, payee, description, amount, payment_mode)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, expense)
        
        mysql.connection.commit()
        print("Sample expenses added successfully")
    except Exception as e:
        print(f"Error adding sample expenses: {e}")
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
        # Check if expenses table exists
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'restaurent_db' AND table_name = 'expenses'
        """)
        expenses_exists = cursor.fetchone() is not None
        
        if expenses_exists:
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
        else:
            # Fallback: estimate expenses from purchase orders and other sources
            cursor.execute("""
                SELECT 
                    'Ingredient Purchase' as expense_type,
                    COALESCE(SUM(total_amount), 0) as total_amount,
                    COUNT(*) as count
                FROM purchase_orders 
                WHERE status = 'received' 
                AND created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                
                UNION ALL
                
                SELECT 
                    'Employee Salaries' as expense_type,
                    COUNT(*) * 15000 as total_amount,  # Estimate
                    COUNT(*) as count
                FROM employees 
                WHERE status = 'active'
                
                UNION ALL
                
                SELECT 
                    'Utilities' as expense_type,
                    5000 as total_amount,  # Estimate
                    1 as count
                
                UNION ALL
                
                SELECT 
                    'Maintenance' as expense_type,
                    2000 as total_amount,  # Estimate
                    1 as count
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
        
        # Get expense data (from purchase orders as proxy)
        cursor.execute("""
            SELECT 
                DATE_FORMAT(created_at, '%Y-%m') as month,
                SUM(total_amount) as expenses
            FROM purchase_orders 
            WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
            AND status = 'received'
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
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
# Uncomment the lines below to create the table and add sample data:
# create_expenses_table()
# add_sample_expenses()
# ---------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5050)