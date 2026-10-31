# -*- coding: utf-8 -*-
import os
import sys
import base64
from urllib.parse import quote

from dotenv import load_dotenv

# Nécessaire uniquement si le projet est organisé avec un dossier src.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# --- Configuration sécurisée ---
load_dotenv()

AIRTABLE_PAT = os.environ.get("AIRTABLE_PAT")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = os.environ.get("AIRTABLE_TABLE_NAME")

required_variables = {
    "AIRTABLE_PAT": AIRTABLE_PAT,
    "AIRTABLE_BASE_ID": AIRTABLE_BASE_ID,
    "AIRTABLE_TABLE_NAME": AIRTABLE_TABLE_NAME,
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

# Taille maximale documentée par l'API d'upload direct Airtable : 5 Mo par fichier.
MAX_DIRECT_ATTACHMENT_SIZE = 5 * 1024 * 1024

# Initialisation d'Airtable
airtable = Airtable(AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME, api_key=AIRTABLE_PAT)

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), "static"))
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "une-cle-secrete-par-defaut-pour-le-dev"
)


# --- Fonctions Airtable ---
def add_ean_to_airtable(ean):
    """Ajoute un code EAN dans Airtable."""
    try:
        airtable.insert({EAN_COLUMN: ean})
        return True, "EAN ajouté avec succès"
    except Exception as exc:
        print(f"Erreur Airtable (add_ean): {exc}")
        return False, "Erreur lors de l'ajout à Airtable."


def create_empty_photo_record():
    """Crée le futur enregistrement qui recevra la photo."""
    try:
        # Airtable accepte la création d'un enregistrement sans valeur,
        # puis l'API d'upload ajoute le fichier dans PHOTO.
        created_record = airtable.insert({})
        record_id = created_record.get("id")
        if not record_id:
            print("Airtable a créé un enregistrement sans identifiant :", created_record)
            return False, "Airtable n'a pas renvoyé l'identifiant de l'enregistrement."
        return True, record_id
    except Exception as exc:
        print(f"Erreur Airtable (création enregistrement photo): {exc}")
        return False, "Impossible de créer l'enregistrement de la photo dans Airtable."


def delete_record_silently(record_id):
    """Supprime le brouillon créé si la photo n'a pas pu être envoyée."""
    try:
        airtable.delete(record_id)
        print("Enregistrement photo incomplet supprimé.")
    except Exception as exc:
        # Il ne faut pas masquer l'erreur principale d'upload.
        print(f"Impossible de supprimer l'enregistrement incomplet {record_id}: {exc}")


def upload_attachment_to_airtable(record_id, image_data, original_filename, mimetype):
    """Charge l'image directement dans le champ PHOTO d'Airtable.

    L'API officielle Airtable accepte un fichier encodé Base64 de 5 Mo maximum.
    Cette méthode ne dépend d'aucun hébergeur intermédiaire tel qu'ImgBB.
    """
    if not image_data:
        return False, "La photo reçue est vide. Reprenez la photo puis réessayez."

    if len(image_data) > MAX_DIRECT_ATTACHMENT_SIZE:
        size_mb = len(image_data) / (1024 * 1024)
        print(f"Photo refusée car trop volumineuse : {size_mb:.2f} Mo")
        return False, (
            "La photo est trop volumineuse pour l'envoi direct à Airtable "
            f"({size_mb:.1f} Mo ; maximum 5 Mo)."
        )

    filename = original_filename or "couverture.jpg"
    content_type = mimetype or "image/jpeg"
    # Le nom de champ est encodé pour être sûr même s'il contient un espace ou un accent.
    field_name = quote(PHOTO_COLUMN, safe="")
    upload_url = (
        f"https://content.airtable.com/v0/{AIRTABLE_BASE_ID}/"
        f"{record_id}/{field_name}/uploadAttachment"
    )
    payload = {
        "contentType": content_type,
        "filename": filename,
        "file": base64.b64encode(image_data).decode("ascii"),
    }
    headers = {
        "Authorization": f"Bearer {AIRTABLE_PAT}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(upload_url, headers=headers, json=payload, timeout=(10, 60))
        if not response.ok:
            print(
                "Airtable a refusé l'upload direct "
                f"(HTTP {response.status_code}) : {response.text[:1000]}"
            )
            return False, "Airtable a refusé l'envoi de la photo. Réessayez."

        print("Photo envoyée directement dans Airtable avec succès.")
        return True, "Photo ajoutée avec succès à Airtable."
    except requests.exceptions.Timeout:
        print("Délai dépassé pendant l'envoi direct à Airtable.")
        return False, "L'envoi de la photo a dépassé le délai. Réessayez."
    except requests.exceptions.RequestException as exc:
        print(f"Erreur réseau pendant l'envoi direct à Airtable : {exc}")
        return False, "Impossible de joindre Airtable pour le moment. Réessayez."
    except Exception as exc:
        print(f"Erreur inattendue lors de l'upload direct Airtable : {exc}")
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
        return jsonify({"message": "Aucun fichier image reçu."}), 400

    file = request.files["image"]
    image_data = file.read()
    if not image_data:
        return jsonify({"message": "La photo reçue est vide."}), 400

    # L'API Airtable d'upload direct a besoin d'un identifiant d'enregistrement.
    success_record, record_result = create_empty_photo_record()
    if not success_record:
        return jsonify({"message": record_result}), 500

    record_id = record_result
    success_upload, message = upload_attachment_to_airtable(
        record_id=record_id,
        image_data=image_data,
        original_filename=file.filename,
        mimetype=file.mimetype,
    )

    if not success_upload:
        # Évite de laisser une ligne vide dans Airtable en cas d'échec de photo.
        delete_record_silently(record_id)
        return jsonify({"message": message}), 502

    return jsonify({"message": message}), 200


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
