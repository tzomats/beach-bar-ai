from flask import Flask, render_template, request, jsonify
import requests
import json
import re

app = Flask(__name__)

API_KEY = "AIzaSyCu6l9azuUcex5x02gX8nCUr9ZIbq2JccM"
MODEL = "gemini-3-flash-preview"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

beach_orders_list = []



@app.route('/')
def index(): 
    # Εδώ καλούμε το dashboard.html που έφτιαξες στον φάκελο templates
    return render_template('dashboard.html', data_list=beach_orders_list)

@app.route('/client')
def client(): 
    return render_template('client.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_text = request.json.get('text', '')
    
    # Το μυστικό Prompt: Το AI πρέπει να απαντάει ευγενικά ΚΑΙ να βάζει το JSON κρυφά αν υπάρχει παραγγελία
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
        
        # Διαχωρισμός της απάντησης από το κρυφό JSON
        if "ORDER_JSON" in ai_full_reply:
            parts = ai_full_reply.split("ORDER_JSON")
            visible_reply = parts[0].strip()
            json_part = re.search(r'\{.*\}', parts[1], re.DOTALL)
            
            if json_part:
                order_data = json.loads(json_part.group())
                beach_orders_list.insert(0, order_data) # Στέλνουμε την παραγγελία στο Bar
        else:
            visible_reply = ai_full_reply

        return jsonify({"reply": visible_reply})
    except:
        return jsonify({"reply": "Με συγχωρείτε, είχαμε μια μικρή διακοπή. Μπορείτε να επαναλάβετε;"})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)