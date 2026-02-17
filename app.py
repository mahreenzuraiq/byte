from flask import Flask, render_template, request, session, redirect, url_for, send_from_directory
import psycopg2
import random
import json

app = Flask(__name__)
app.secret_key = "byte_official_secret"

def get_db_connection():
    return psycopg2.connect(
        database="postgres",
        user="postgres",
        password="dbmsbyte123",
        host="db.juypzygnvagvpfqwqpmd.supabase.co",
        port="5432",
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
    
    # Fetch current customer details to display on the review page
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
    
    # Grab the updated address from the Review page
    street = request.form.get('street')
    city = request.form.get('city')
    
    # Update the database with the delivery address before moving to payment
    if street and city:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE customer SET street = %s, city = %s WHERE customer_id = %s", (street, city, session['customer_id']))
        conn.commit()
        cur.close()
        conn.close()
        
    return render_template('payment.html', cart_data=cart_data, total=total)

@app.route('/process_payment', methods=['POST'])
def process_payment():
    cart_data = json.loads(request.form.get('cart_data'))
    total = request.form.get('total_amount')
    pay_mode = request.form.get('payment_mode') 
    cust_id = session.get('customer_id')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT agent_id FROM delivery_agent")
        agent_ids = [row[0] for row in cur.fetchall()]
        assigned_agent = random.choice(agent_ids)

        cur.execute("""
            INSERT INTO orders (customer_id, agent_id, payment_mode, total_amount)
            VALUES (%s, %s, %s, %s) RETURNING order_id
        """, (cust_id, assigned_agent, pay_mode, total))
        new_order_id = cur.fetchone()[0]

        for item in cart_data:
            cur.execute("""
                INSERT INTO order_items (order_id, item_id, quantity, unit_price)
                VALUES (%s, %s, %s, %s)
            """, (new_order_id, item['id'], item['quantity'], item['price']))

        conn.commit()

        return f"""
            <div style="text-align:center; padding:100px; font-family:sans-serif; background:#e3f2fd; height:100vh;">
                <h1 style="color:#1565c0;">Payment Confirmed!</h1>
                <p style="font-size:2rem;">Your Order Number: <strong>#{new_order_id}</strong></p>
                <p>Delivery Agent ID: {assigned_agent} | Paid via: {pay_mode}</p>
                <a href="/" style="text-decoration:none; color:white; background:#1e88e5; padding:10px 20px; border-radius:5px; margin-top: 20px; display: inline-block;">Back to Home</a>
            </div>
        """
    except Exception as e:
        conn.rollback()
        return f"An error occurred: {str(e)}"
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)