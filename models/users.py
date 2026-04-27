"""
models/users.py — 4 catégories réelles INFOSOLUCES
"""
import os
from datetime import datetime
from pymongo.errors import DuplicateKeyError
from models.database import get_db

# ── 4 Catégories de routage ───────────────────────────────────────────────────

CATEGORIES = {
    "CAT1": {
        "label":    "Développement / ERP / Infrastructure IT / Mobile / Application",
        "keywords": ["développement", "application", "ERP", "logiciel", "web", "mobile",
                     "plateforme", "système", "digitale", "infrastructure", "cloud"],
        "emails":   [
            "aymarbly559@gmail.com",
            "ben.konate@infosoluces.ci",
            "privat.kouadio@infosoluces.ci",
            "tidiane.diabate@infosoluces.ci",
            "aubin.kouame@infosoluces.ci",
        ],
    },
    "CAT2": {
        "label":    "Réseau / Cloud / Sécurité / Marchés IT",
        "keywords": ["réseau", "cybersécurité", "sécurité", "cloud", "marché IT",
                     "infrastructure réseau", "firewall", "VPN", "datacenter"],
        "emails":   [
            "pascal.ndri@infosoluces.ci",
            "privat.kouadio@infosoluces.ci",
            "rebecca.hili@infosoluces.ci",
            "marius.koffi@infosoluces.ci",
            "aubin.kouame@infosoluces.ci",
        ],
    },
    "CAT3": {
        "label":    "Infogérance / Électronique / Réparation / Électricité",
        "keywords": ["infogérance", "réparation", "électricité", "électronique",
                     "surveillance","sécurité","caméra", "camera","contrôle","accès","télésurveillance",
                     "antivirus", "maintenance", "énergie", "solaire", "fibre","matériel","electricité"],
        "emails":   [
            "marius.koffi@infosoluces.ci",
            "aubin.kouame@infosoluces.ci",
            "privat.kouadio@infosoluces.ci",
            "dorsaille.any@infosoluces.ci",
            "venus.danon@infosoluces.ci",
            "aubin.kouame@infosoluces.ci",
        ],
    },
    "CAT4": {
        "label":    "Vente matériel / Maintenance réseau / Support",
        "keywords": ["vente", "matériel", "fourniture", "ordinateur", "imprimante",
                     "maintenance réseau", "support technique", "LAN", "WAN","WLAN"],
        "emails":   [
            "marius.koffi@infosoluces.ci",
            "aubin.kouame@infosoluces.ci",
            "privat.kouadio@infosoluces.ci",
            "dorsaille.any@infosoluces.ci",
            "venus.danon@infosoluces.ci",
            "aubin.kouame@infosoluces.ci",
        ],
    },
}

# ── Utilisateurs par défaut ───────────────────────────────────────────────────

