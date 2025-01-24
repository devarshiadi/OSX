import os
import base64
import json
import google.generativeai as genai
from flask import Flask, request, jsonify, render_template, send_file
import sqlite3
from datetime import datetime
import csv
import io

app = Flask(__name__)

# Configure Gemini
genai.configure(api_key='AIzaSyDcYyq3w21iwipYn17wCAQo3AYWhUIGDSI')
model = genai.GenerativeModel(model_name="gemini-1.5-pro")

# Configure upload settings
UPLOAD_FOLDER = '/tmp/uploads'  # Change to /tmp for Vercel
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('business_cards.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS scanned_cards
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  company_name TEXT,
                  email TEXT,
                  contact_number TEXT,
                  website TEXT,
                  address TEXT,
                  scan_date TIMESTAMP)''')
    conn.commit()
    conn.close()

# Call init_db when the app starts
init_db()

def process_image(image_bytes):
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    prompt = """Extract info STRICTLY in this JSON format ONLY:
    {
      "businessCard": {
        "companyName": "",
        "email": "",
        "contactNumber": "",
        "website": "",
        "address": ""
      }
    }
    NO TEXT BEFORE/AFTER THE JSON. NO MARKDOWN. ONLY VALID JSON."""
    
    try:
        response = model.generate_content(
            [
                {
                    "mime_type": "image/jpeg",
                    "data": base64_image
                },
                prompt
            ]
        )
        # Clean and parse the response
        return clean_response(response.text)
    except Exception as e:
        raise Exception(f"Error processing image: {str(e)}")

def clean_response(response_text):
    """Clean the response text to extract pure JSON."""
    # Remove markdown code blocks
    clean_text = response_text.replace('```json', '').replace('```', '').strip()
    
    try:
        # Parse and return clean JSON
        json_data = json.loads(clean_text)
        
        # Clean up email and contact number fields (remove duplicates and format)
        if 'businessCard' in json_data:
            card = json_data['businessCard']
            
            # Clean email field
            if card.get('email'):
                emails = [e.strip() for e in card['email'].replace('\\n', ',').split(',')]
                card['email'] = ', '.join(list(dict.fromkeys(emails)))  # Remove duplicates
            
            # Clean contact number field
            if card.get('contactNumber'):
                numbers = [n.strip() for n in card['contactNumber'].split(',')]
                card['contactNumber'] = ', '.join(list(dict.fromkeys(numbers)))  # Remove duplicates
            
            # Clean address field
            if card.get('address'):
                card['address'] = card['address'].replace('\\n', ' ').strip()
                
        return json_data
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse JSON response: {str(e)}")

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/process_card', methods=['POST'])
def process_business_card():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        # Read file bytes directly from the uploaded file
        image_bytes = file.read()
        
        # Process the image and get clean JSON response
        result = process_image(image_bytes)
        
        # Store the result in SQLite database
        if 'businessCard' in result:
            card = result['businessCard']
            conn = sqlite3.connect('business_cards.db')
            c = conn.cursor()
            c.execute('''INSERT INTO scanned_cards 
                        (company_name, email, contact_number, website, address, scan_date)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                     (card.get('companyName', ''),
                      card.get('email', ''),
                      card.get('contactNumber', ''),
                      card.get('website', ''),
                      card.get('address', ''),
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            conn.close()
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/history', methods=['GET'])
def get_history():
    try:
        conn = sqlite3.connect('business_cards.db')
        c = conn.cursor()
        c.execute('SELECT * FROM scanned_cards ORDER BY scan_date DESC')
        rows = c.fetchall()
        history = []
        for row in rows:
            history.append({
                'id': row[0],
                'companyName': row[1],
                'email': row[2],
                'contactNumber': row[3],
                'website': row[4],
                'address': row[5],
                'scanDate': row[6]
            })
        conn.close()
        return jsonify(history), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export_csv', methods=['GET'])
def export_csv():
    try:
        conn = sqlite3.connect('business_cards.db')
        c = conn.cursor()
        c.execute('SELECT * FROM scanned_cards ORDER BY scan_date DESC')
        rows = c.fetchall()
        conn.close()

        # Create CSV in memory
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', 'Company Name', 'Email', 'Contact Number', 'Website', 'Address', 'Scan Date'])
        cw.writerows(rows)

        output = io.BytesIO()
        output.write(si.getvalue().encode('utf-8'))
        output.seek(0)
        
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name='business_cards_history.csv'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860)
