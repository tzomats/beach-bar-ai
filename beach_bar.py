from flask import Flask, render_template, request, jsonify
import requests
import json
import re
import sqlite3

app = Flask(__name__)

API_KEY = "AIzaSyCu6l9azuUcex5x02gX8nCUr9ZIbq2JccM"
MODEL = "gemini-3-flash-preview"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

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
    c.execute("SELECT id, content FROM orders ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    beach_orders_list = []
    for row in rows:
        order_data = json.loads(row[1])
        order_data['id'] = row[0]
        beach_orders_list.append(order_data)
    return render_template('dashboard.html', data_list=beach_orders_list)

@app.route('/client')
def client():
    # Παίρνει το u από το link (π.χ. ?u=5)
    u_number = request.args.get('u', 'Άγνωστη') 
    return render_template('client.html', umbrella=u_number)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_text = data.get('text', '')
    umbrella_fixed = data.get('umbrella', '??') # Το νούμερο που στείλαμε από το JavaScript
    
    system_instruction = (
        f"Είσαι ένας σερβιτόρος. Ο πελάτης είναι στην ΟΜΠΡΕΛΑ {umbrella_fixed}. "
        "Αν παραγγείλει, φτιάξε το JSON με 'umbrella_number': '" + umbrella_fixed + "' "
        "και 'products_list' με 'name' και 'qty'. Πρόσθεσε ORDER_JSON στο τέλος."
    )
    
    prompt = f"{system_instruction}\nΠελάτης: {user_text}"
    
    try:
        resp = requests.post(URL, json={"contents": [{"parts": [{"text": prompt}]}]})
        ai_reply = resp.json()['candidates'][0]['content']['parts'][0]['text']
        
        if "ORDER_JSON" in ai_reply:
            parts = ai_reply.split("ORDER_JSON")
            visible_reply = parts[0].strip()
            json_str = re.search(r'\{.*\}', parts[1], re.DOTALL).group()
            order_data = json.loads(json_str)
            
            # Σιγουρευόμαστε ότι το JSON έχει το σωστό νούμερο ομπρέλας
            order_data['umbrella_number'] = umbrella_fixed
            
            conn = sqlite3.connect('orders.db')
            c = conn.cursor()
            c.execute("INSERT INTO orders (content) VALUES (?)", (json.dumps(order_data),))
            conn.commit()
            conn.close()
        else:
            visible_reply = ai_reply

        return jsonify({"reply": visible_reply})
    except:
        return jsonify({"reply": "Σφάλμα σύνδεσης."})

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
