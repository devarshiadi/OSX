import os
import base64
import json
import google.generativeai as genai
from flask import Flask, request, jsonify, render_template, send_file
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

# In-memory storage for business cards
business_cards = []

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
        
        # Store the result in memory
        if 'businessCard' in result:
            card = result['businessCard']
            business_cards.append({
                'id': len(business_cards) + 1,
                'companyName': card.get('companyName', ''),
                'email': card.get('email', ''),
                'contactNumber': card.get('contactNumber', ''),
                'website': card.get('website', ''),
                'address': card.get('address', ''),
                'scanDate': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/history', methods=['GET'])
def get_history():
    try:
        return jsonify(business_cards), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export_csv', methods=['GET'])
def export_csv():
    try:
        # Create CSV in memory
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow(['ID', 'Company Name', 'Email', 'Contact Number', 'Website', 'Address', 'Scan Date'])
        
        for card in business_cards:
            cw.writerow([
                card['id'],
                card['companyName'],
                card['email'],
                card['contactNumber'],
                card['website'],
                card['address'],
                card['scanDate']
            ])

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
