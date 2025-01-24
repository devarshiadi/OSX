import os
import base64
import json
import google.generativeai as genai
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# Configure Gemini
genai.configure(api_key='AIzaSyDcYyq3w21iwipYn17wCAQo3AYWhUIGDSI')
model = genai.GenerativeModel(model_name="gemini-1.5-pro")

# Configure upload settings
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/process_card', methods=['POST'])
def process_business_card():
    # Check if file is present in request
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed. Use jpg, jpeg, or png'}), 400
    
    try:
        # Read file bytes directly from the uploaded file
        image_bytes = file.read()
        
        # Process the image and get clean JSON response
        result = process_image(image_bytes)
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    app.run(debug=True, port=7860)