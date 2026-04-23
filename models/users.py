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
        "label":    "Développement / ERP / Infrastructure IT / Développement Mobile / Développement d'application ",
        "keywords": ["développement", "application", "ERP", "logiciel", "web", "mobile","Application",
                     "plateforme", "système", "digitale", "infrastructure", "cloud"],
        "emails":   [
            "aymarbly559@gmail.com",
            "ben.konate@infosoluces.ci",
            "privat.kouadio@infosoluces.ci",
            "tidiane.dibate@infosoluces.ci",
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
            "aubin.kouame@infosoluces.ci",
        ],
    },
    "CAT3": {
        "label":    "Infogérance / Électronique / Réparation / Électricité",
        "keywords": ["infogérance", "réparation", "électricité", "électronique",
                     "antivirus", "maintenance", "énergie", "solaire", "fibre"],
        "emails":   [
            "marius.koffi@infosoluces.ci",
            "aubin.kouame@infosoluces.ci",
            "privat.kouadio@infosoluces.ci",
            "rebecca.hili@infosoluces.ci",
        ],
    },
    "CAT4": {
        "label":    "Vente matériel / Maintenance réseau / Support",
        "keywords": ["vente", "matériel", "fourniture", "ordinateur", "imprimante",
                     "maintenance réseau", "support technique", "LAN", "WAN"],
        "emails":   [
            "rebecca.hili@infosoluces.ci",
            "venus.danon@infosoluces.ci",
            "aubin.kouame@infosoluces.ci",
            "privat.kouadio@infosoluces.ci",
        ],
    },
}

# ── Utilisateurs par défaut (gardés pour compatibilité dashboard) ─────────────
DEFAULT_USERS = [
    {
        "username":     "direction",
        "full_name":    "Direction Générale",
        "email":        "aymarbly559@gmail.com",
        "role":         "admin",
        "sectors":      ["Développement","Réseau","Sécurité","Matériel","Maintenance","Autre"],
        "score_min":    40,
        "notify_email": True,
        "active":       True,
    },
    {
        "username":     "dev_team",
        "full_name":    "Équipe Développement",
        "email":        "tidiane.dibate@infosoluces.ci",        # CAT1
        "role":         "member",
        "sectors":      ["Développement"],
        "score_min":    50,
        "notify_email": True,
        "active":       True,
    },
    {
        "username":     "reseau_team",
        "full_name":    "Équipe Réseau & Infra",
        "email":        "pascal.ndri@infosoluces.ci",       # CAT2
        "role":         "member",
        "sectors":      ["Réseau","Matériel"],
        "score_min":    50,
        "notify_email": True,
        "active":       True,
    },
    {
        "username":     "commercial",
        "full_name":    "Équipe Commerciale",
        "email":        "aubin.kouame@infosoluces.ci",      # CAT1/2/3/4
        "role":         "member",
        "sectors":      ["Développement","Réseau","Sécurité","Matériel","Maintenance"],
        "score_min":    60,
        "notify_email": True,
        "active":       True,
    },
    {
        "username":     "securite_team",
        "full_name":    "Équipe Sécurité",
        "email":        "rebecca.hili@infosoluces.ci",      # CAT2/3/4
        "role":         "member",
        "sectors":      ["Sécurité"],
        "score_min":    50,
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
        col.insert_one({"username": username, "tender_id": tender_id,
                        "channel": channel, "sent_at": datetime.utcnow()})
        return True
    except DuplicateKeyError:
        return False


def was_notified(username: str, tender_id: str) -> bool:
    return get_db()["notifications"].count_documents(
        {"username": username, "tender_id": tender_id}
    ) > 0