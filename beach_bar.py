from flask import Flask, render_template, request, jsonify
import requests
import json
import re
import sqlite3
import base64
from io import BytesIO
from PIL import Image

app = Flask(__name__)

# --- ΡΥΘΜΙΣΕΙΣ ---
API_KEY = "AIzaSyDi3MgwXvAqda1APnSHHT6uYl5ZrNF-ymU"
MODEL = "gemini-3-flash-preview" # To 3-flash-preview είναι ασταθές, το 1.5-flash είναι το standard πλέον
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, umbrella TEXT, sender TEXT, text TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS menu 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, price REAL NOT NULL, category TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT id, content FROM orders ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    beach_orders_list = []
    for row in rows:
        try:
            order = json.loads(row[1])
            order['id'] = row[0]
            beach_orders_list.append(order)
        except: continue
    return render_template('dashboard.html', data_list=beach_orders_list)

@app.route('/client')
def client():
    u_number = request.args.get('u', '??') 
    return render_template('client.html', umbrella=u_number)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_text = data.get('text') or data.get('message') or ""
    umbrella_fixed = str(data.get('umbrella') or data.get('umbrella_id') or "??")
    
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT name, price FROM menu")
    rows = c.fetchall()
    
    if not rows:
        menu_context = "Αυτή τη στιγμή δεν έχουμε τίποτα διαθέσιμο."
    else:
        menu_context = "ΚΑΤΑΛΟΓΟΣ:\n" + "\n".join([f"- {r[0]}: {r[1]}€" for r in rows])
    
    system_prompt = f"Είσαι σερβιτόρος στην ομπρέλα {umbrella_fixed}. ΜΕΝΟΥ: {menu_context}. Απάντα σύντομα."

    try:
        resp = requests.post(URL, json={"contents": [{"parts": [{"text": f"{system_prompt}\nΠελάτης: {user_text}"}]}]})
        ai_reply = resp.json()['candidates'][0]['content']['parts'][0]['text']
        return jsonify({"reply": ai_reply})
    except:
        return jsonify({"reply": "Σφάλμα AI. Δοκίμασε πάλι."})
    finally:
        conn.close()

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

@app.route('/delete-menu/<int:item_id>', methods=['POST'])
def delete_menu(item_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("DELETE FROM menu WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/upload-menu-text', methods=['POST'])
def upload_menu_text():
    data = request.json
    raw_text = data.get('text', '')
    if not raw_text: 
        return jsonify({"error": "Το κείμενο είναι κενό"}), 400
        
    prompt = (
        "Ανάλυσε το παρακάτω κείμενο και βρες τα προϊόντα. "
        "Επέστρεψε ΜΟΝΟ ένα JSON array με κλειδιά 'name', 'price', 'category'. "
        "Μην γράψεις κανένα άλλο σχόλιο. Μόνο το JSON σε αγκύλες [ ]. "
        "Κείμενο: " + raw_text
    )

    try:
        resp = requests.post(URL, json={"contents": [{"parts": [{"text": prompt}]}]})
        ai_data = resp.json()['candidates'][0]['content']['parts'][0]['text']
        
        # Καθαρισμός για να βρούμε μόνο το JSON
        match = re.search(r'\[.*\]', ai_data, re.DOTALL)
        
        if match:
            clean_json = match.group()
            menu_items = json.loads(clean_json)

            conn = sqlite3.connect('orders.db')
            c = conn.cursor()
            for item in menu_items:
                try:
                    p_raw = str(item.get('price')).replace('€', '').replace(',', '.').strip()
                    price_val = float(p_raw)
                    c.execute("INSERT INTO menu (name, price, category) VALUES (?, ?, ?)", 
                              (item.get('name'), price_val, item.get('category', 'Γενικά')))
                except: continue
            
            conn.commit()
            conn.close()
            return jsonify({"status": "success", "items_added": len(menu_items)})
        else:
            return jsonify({"error": "Δεν βρέθηκε έγκυρο JSON στην απάντηση του AI"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/delete/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)


