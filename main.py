# -*- coding: utf-8 -*-
import os
import sys

from dotenv import load_dotenv

# NÃ©cessaire uniquement si le projet est organisÃ© avec un dossier src.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# --- Configuration sÃ©curisÃ©e ---
load_dotenv()

AIRTABLE_PAT = os.environ.get("AIRTABLE_PAT")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME")
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY")

required_variables = {
    "AIRTABLE_PAT": AIRTABLE_PAT,
    "AIRTABLE_BASE_ID": AIRTABLE_BASE_ID,
    "AIRTABLE_TABLE_NAME": AIRTABLE_TABLE_NAME,
    "IMGBB_API_KEY": IMGBB_API_KEY,
}
missing_secrets = [name for name, value in required_variables.items() if not value]
if missing_secrets:
    raise ValueError(
        "Variables d'environnement manquantes : " + ", ".join(missing_secrets)
    )

from flask import Flask, send_from_directory, request, jsonify
from airtable import Airtable
import requests

# Noms des colonnes Airtable
EAN_COLUMN = "EAN"
PHOTO_COLUMN = "PHOTO"

# Initialisation d'Airtable
airtable = Airtable(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME, api_key=AIRTABLE_PAT)

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), "static"))
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "une-cle-secrete-par-defaut-pour-le-dev")


# --- Fonctions Airtable ---
def add_ean_to_airtable(ean):
    """Ajoute un code EAN dans Airtable."""
    try:
        airtable.insert({EAN_COLUMN: ean})
        return True, "EAN ajoutÃ© avec succÃ¨s"
    except Exception as exc:
        print(f"Erreur Airtable (add_ean): {exc}")
        return False, "Erreur lors de l'ajout Ã  Airtable."


def add_image_attachment_to_airtable(image_public_url):
    """Ajoute une piÃ¨ce jointe Ã  Airtable Ã  partir de son URL publique."""
    try:
        airtable.insert({PHOTO_COLUMN: [{"url": image_public_url}]})
        return True, "Image ajoutÃ©e avec succÃ¨s Ã  Airtable"
    except Exception as exc:
        error_detail = str(exc)
        if hasattr(exc, "response") and getattr(exc.response, "text", None):
            error_detail = exc.response.text
        print(f"Erreur Airtable (add_image_attachment): {error_detail}")
        return False, "Erreur lors de l'ajout de la photo Ã  Airtable."


# --- Fonction ImgBB ---
def upload_to_imgbb(image_data, original_filename, mimetype):
    """Envoie le fichier image Ã  ImgBB et renvoie son URL publique."""
    if not image_data:
        return False, "La photo reÃ§ue est vide. Reprenez la photo puis rÃ©essayez."

    imgbb_url = "https://api.imgbb.com/1/upload"
    filename = original_filename or "couverture.jpg"
    content_type = mimetype or "image/jpeg"

    try:
        # ImgBB accepte un fichier binaire en multipart/form-data.
        # La clÃ© reste exclusivement dans les variables d'environnement Render.
        response = requests.post(
            imgbb_url,
            data={"key": IMGBB_API_KEY.strip()},
            files={"image": (filename, image_data, content_type)},
            timeout=30,
        )

        # Conserver le vrai message ImgBB dans Render Logs, sans jamais Ã©crire la clÃ© API.
        try:
            result = response.json()
        except ValueError:
            result = {}

        if not response.ok or not result.get("success"):
            api_error = result.get("error", {}) if isinstance(result, dict) else {}
            error_message = api_error.get("message") or response.text[:1000] or "RÃ©ponse vide"
            error_code = api_error.get("code", "inconnu")
            print(
                "ImgBB a refusÃ© l'envoi "
                f"(HTTP {response.status_code}, code {error_code}) : {error_message}"
            )
            return False, (
                "ImgBB a refusÃ© la photo. VÃ©rifiez la clÃ© ImgBB dans Render, "
                "puis rÃ©essayez."
            )

        image_url = result.get("data", {}).get("url")
        if not image_url:
            print("RÃ©ponse ImgBB sans URL d'image :", result)
            return False, "ImgBB n'a pas renvoyÃ© d'URL pour cette photo."

        print("Image envoyÃ©e avec succÃ¨s Ã  ImgBB.")
        return True, image_url

    except requests.exceptions.Timeout:
        print("DÃ©lai dÃ©passÃ© pendant l'envoi Ã  ImgBB.")
        return False, "L'envoi de la photo a dÃ©passÃ© le dÃ©lai. RÃ©essayez."
    except requests.exceptions.RequestException as exc:
        print(f"Erreur rÃ©seau lors de l'envoi Ã  ImgBB : {exc}")
        return False, "Impossible de joindre ImgBB pour le moment. RÃ©essayez."
    except Exception as exc:
        print(f"Erreur inattendue lors de l'envoi Ã  ImgBB : {exc}")
        return False, "Erreur inattendue lors de l'envoi de la photo."


# --- Endpoints Flask ---
@app.route("/add_barcode", methods=["POST"])
def handle_add_barcode():
    data = request.get_json(silent=True) or {}
    ean = data.get("ean")

    if not ean:
        return jsonify({"message": "EAN manquant"}), 400

    success, message = add_ean_to_airtable(ean)
    return jsonify({"message": message}), 200 if success else 500


@app.route("/add_image", methods=["POST"])
def handle_add_image():
    if "image" not in request.files:
        return jsonify({"message": "Aucun fichier image reÃ§u."}), 400

    file = request.files["image"]
    if not file or not file.filename:
        return jsonify({"message": "Le fichier photo est manquant."}), 400

    image_data = file.read()
    if not image_data:
        return jsonify({"message": "La photo reÃ§ue est vide."}), 400

    success_imgbb, imgbb_result = upload_to_imgbb(
        image_data=image_data,
        original_filename=file.filename,
        mimetype=file.mimetype,
    )
    if not success_imgbb:
        return jsonify({"message": imgbb_result}), 502

    success_at, message_at = add_image_attachment_to_airtable(imgbb_result)
    if not success_at:
        return jsonify({"message": message_at}), 500

    return jsonify({"message": message_at}), 200


# --- Fichiers statiques ---
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    if path and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)

    index_path = os.path.join(static_folder_path, "index.html")
    if os.path.exists(index_path):
        return send_from_directory(static_folder_path, "index.html")
    return "index.html not found", 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
