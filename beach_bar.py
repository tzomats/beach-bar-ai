from flask import Flask, render_template, request, jsonify
import requests
import json
import re
import sqlite3

app = Flask(__name__)

API_KEY = "AIzaSyCu6l9azuUcex5x02gX8nCUr9ZIbq2JccM"
MODEL = "gemini-1.5-flash"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    # Πίνακας Παραγγελιών (κουζίνα)
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    # ΝΕΟΣ Πίνακας Συνομιλιών (για τον υπεύθυνο)
    c.execute('''CREATE TABLE IF NOT EXISTS messages 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, umbrella TEXT, sender TEXT, text TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_text = data.get('text', '')
    umbrella_fixed = str(data.get('umbrella', '??'))
    
    # 1. Αποθήκευση μηνύματος πελάτη στη βάση
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("INSERT INTO messages (umbrella, sender, text) VALUES (?, ?, ?)", (umbrella_fixed, 'Πελάτης', user_text))
    
    system_instruction = (
        f"Είσαι σερβιτόρος στην ΟΜΠΡΕΛΑ {umbrella_fixed}. Απάντησε σύντομα. "
        "Αν παραγγείλει, γράψε ORDER_JSON και το JSON: "
        "{\"umbrella_number\": \"" + umbrella_fixed + "\", \"products_list\": [{\"name\": \"...\", \"qty\": 1}]}"
    )
    
    try:
        resp = requests.post(URL, json={"contents": [{"parts": [{"text": f"{system_instruction}\nΠελάτης: {user_text}"}]}]})
        ai_reply = resp.json()['candidates'][0]['content']['parts'][0]['text']
        
        # 2. Αποθήκευση απάντησης AI στη βάση
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

# Σελίδα για τον υπεύθυνο να βλέπει το ιστορικό συνομιλιών
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

# Οι υπόλοιπες διαδρομές (index, delete, κτλ) παραμένουν ίδιες...
