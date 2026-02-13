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
MODEL = "gemini-1.5-flash" # Προτείνω το 1.5 flash για καλύτερη υποστήριξη εικόνας
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
    user_text = data.get('text', '')
    umbrella_fixed = str(data.get('umbrella', '??'))
    
    # 1. ΦΟΡΤΩΝΟΥΜΕ ΤΟ ΜΕΝΟΥ ΑΠΟ ΤΗ ΒΑΣΗ
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT name, price, category FROM menu")
    menu_rows = c.fetchall()
    
    menu_context = "ΤΟ ΜΕΝΟΥ ΜΑΣ:\n"
    for item in menu_rows:
        menu_context += f"- {item[0]} ({item[2]}): {item[1]}€\n"
    
    # Αποθήκευση μηνύματος πελάτη
    c.execute("INSERT INTO messages (umbrella, sender, text) VALUES (?, ?, ?)", (umbrella_fixed, 'Πελάτης', user_text))
    
    # 2. ΟΔΗΓΙΕΣ ΣΤΟ AI (SYSTEM PROMPT)
    system_instruction = (
        f"Είσαι σερβιτόρος στην ΟΜΠΡΕΛΑ {umbrella_fixed}. "
        f"Χρησιμοποίησε ΑΥΤΟ ΤΟ ΜΕΝΟΥ: {menu_context}. "
        "Απάντησε σύντομα. Κατάλαβε Greeklish και ορθογραφικά. "
        "Αν ο πελάτης παραγγείλει, γράψε ΟΠΩΣΔΗΠΟΤΕ ORDER_JSON και μετά το JSON: "
        "{\"umbrella_number\": \"" + umbrella_fixed + "\", \"products_list\": [{\"name\": \"...\", \"qty\": 1}]}"
    )
    
    try:
        resp = requests.post(URL, json={"contents": [{"parts": [{"text": f"{system_instruction}\nΠελάτης: {user_text}"}]}]})
        ai_reply = resp.json()['candidates'][0]['content']['parts'][0]['text']
        
        clean_ai_text = ai_reply.split("ORDER_JSON")[0].strip()
        c.execute("INSERT INTO messages (umbrella, sender, text) VALUES (?, ?, ?)", (umbrella_fixed, 'AI', clean_ai_text))
        
        if "ORDER_JSON" in ai_reply:
            json_str = re.search(r'\{.*\}', ai_reply, re.DOTALL).group()
            c.execute("INSERT INTO orders (content) VALUES (?)", (json_str,))
            
        conn.commit()
        conn.close()
        return jsonify({"reply": clean_ai_text})
    except Exception as e:
        return jsonify({"reply": f"Σφάλμα AI: {str(e)}"})

@app.route('/admin-menu', methods=['GET', 'POST'])
def admin_menu():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        category = request.form.get('category')
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

@app.route('/upload-menu-photo', methods=['POST'])
def upload_menu_photo():
    if 'photo' not in request.files:
        return jsonify({"error": "No photo uploaded"}), 400
    file = request.files['photo']
    image = Image.open(file).convert('RGB')
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    prompt = "Analyze this menu photo. Return ONLY a JSON array with 'name', 'price', 'category'. No extra text."

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": img_str}}
            ]
        }]
    }

    try:
        resp = requests.post(URL, json=payload)
        ai_data = resp.json()['candidates'][0]['content']['parts'][0]['text']
        clean_json = re.search(r'\[.*\]', ai_data, re.DOTALL).group()
        menu_items = json.loads(clean_json)

        conn = sqlite3.connect('orders.db')
        c = conn.cursor()
        for item in menu_items:
            # Διόρθωση τιμής αν έρθει ως κείμενο
            p = str(item['price']).replace('€', '').replace(',', '.').strip()
            c.execute("INSERT INTO menu (name, price, category) VALUES (?, ?, ?)", (item['name'], float(p), item['category']))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "items_added": len(menu_items)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/upload-menu-text', methods=['POST'])
def upload_menu_text():
    data = request.json
    raw_text = data.get('text', '')
    if not raw_text: return jsonify({"error": "Κενό κείμενο"}), 400
    
    prompt = f"Μετάτρεψε αυτό το κείμενο σε JSON με 'name', 'price', 'category': {raw_text}"
    
    try:
        resp = requests.post(URL, json={"contents": [{"parts": [{"text": prompt}]}]})
        ai_data = resp.json()['candidates'][0]['content']['parts'][0]['text']
        clean_json = re.search(r'\[.*\]', ai_data, re.DOTALL).group()
        menu_items = json.loads(clean_json)

        conn = sqlite3.connect('orders.db')
        c = conn.cursor()
        for item in menu_items:
            p = str(item['price']).replace('€', '').replace(',', '.').strip()
            c.execute("INSERT INTO menu (name, price, category) VALUES (?, ?, ?)", (item['name'], float(p), item['category']))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "items_added": len(menu_items)})
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
