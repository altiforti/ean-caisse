# -*- coding: utf-8 -*-
import os
import sys
from dotenv import load_dotenv

# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# --- Configuration Sécurisée ---
load_dotenv()

AIRTABLE_PAT = os.environ.get("AIRTABLE_PAT")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME")
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY")

# Vérification de sécurité
if not all([AIRTABLE_PAT, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME, IMGBB_API_KEY]):
    missing_secrets = [secret for secret in ["AIRTABLE_PAT", "AIRTABLE_BASE_ID", "AIRTABLE_TABLE_NAME", "IMGBB_API_KEY"] if not os.environ.get(secret)]
    raise ValueError(f"Secrets manquants dans les variables d'environnement : {', '.join(missing_secrets)}")

from flask import Flask, send_from_directory, request, jsonify
from airtable import Airtable
import requests
import base64

# Noms des colonnes
EAN_COLUMN = "EAN"
PHOTO_COLUMN = "PHOTO"

# Initialisation d'Airtable
airtable = Airtable(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME, api_key=AIRTABLE_PAT)

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'une-cle-secrete-par-defaut-pour-le-dev')

# --- Fonctions d'aide Airtable ---
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
            PHOTO_COLUMN: [{'url': image_public_url}]
        }
        airtable.insert(record)
        return True, "Image ajoutée avec succès à Airtable"
    except Exception as e:
        print(f"Erreur Airtable (add_image_attachment): {e}")
        error_detail = str(e)
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            error_detail = e.response.text
        return False, f"Erreur lors de l'ajout de la pièce jointe à Airtable: {error_detail}"

# --- Fonction d'aide ImgBB ---
def upload_to_imgbb(image_data):
    """Uploads image data to ImgBB and returns the public URL."""
    try:
        imgbb_url = "https://api.imgbb.com/1/upload"
        payload = {
            "key": IMGBB_API_KEY,
            "image": base64.b64encode(image_data ),
        }
        response = requests.post(imgbb_url, payload)
        response.raise_for_status()
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

# --- Endpoints Flask ---
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
            return jsonify({"message": imgbb_result}), 500

        image_public_url = imgbb_result

        # 2. Add Image Attachment to Airtable using the ImgBB URL
        success_at, message_at = add_image_attachment_to_airtable(image_public_url)

        if success_at:
            return jsonify({"message": message_at}), 200
        else:
            print(f"Échec de l'ajout à Airtable: {message_at}")
            return jsonify({"message": message_at}), 500

    except Exception as e:
        print(f"Erreur inattendue dans handle_add_image: {e}")
        return jsonify({"message": f"Erreur serveur inattendue: {e}"}), 500

# --- Service des fichiers statiques ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)

    index_path = os.path.join(static_folder_path, 'index.html')
    if os.path.exists(index_path):
        return send_from_directory(static_folder_path, 'index.html')
    else:
        return "index.html not found", 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
