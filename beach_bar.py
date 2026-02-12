from flask import Flask, render_template, request, jsonify
import requests
import json
import re
import sqlite3

app = Flask(__name__)

# --- ΟΙ ΣΩΣΤΕΣ ΡΥΘΜΙΣΕΙΣ ΣΟΥ ---
API_KEY = "AIzaSyDi3MgwXvAqda1APnSHHT6uYl5ZrNF-ymU"
MODEL = "gemini-3-flash-preview"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    # Πίνακας Παραγγελιών
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    # Πίνακας Συνομιλιών (Logs)
    c.execute('''CREATE TABLE IF NOT EXISTS messages 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, umbrella TEXT, sender TEXT, text TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
    # Πίνακας για το Μενού
    c.execute('''CREATE TABLE IF NOT EXISTS menu 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  name TEXT NOT NULL, 
                  price REAL NOT NULL, 
                  category TEXT, 
                  image_url TEXT)''')

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
        order = json.loads(row[1])
        order['id'] = row[0]
        beach_orders_list.append(order)
    return render_template('dashboard.html', data_list=beach_orders_list)

@app.route('/client')
def client():
    u_number = request.args.get('u', '') 
    return render_template('client.html', umbrella=u_number)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_text = data.get('text', '')
    umbrella_fixed = str(data.get('umbrella', '??'))
    
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    # Αποθήκευση μηνύματος πελάτη
    c.execute("INSERT INTO messages (umbrella, sender, text) VALUES (?, ?, ?)", (umbrella_fixed, 'Πελάτης', user_text))
    
    system_instruction = (
        f"Είσαι σερβιτόρος στην ΟΜΠΡΕΛΑ {umbrella_fixed}. Απάντησε σύντομα. "
        "ΟΤΑΝ ο πελάτης παραγγείλει, γράψε ΟΠΩΣΔΗΠΟΤΕ ORDER_JSON και μετά το JSON: "
        "{\"umbrella_number\": \"" + umbrella_fixed + "\", \"products_list\": [{\"name\": \"...\", \"qty\": 1}]}"
    )
    
    try:
        resp = requests.post(URL, json={"contents": [{"parts": [{"text": f"{system_instruction}\nΠελάτης: {user_text}"}]}]})
        ai_reply = resp.json()['candidates'][0]['content']['parts'][0]['text']
        
        # Αποθήκευση απάντησης AI (χωρίς το JSON)
        clean_ai_text = ai_reply.split("ORDER_JSON")[0].strip()
        c.execute("INSERT INTO messages (umbrella, sender, text) VALUES (?, ?, ?)", (umbrella_fixed, 'AI', clean_ai_text))
        
        if "ORDER_JSON" in ai_reply:
            json_str = re.search(r'\{.*\}', ai_reply, re.DOTALL).group()
            c.execute("INSERT INTO orders (content) VALUES (?)", (json_str,))
            
        conn.commit()
        conn.close()
        return jsonify({"reply": clean_ai_text})
    except:
        return jsonify({"reply": "Σφάλμα σύνδεσης."})

@app.route('/owner-history')
def owner_history():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT id, content, timestamp FROM orders ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    history_list = []
    for row in rows:
        order = json.loads(row[1])
        order['id'] = row[0]
        order['time'] = row[2]
        history_list.append(order)
    return render_template('history.html', data_list=history_list)

@app.route('/admin-logs')
def admin_logs():
    umbrella = request.args.get('u')
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    if umbrella:
        c.execute("SELECT sender, text, timestamp FROM messages WHERE umbrella = ? ORDER BY id ASC", (umbrella,))
    else:
        c.execute("SELECT umbrella, sender, text, timestamp FROM messages ORDER BY id DESC LIMIT 100")
    logs = c.fetchall()
    conn.close()
    return render_template('logs.html', logs=logs)

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

