from flask import Flask, render_template, request, jsonify
import requests
import json
import re
import sqlite3
import os

app = Flask(__name__)

# --- ΡΥΘΜΙΣΕΙΣ ---
API_KEY = "AIzaSyDi3MgwXvAqda1APnSHHT6uYl5ZrNF-ymU"
MODEL = "gemini-3-flash-preview" 
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS menu 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, price REAL NOT NULL, category TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT id, content, timestamp FROM orders ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    
    beach_orders_list = []
    for row in rows:
        try:
            # Μετατρέπουμε το κείμενο από τη βάση σε αντικείμενο Python
            order_data = json.loads(row[1])
            order_data['id'] = row[0]
            order_data['timestamp'] = row[2]
            beach_orders_list.append(order_data)
        except Exception as e:
            print(f"Error parsing order {row[0]}: {e}")
            continue
    return render_template('dashboard.html', data_list=beach_orders_list)

@app.route('/admin-menu', methods=['GET', 'POST'])
def admin_menu():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        category = request.form.get('category')
        if name and price:
            c.execute("INSERT INTO menu (name, price, category) VALUES (?, ?, ?)", (name, price, category))
            conn.commit()
    c.execute("SELECT id, name, price, category FROM menu ORDER BY category")
    items = c.fetchall()
    conn.close()
    return render_template('admin_menu.html', items=items)

@app.route('/upload-menu-text', methods=['POST'])
def upload_menu_text():
    data = request.json
    raw_text = data.get('text', '')
    prompt = f"Μετάτρεψε αυτό σε JSON array με name, price, category: {raw_text}"
    try:
        resp = requests.post(URL, json={"contents": [{"parts": [{"text": prompt}]}]})
        ai_data = resp.json()['candidates'][0]['content']['parts'][0]['text']
        match = re.search(r'\[.*\]', ai_data, re.DOTALL)
        if match:
            items = json.loads(match.group())
            conn = sqlite3.connect('orders.db')
            c = conn.cursor()
            for i in items:
                p = str(i.get('price', 0)).replace(',', '.')
                c.execute("INSERT INTO menu (name, price, category) VALUES (?, ?, ?)", (i.get('name'), float(p), i.get('category')))
            conn.commit()
            conn.close()
            return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_text = data.get('text') or ""
    umbrella = data.get('umbrella', '7')
    
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT name, price FROM menu")
    rows = c.fetchall()
    menu_txt = "\n".join([f"{r[0]}: {r[1]}€" for r in rows])
    
    prompt = f"Είσαι σερβιτόρος στην ομπρέλα {umbrella}. ΜΕΝΟΥ: {menu_txt}. Αν παραγγείλουν, γράψε ORDER_JSON {{'items': [{{'name': '...', 'price': ...}}], 'total': ..., 'umbrella': '{umbrella}'}}"

    try:
        resp = requests.post(URL, json={"contents": [{"parts": [{"text": f"{prompt}\nΠελάτης: {user_text}"}]}]})
        ai_reply = resp.json()['candidates'][0]['content']['parts'][0]['text']
        
        if "ORDER_JSON" in ai_reply:
            match = re.search(r'\{.*\}', ai_reply, re.DOTALL)
            if match:
                # Αποθηκεύουμε ως έγκυρο JSON για να το διαβάζει το Ιστορικό
                order_json = match.group().replace("'", '"') 
                c.execute("INSERT INTO orders (content) VALUES (?)", (order_json,))
                conn.commit()
        
        return jsonify({"reply": ai_reply.split("ORDER_JSON")[0].strip()})
    except Exception as e:
        return jsonify({"reply": "Σφάλμα"}), 500
    finally:
        conn.close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

