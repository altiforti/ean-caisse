# -*- coding: utf-8 -*-
import os
import sys
from dotenv import load_dotenv # Importez dotenv

# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# --- Configuration Sécurisée ---
# Charge les variables d'environnement depuis un fichier .env pour le développement local
# Sur Render, ces variables seront fournies par le dashboard
load_dotenv()

# Récupère les secrets depuis les variables d'environnement
AIRTABLE_PAT = os.environ.get("AIRTABLE_PAT")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME")
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY")

# Vérification de sécurité : s'assurer que les variables sont bien définies
if not all([AIRTABLE_PAT, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME, IMGBB_API_KEY]):
    missing_secrets = [secret for secret in ["AIRTABLE_PAT", "AIRTABLE_BASE_ID", "AIRTABLE_TABLE_NAME", "IMGBB_API_KEY"] if not os.environ.get(secret)]
    raise ValueError(f"Secrets manquants dans les variables d'environnement : {', '.join(missing_secrets)}")

# --- Le reste de votre code ---

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
    try:
        airtable.insert({EAN_COLUMN: ean})
        return True, "EAN ajouté avec succès"
    except Exception as e:
        print(f"Erreur Airtable (add_ean): {e}")
        return False, f"Erreur lors de l'ajout à Airtable: {e}"

def add_image_attachment_to_airtable(image_public_url):
    try:
        records = airtable.get_all(formula=f"AND({{PHOTO}} = '', {{EAN}} != '')")
        if records:
            record_id = records[0]['id']
            airtable.update(record_id, {PHOTO_COLUMN: [{'url': image_public_url}]})
            return True, "Image liée à l'enregistrement existant"
        else:
            airtable.insert({PHOTO_COLUMN: [{'url': image_public_url}]})
            return True, "Nouvel enregistrement créé avec l'image"
    except Exception as e:
        print(f"Erreur Airtable (add_image_attachment): {e}")
        return False, f"Erreur lors de l'ajout de la pièce jointe à Airtable: {e}"

# --- Fonction d'aide ImgBB ---
def upload_to_imgbb(image_data):
    try:
        response = requests.post(
            "https://api.imgbb.com/1/upload",
            params={"key": IMGBB_API_KEY},
            files={"image": image_data}
         )
        response.raise_for_status()
        result = response.json()
        if result.get("success"):
            image_url = result.get("data", {}).get("url")
            return True, image_url
        else:
            return False, result.get("error", {}).get("message", "Erreur inconnue ImgBB")
    except requests.exceptions.RequestException as e:
        return False, f"Erreur réseau ImgBB: {e}"

# --- Endpoints Flask ---
@app.route('/add_barcode', methods=['POST'])
def handle_add_barcode():
    ean = request.json.get('ean')
    if not ean:
        return jsonify({"message": "EAN manquant"}), 400
    success, message = add_ean_to_airtable(ean)
    return jsonify({"message": message}), 200 if success else 500

@app.route('/add_image', methods=['POST'])
def handle_add_image():
    if 'image' not in request.files:
        return jsonify({"message": "Aucun fichier image reçu"}), 400
    
    image_data = request.files['image'].read()
    success_imgbb, imgbb_result = upload_to_imgbb(image_data)
    
    if not success_imgbb:
        return jsonify({"message": imgbb_result}), 500

    success_at, message_at = add_image_attachment_to_airtable(imgbb_result)
    return jsonify({"message": message_at}), 200 if success_at else 500

# --- Service des fichiers statiques ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
