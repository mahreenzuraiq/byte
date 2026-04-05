from flask import Flask, render_template, request, session, redirect, url_for, send_from_directory
import psycopg2
import random
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = "byte_official_secret"

# --- BULLETPROOF DATABASE CONNECTION ---
def get_db_connection():
    return psycopg2.connect(
        database="postgres",
        user="postgres.juypzygnvagvpfqwqpmd",              # Project ID included
        password="dbmsbyte123",
        host="aws-1-ap-northeast-2.pooler.supabase.com",   # IPv4 Pooler URL
        port="6543",                                       # Pooler Port
        sslmode="require"
    )

@app.route('/templates/<path:filename>')
def serve_templates_images(filename):
    return send_from_directory('templates', filename)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['POST'])
def login():
    phone = request.form.get('phone')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT customer_id, customer_name FROM customer WHERE phone_number = %s", (phone,))
    customer = cur.fetchone()
    cur.close()
    conn.close()
    
    if customer:
        session['customer_id'] = customer[0]
        session['customer_name'] = customer[1]
        return redirect(url_for('menu'))
    else:
        return "<script>alert('Number not found. Please Sign Up first!'); window.location.href='/';</script>"

@app.route('/signup', methods=['POST'])
def signup():
    name = request.form.get('name')
    phone = request.form.get('phone')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT customer_id FROM customer WHERE phone_number = %s", (phone,))
    if cur.fetchone():
        cur.close()
        conn.close()
        return "<script>alert('Number already registered! Please Login.'); window.location.href='/';</script>"
        
    cur.execute("""
        INSERT INTO customer (customer_name, phone_number) 
        VALUES (%s, %s) RETURNING customer_id
    """, (name, phone))
    
    session['customer_id'] = cur.fetchone()[0]
    session['customer_name'] = name
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('menu'))

# --- USER PROFILE ROUTE ---
@app.route('/profile')
def profile():
    if 'customer_id' not in session:
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT customer_name, phone_number, street, city FROM customer WHERE customer_id = %s", (session['customer_id'],))
    cust_info = cur.fetchone()
    cur.close()
    conn.close()
    
    customer = {
        "name": cust_info[0],
        "phone": cust_info[1],
        "street": cust_info[2] if cust_info[2] else "Not provided yet",
        "city": cust_info[3] if cust_info[3] else "Not provided yet"
    }
    
    return render_template('profile.html', customer=customer)

@app.route('/menu')
def menu():
    if 'customer_id' not in session:
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT item_id, item_name, description, price, image_url FROM food_items ORDER BY item_id")
    rows = cur.fetchall()
    foods = [{"item_id": r[0], "item_name": r[1], "description": r[2], "price": float(r[3]), "image_url": r[4]} for r in rows]
    
    cur.close()
    conn.close()
    return render_template('menu.html', foods=foods)

@app.route('/review', methods=['POST'])
def review():
    cart_data_raw = request.form.get('cart_data')
    total = request.form.get('total_amount')
    cart_items = json.loads(cart_data_raw)
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT customer_name, phone_number, street, city FROM customer WHERE customer_id = %s", (session['customer_id'],))
    cust_info = cur.fetchone()
    cur.close()
    conn.close()
    
    customer = {
        "name": cust_info[0],
        "phone": cust_info[1],
        "street": cust_info[2] if cust_info[2] else "",
        "city": cust_info[3] if cust_info[3] else ""
    }
    
    return render_template('review.html', cart_items=cart_items, total=total, cart_data_raw=cart_data_raw, customer=customer)

@app.route('/payment', methods=['POST'])
def payment():
    cart_data = request.form.get('cart_data')
    total = request.form.get('total_amount')
    
    street = request.form.get('street')
    city = request.form.get('city')
    
    if street and city:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE customer SET street = %s, city = %s WHERE customer_id = %s", (street, city, session['customer_id']))
        conn.commit()
        cur.close()
        conn.close()
        
    return render_template('payment.html', cart_data=cart_data, total=total)

# --- PROCESS PAYMENT & GENERATE RECEIPT ---
@app.route('/process_payment', methods=['POST'])
def process_payment():
    cart_data = json.loads(request.form.get('cart_data'))
    total = request.form.get('total_amount')
    pay_mode = request.form.get('payment_mode') 
    cust_id = session.get('customer_id')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 1. Assign a random delivery agent
        cur.execute("SELECT agent_id, agent_name FROM delivery_agent")
        agents = cur.fetchall()
        assigned_agent = random.choice(agents)
        agent_id = assigned_agent[0]
        agent_name = assigned_agent[1]

        # 2. Create the Order
        cur.execute("""
            INSERT INTO orders (customer_id, agent_id, payment_mode, total_amount)
            VALUES (%s, %s, %s, %s) RETURNING order_id
        """, (cust_id, agent_id, pay_mode, total))
        new_order_id = cur.fetchone()[0]

        # 3. Add Items to Order
        for item in cart_data:
            cur.execute("""
                INSERT INTO order_items (order_id, item_id, quantity, unit_price)
                VALUES (%s, %s, %s, %s)
            """, (new_order_id, item['id'], item['quantity'], item['price']))

        conn.commit()

        # 4. Generate ETA and Date for the Receipt
        delivery_time = random.randint(20, 45)
        current_date = datetime.now().strftime("%d %b %Y, %I:%M %p")

        # 5. Render the final bill
        return render_template('bill.html', 
                               order_id=new_order_id, 
                               agent_name=agent_name, 
                               pay_mode=pay_mode, 
                               total=total, 
                               cart_data=cart_data, 
                               delivery_time=delivery_time,
                               date=current_date,
                               customer_name=session.get('customer_name'))
    except Exception as e:
        conn.rollback()
        return f"An error occurred: {str(e)}"
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)