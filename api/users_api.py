"""
api/users_api.py — Routes API pour la gestion des utilisateurs/équipes
════════════════════════════════════════════════════════════════════════
Permet :
- CRUD complet des membres de l'équipe
- Attribution des catégories (CAT1-CAT4)
- Activation/désactivation
- Gestion des secteurs et score minimum
"""
from flask import Blueprint, jsonify, request
from datetime import datetime
from bson import ObjectId
from models.database import get_db
from models.users import CATEGORIES, DEFAULT_USERS

users_bp = Blueprint("users_api", __name__)


def _serialize(user: dict) -> dict:
    """Sérialise un doc MongoDB pour JSON."""
    user["id"] = str(user.pop("_id"))
    for f in ("created_at", "updated_at"):
        if isinstance(user.get(f), datetime):
            user[f] = user[f].isoformat()
    return user


@users_bp.route("/api/users", methods=["GET"])
def list_users():
    """Liste tous les utilisateurs avec leur catégorie."""
    try:
        db = get_db()
        col = db["users"]
        users = []
        for doc in col.find().sort("full_name", 1):
            users.append(_serialize(doc))
        return jsonify({"items": users, "total": len(users)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@users_bp.route("/api/users", methods=["POST"])
def create_user():
    """Crée un nouvel utilisateur/équipier."""
    try:
        data = request.get_json() or {}
        required = ["full_name", "email"]
        for r in required:
            if not data.get(r):
                return jsonify({"error": f"Le champ '{r}' est requis"}), 400

        doc = {
            "username":     data.get("username", data["email"].split("@")[0]),
            "full_name":    data["full_name"].strip(),
            "email":        data["email"].strip().lower(),
            "role":         data.get("role", "member"),
            "categories":   data.get("categories", ["CAT1"]),
            "sectors":      data.get("sectors", []),
            "score_min":    data.get("score_min", 40),
            "notify_email": data.get("notify_email", True),
            "active":       data.get("active", True),
            "phone":        data.get("phone", ""),
            "title":        data.get("title", ""),  # Poste/fonction
            "created_at":   datetime.utcnow(),
            "updated_at":   datetime.utcnow(),
        }

        from pymongo.errors import DuplicateKeyError
        db = get_db()
        col = db["users"]
        col.create_index("username", unique=True)
        col.create_index("email", unique=True)

        result = col.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        doc.pop("_id", None)

        return jsonify({"status": "ok", "user": _serialize(doc)}), 201
    except DuplicateKeyError:
        return jsonify({"error": "Un utilisateur avec cet email ou ce nom existe déjà"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@users_bp.route("/api/users/<user_id>", methods=["GET"])
def get_user(user_id):
    """Détail d'un utilisateur."""
    try:
        db = get_db()
        doc = db["users"].find_one({"_id": ObjectId(user_id)})
        if not doc:
            return jsonify({"error": "Utilisateur introuvable"}), 404
        return jsonify(_serialize(doc))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@users_bp.route("/api/users/<user_id>", methods=["PATCH"])
def update_user(user_id):
    """Met à jour un utilisateur."""
    try:
        data = request.get_json() or {}
        db = get_db()
        col = db["users"]

        # Champs autorisés à la modification
        allowed = ("full_name", "email", "role", "categories", "sectors",
                   "score_min", "notify_email", "active", "phone", "title", "username")
        update = {}
        for key in allowed:
            if key in data:
                update[key] = data[key]

        if not update:
            return jsonify({"error": "Aucune donnée à mettre à jour"}), 400

        update["updated_at"] = datetime.utcnow()
        result = col.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update}
        )
        if result.matched_count == 0:
            return jsonify({"error": "Utilisateur introuvable"}), 404

        doc = col.find_one({"_id": ObjectId(user_id)})
        return jsonify({"status": "ok", "user": _serialize(doc)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@users_bp.route("/api/users/<user_id>", methods=["DELETE"])
def delete_user(user_id):
    """Supprime (désactive) un utilisateur."""
    try:
        db = get_db()
        result = db["users"].update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"active": False, "updated_at": datetime.utcnow()}}
        )
        if result.matched_count == 0:
            return jsonify({"error": "Utilisateur introuvable"}), 404
        return jsonify({"status": "ok", "message": "Utilisateur désactivé"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@users_bp.route("/api/users/categories", methods=["GET"])
def list_categories():
    """Retourne la liste des catégories disponibles."""
    cats = []
    for cid, cat in CATEGORIES.items():
        cats.append({
            "id": cid,
            "label": cat["label"],
            "emails": cat.get("emails", []),
        })
    return jsonify({"items": cats, "total": len(cats)})


@users_bp.route("/api/users/roles", methods=["GET"])
def list_roles():
    """Retourne les rôles disponibles."""
    return jsonify({
        "items": [
            {"id": "admin", "label": "Administrateur"},
            {"id": "member", "label": "Membre équipe"},
            {"id": "viewer", "label": "Lecteur seul"},
        ]
    })
