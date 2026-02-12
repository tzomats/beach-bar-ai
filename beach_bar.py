from flask import Flask, render_template, request, jsonify
import requests
import json
import re
import sqlite3

app = Flask(__name__)

API_KEY = "AIzaSyDi3MgwXvAqda1APnSHHT6uYl5ZrNF-ymU"
MODEL = "gemini-3-flash-preview"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

# --- ΡΥΘΜΙΣΗ ΒΑΣΗΣ ΔΕΔΟΜΕΝΩΝ ---
def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  content TEXT, 
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT content FROM orders ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    beach_orders_list = [json.loads(row[0]) for row in rows]
    return render_template('dashboard.html', data_list=beach_orders_list)

@app.route('/client')
def client():
    # Παίρνει το 'u' από το link (π.χ. ?u=5). Αν δεν υπάρχει, αφήνει κενό.
    u_number = request.args.get('u', '') 
    return render_template('client.html', umbrella=u_number)

@app.route('/chat', methods=['POST'])
def chat():
    user_text = request.json.get('text', '')
    system_instruction = (
        "Είσαι ένας ευγενικός σερβιτόρος σε beach bar στην Ελλάδα. "
        "Απάντησε στον πελάτη σύντομα και φιλικά. "
        "Αν ο πελάτης παραγγέλνει κάτι ΚΑΙ δώσει νούμερο ομπρέλας, "
        "πρόσθεσε στο τέλος της απάντησής σου τη λέξη ORDER_JSON ακολουθούμενη από το JSON "
        "με κλειδιά 'umbrella_number' και 'products_list' (name, qty). "
        "Αν δεν δώσει ομπρέλα, ζήτησέ την ευγενικά."
    )
    
    prompt = f"{system_instruction}\nΠελάτης: {user_text}"
    
    try:
        resp = requests.post(URL, json={"contents": [{"parts": [{"text": prompt}]}]})
        ai_full_reply = resp.json()['candidates'][0]['content']['parts'][0]['text']
        
        if "ORDER_JSON" in ai_full_reply:
            parts = ai_full_reply.split("ORDER_JSON")
            visible_reply = parts[0].strip()
            json_part = re.search(r'\{.*\}', parts[1], re.DOTALL)
            
            if json_part:
                order_data = json.loads(json_part.group())
                conn = sqlite3.connect('orders.db')
                c = conn.cursor()
                c.execute("INSERT INTO orders (content) VALUES (?)", (json.dumps(order_data),))
                conn.commit()
                conn.close()
        else:
            visible_reply = ai_full_reply

        return jsonify({"reply": visible_reply})
    except Exception as e:
        return jsonify({"reply": "Με συγχωρείτε, είχαμε μια μικρή διακοπή. Μπορείτε να επαναλάβετε;"})

# --- Η ΔΙΑΔΡΟΜΗ ΓΙΑ ΤΟ ΙΣΤΟΡΙΚΟ (ΜΠΗΚΕ ΣΤΗ ΣΩΣΤΗ ΘΕΣΗ) ---
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

# --- ΤΕΛΕΥΤΑΙΑ ΓΡΑΜΜΗ ΤΟΥ ΑΡΧΕΙΟΥ ---
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)


