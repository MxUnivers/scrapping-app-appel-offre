"""
models/database.py
──────────────────
Couche d'accès MongoDB pour AO Tracker.
Collection principale : tenders
"""

import os, hashlib
from datetime import datetime, timedelta
from pymongo import MongoClient, DESCENDING
from pymongo.errors import DuplicateKeyError
from dotenv import load_dotenv

load_dotenv()

# ── Connexion ─────────────────────────────────────────────────────────────────

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB  = os.getenv("MONGO_DB",  "ao_tracker")

_client = None

def get_db():
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client[MONGO_DB]


# ── Init (index uniques + texte) ──────────────────────────────────────────────

def init_db():
    db  = get_db()
    col = db["tenders"]

    # Index unique sur hash → déduplication automatique
    col.create_index("hash", unique=True)

    # Index full-text sur titre + description
    col.create_index([("title", "text"), ("description", "text")])

    # Index de tri fréquents
    col.create_index([("score", DESCENDING)])
    col.create_index([("created_at", DESCENDING)])
    col.create_index("sector")
    col.create_index("status")
    col.create_index("deadline")

    print(f"[MongoDB] Connecté → {MONGO_URI}  |  base : {MONGO_DB} ✓")


# ── Écriture ──────────────────────────────────────────────────────────────────

def save_tender(tender: dict) -> bool:
    """
    Insère un AO.
    Retourne True si nouveau, False si doublon (hash déjà présent).
    """
    db  = get_db()
    col = db["tenders"]

    raw = (tender.get("title", "") + tender.get("source_url", "")).encode()
    h   = hashlib.md5(raw).hexdigest()

    doc = {
        "hash":         h,
        "title":        tender.get("title", ""),
        "source_url":   tender.get("source_url", ""),
        "sector":       tender.get("sector", "Autre"),
        "budget":       tender.get("budget", ""),
        "deadline":     tender.get("deadline", ""),
        "description":  tender.get("description", ""),
        "score":        int(tender.get("score", 0)),
        "score_reason": tender.get("score_reason", ""),
        "status":       tender.get("status", "Nouveau"),
        "raw_text":     tender.get("raw_text", ""),
        "created_at":   datetime.utcnow(),
        "updated_at":   datetime.utcnow(),
    }

    try:
        col.insert_one(doc)
        return True
    except DuplicateKeyError:
        return False


def update_status(tender_id: str, status: str):
    """Met à jour le statut d'un AO par son _id (string)."""
    from bson import objectid
    get_db()["tenders"].update_one(
        {"_id": objectid(tender_id)},
        {"$set": {"status": status, "updated_at": datetime.utcnow()}}
    )


# ── Lecture ───────────────────────────────────────────────────────────────────

def _serialize(doc: dict) -> dict:
    """Convertit ObjectId → str et datetime → str pour JSON/Jinja."""
    doc["id"] = str(doc.pop("_id"))
    for field in ("created_at", "updated_at"):
        if isinstance(doc.get(field), datetime):
            doc[field] = doc[field].strftime("%Y-%m-%d %H:%M")
    doc.pop("raw_text", None)
    return doc


def get_all_tenders(sector: str = "all", status: str = "all") -> list[dict]:
    """AO filtrés, triés score DESC puis date DESC."""
    query = {}
    if sector != "all":
        query["sector"] = sector
    if status != "all":
        query["status"] = status

    cursor = get_db()["tenders"].find(query).sort(
        [("score", DESCENDING), ("created_at", DESCENDING)]
    )
    return [_serialize(doc) for doc in cursor]


def get_tender_by_id(tender_id: str) -> dict | None:
    from bson import ObjectId
    doc = get_db()["tenders"].find_one({"_id": ObjectId(tender_id)})
    return _serialize(doc) if doc else None


def get_stats() -> dict:
    col = get_db()["tenders"]

    total    = col.count_documents({})
    nouveaux = col.count_documents({"status": "Nouveau"})

    today     = datetime.utcnow().strftime("%Y-%m-%d")
    in_7_days = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")
    urgents   = col.count_documents({"deadline": {"$gte": today, "$lte": in_7_days}})

    par_secteur = {
        r["_id"]: r["count"]
        for r in col.aggregate([
            {"$group": {"_id": "$sector", "count": {"$sum": 1}}},
            {"$sort":  {"count": DESCENDING}},
        ])
        if r["_id"]
    }

    score_res   = list(col.aggregate([
        {"$match": {"score": {"$gt": 0}}},
        {"$group": {"_id": None, "avg": {"$avg": "$score"}}},
    ]))
    score_moyen = round(score_res[0]["avg"], 1) if score_res else 0

    return {
        "total":       total,
        "nouveaux":    nouveaux,
        "urgents":     urgents,
        "par_secteur": par_secteur,
        "score_moyen": score_moyen,
        "top_secteur": max(par_secteur, key=par_secteur.get) if par_secteur else "—",
    }


def search_text(query: str) -> list[dict]:
    """Recherche full-text MongoDB sur titre + description."""
    cursor = get_db()["tenders"].find(
        {"$text": {"$search": query}},
        {"score": {"$meta": "textScore"}, "raw_text": 0}
    ).sort([("score", {"$meta": "textScore"})])
    return [_serialize(doc) for doc in cursor]