DEFAULT_USERS = [

    # ── Direction Générale ────────────────────────────────────────────────────
    {
        "username":     "direction",
        "full_name":    "Aymar Bly",
        "email":        "aymarbly559@gmail.com",
        "role":         "admin",
        "categories":   ["CAT1", "CAT2", "CAT3", "CAT4"],
        "sectors":      ["Développement", "Réseau", "Sécurité", "Matériel",
                         "Maintenance", "Électricité", "Veille", "Autre"],
        "score_min":    40,
        "notify_email": True,
        "active":       True,
    },

    # ── Équipe Développement ──────────────────────────────────────────────────
    {
        "username":     "tidiane_diabate",
        "full_name":    "Tidiane Diabaté",
        "email":        "tidiane.diabate@infosoluces.ci",
        "role":         "member",
        "categories":   ["CAT1"],
        "sectors":      ["Développement"],
        "score_min":    50,
        "notify_email": True,
        "active":       True,
    },
    {
        "username":     "ben_konate",
        "full_name":    "Ben Konaté",
        "email":        "ben.konate@infosoluces.ci",
        "role":         "member",
        "categories":   ["CAT1"],
        "sectors":      ["Développement"],
        "score_min":    50,
        "notify_email": True,
        "active":       True,
    },

    # ── Équipe Réseau & Infrastructure ────────────────────────────────────────
    {
        "username":     "pascal_ndri",
        "full_name":    "Pascal Ndri",
        "email":        "pascal.ndri@infosoluces.ci",
        "role":         "member",
        "categories":   ["CAT2"],
        "sectors":      ["Réseau", "Sécurité", "Matériel"],
        "score_min":    50,
        "notify_email": True,
        "active":       True,
    },
    {
        "username":     "marius_koffi",
        "full_name":    "Marius Koffi",
        "email":        "marius.koffi@infosoluces.ci",
        "role":         "member",
        "categories":   ["CAT2", "CAT3"],
        "sectors":      ["Réseau", "Infogérance", "Électricité"],
        "score_min":    50,
        "notify_email": True,
        "active":       True,
    },

    # ── Équipe Sécurité ───────────────────────────────────────────────────────
    {
        "username":     "rebecca_hili",
        "full_name":    "Rebecca Hili",
        "email":        "rebecca.hili@infosoluces.ci",
        "role":         "member",
        "categories":   ["CAT2", "CAT3", "CAT4"],
        "sectors":      ["Sécurité", "Réseau", "Matériel"],
        "score_min":    50,
        "notify_email": True,
        "active":       True,
    },

    # ── Équipe Commerciale ────────────────────────────────────────────────────
    {
        "username":     "aubin_kouame",
        "full_name":    "Aubin Kouamé",
        "email":        "aubin.kouame@infosoluces.ci",
        "role":         "member",
        "categories":   ["CAT1", "CAT2", "CAT3", "CAT4"],
        "sectors":      ["Développement", "Réseau", "Sécurité", "Matériel", "Maintenance"],
        "score_min":    60,
        "notify_email": True,
        "active":       True,
    },
    {
        "username":     "venus_danon",
        "full_name":    "Vénus Danon",
        "email":        "venus.danon@infosoluces.ci",
        "role":         "member",
        "categories":   ["CAT4"],
        "sectors":      ["Matériel", "Maintenance", "Support"],
        "score_min":    50,
        "notify_email": True,
        "active":       True,
    },

    # ── Direction Technique ───────────────────────────────────────────────────
    {
        "username":     "privat_kouadio",
        "full_name":    "Privat Kouadio",
        "email":        "privat.kouadio@infosoluces.ci",
        "role":         "admin",
        "categories":   ["CAT1", "CAT2", "CAT3", "CAT4"],
        "sectors":      ["Développement", "Réseau", "Sécurité", "Matériel",
                         "Maintenance", "Électricité"],
        "score_min":    40,
        "notify_email": True,
        "active":       True,
    },
]


def init_users():
    db  = get_db()
    col = db["users"]
    col.create_index("username", unique=True)
    col.create_index("email",    unique=True)
    inserted = 0
    for user in DEFAULT_USERS:
        try:
            user["created_at"] = datetime.utcnow()
            col.insert_one(user.copy())
            inserted += 1
        except DuplicateKeyError:
            pass
    print(f"[Users] {inserted} créé(s) | total: {col.count_documents({})}")
    _print_summary()


def _print_summary():
    """Affiche le récapitulatif des utilisateurs au démarrage."""
    print("\n" + "=" * 65)
    print("👥  UTILISATEURS INFOSOLUCES")
    print("=" * 65)
    print(f"{'Nom':<25} {'Email':<35} {'Rôle':<8} {'Cats'}")
    print("-" * 65)
    for u in DEFAULT_USERS:
        cats = ", ".join(u.get("categories", []))
        print(f"{u['full_name']:<25} {u['email']:<35} {u['role']:<8} {cats}")
    print("=" * 65 + "\n")


def get_all_users() -> list[dict]:
    users = []
    for u in get_db()["users"].find({"active": True}):
        u["id"] = str(u.pop("_id"))
        u.pop("created_at", None)
        users.append(u)
    return users


def get_users_for_tender(sector: str, score: int) -> list[dict]:
    return [
        u for u in get_all_users()
        if sector in u.get("sectors", [])
        and score >= u.get("score_min", 0)
        and u.get("notify_email")
    ]


def log_notification(username: str, tender_id: str, channel: str = "email"):
    db  = get_db()
    col = db["notifications"]
    col.create_index([("username", 1), ("tender_id", 1)], unique=True)
    try:
        col.insert_one({
            "username":  username,
            "tender_id": tender_id,
            "channel":   channel,
            "sent_at":   datetime.utcnow()
        })
        return True
    except DuplicateKeyError:
        return False


def was_notified(username: str, tender_id: str) -> bool:
    return get_db()["notifications"].count_documents(
        {"username": username, "tender_id": tender_id}
    ) > 0