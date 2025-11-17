# -*- coding: utf-8 -*-
import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, request, jsonify
from airtable import Airtable # Import Airtable library
import requests # For ImgBB API call
import base64 # To encode image data for ImgBB

# --- Configuration ---
# WARNING: Storing credentials directly in code is insecure. Use environment variables in production.
AIRTABLE_PAT = "patXSzDU4Ih7MfMAX.283ee2c7df921f93d37f2d305aee62a65670f6c0bf5cdd62e4075b3ec5fcbe01"
AIRTABLE_BASE_ID = "app0yP7LVfNexKtFF"
AIRTABLE_TABLE_NAME = "ventes caisse"
IMGBB_API_KEY = "ca16b79c433722d254b00ad3ef62142e" # Provided by user

# Column names from user's screenshot (adjust if needed)
EAN_COLUMN = "EAN"
PHOTO_COLUMN = "PHOTO" # Confirmed by user

# Initialize Airtable client
airtable = Airtable(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME, api_key=AIRTABLE_PAT)

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT'

# Removed temporary upload folder logic

# --- Airtable Helper Functions ---
def add_ean_to_airtable(ean):
    """Adds a record to Airtable with the EAN."""
    try:
        record = {
            EAN_COLUMN: ean,
        }
        airtable.insert(record)
        return True, "EAN ajouté avec succès"
    except Exception as e:
        print(f"Erreur Airtable (add_ean): {e}")
        return False, f"Erreur lors de l'ajout à Airtable: {e}"

def add_image_attachment_to_airtable(image_public_url):
    """Adds a record to Airtable with the image attachment URL."""
    try:
        record = {
            PHOTO_COLUMN: [{'url': image_public_url}] # Format for attachment field
        }
        airtable.insert(record)
        return True, "Image ajoutée avec succès à Airtable"
    except Exception as e:
        print(f"Erreur Airtable (add_image_attachment): {e}")
        error_detail = str(e)
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            error_detail = e.response.text
        return False, f"Erreur lors de l'ajout de la pièce jointe à Airtable: {error_detail}"

# --- ImgBB Helper Function ---
def upload_to_imgbb(image_data):
    """Uploads image data to ImgBB and returns the public URL."""
    try:
        imgbb_url = "https://api.imgbb.com/1/upload"
        payload = {
            "key": IMGBB_API_KEY,
            "image": base64.b64encode(image_data), # Send image data base64 encoded
            # Optional: Set expiration time if needed (e.g., "expiration": 600 for 10 minutes)
        }
        response = requests.post(imgbb_url, payload)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        result = response.json()
        if result.get("success"):
            image_url = result.get("data", {}).get("url")
            if image_url:
                print(f"Image uploadée sur ImgBB: {image_url}")
                return True, image_url
            else:
                return False, "URL non trouvée dans la réponse ImgBB"
        else:
            error_message = result.get("error", {}).get("message", "Erreur inconnue ImgBB")
            return False, f"Erreur ImgBB: {error_message}"
    except requests.exceptions.RequestException as e:
        print(f"Erreur réseau lors de l'upload ImgBB: {e}")
        return False, f"Erreur réseau ImgBB: {e}"
    except Exception as e:
        print(f"Erreur inattendue lors de l'upload ImgBB: {e}")
        return False, f"Erreur inattendue ImgBB: {e}"

# --- Flask Endpoints ---
@app.route('/add_barcode', methods=['POST'])
def handle_add_barcode():
    data = request.get_json()
    ean = data.get('ean')
    if not ean:
        return jsonify({"message": "EAN manquant"}), 400

    success, message = add_ean_to_airtable(ean)
    if success:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"message": message}), 500

@app.route('/add_image', methods=['POST'])
def handle_add_image():
    if 'image' not in request.files:
        return jsonify({"message": "Aucun fichier image reçu"}), 400

    file = request.files['image']
    image_data = file.read()

    try:
        # 1. Upload image to ImgBB
        success_imgbb, imgbb_result = upload_to_imgbb(image_data)

        if not success_imgbb:
            return jsonify({"message": imgbb_result}), 500 # Return ImgBB error

        image_public_url = imgbb_result

        # 2. Add Image Attachment to Airtable using the ImgBB URL
        success_at, message_at = add_image_attachment_to_airtable(image_public_url)

        if success_at:
            return jsonify({"message": message_at}), 200
        else:
            # Log the error from Airtable
            print(f"Échec de l'ajout à Airtable: {message_at}")
            return jsonify({"message": message_at}), 500

    except Exception as e:
        # Catch any other unexpected errors
        print(f"Erreur inattendue dans handle_add_image: {e}")
        return jsonify({"message": f"Erreur serveur inattendue: {e}"}), 500

# --- Static File Serving --- (Keep the existing serve function)
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    # Serve files from static folder directly if they exist
    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
         # Removed temp_uploads check
         return send_from_directory(static_folder_path, path)

    # Default to index.html
    index_path = os.path.join(static_folder_path, 'index.html')
    if os.path.exists(index_path):
        return send_from_directory(static_folder_path, 'index.html')
    else:
        return "index.html not found", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)

