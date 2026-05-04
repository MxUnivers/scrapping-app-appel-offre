"""
models/prospect_data.py
────────────────────────
Modèle MongoDB pour la prospection email automatisée.

Collections :
  - prospects : chaque prospect généré + statut d'envoi
  - campaigns : regroupement de prospections par campagne
  - prospect_logs : historique des actions (envoi, ouverture, rebond)

INFOSOLUCES SARL — Abidjan, Côte d'Ivoire
"""

import os, hashlib
from datetime import datetime, timedelta
from typing import Optional
from bson import ObjectId
from pymongo import DESCENDING
from pymongo.errors import DuplicateKeyError
from models.database import get_db

# ── Statuts de prospection ────────────────────────────────────────────────────

PROSPECT_STATUS = {
    "DRAFT":     "Brouillon — email généré, pas encore envoyé",
    "SENT":      "Email envoyé avec succès",
    "OPENED":    "Email ouvert (si tracking activé)",
    "REPLIED":   "Le prospect a répondu",
    "FOLLOW_UP": "Relance envoyée",
    "BOUNCED":   "Email rejeté (adresse invalide)",
    "UNSUB":     "Désabonné / refus",
    "WON":       "Converti en client",
    "LOST":      "Perdu (concurrent, abandon, etc.)",
}

# ── Initialisation ────────────────────────────────────────────────────────────

def init_prospects():
    """Crée les index et collections nécessaires."""
    db = get_db()

    # Collection prospects
    col = db["prospects"]
    col.create_index("email_hash", unique=True)
    col.create_index([("created_at", DESCENDING)])
    col.create_index("status")
    col.create_index("source_tender_id")
    col.create_index("company_name")
    col.create_index("campaign_id")

    # Collection campaigns
    camp = db["campaigns"]
    camp.create_index([("created_at", DESCENDING)])

    # Collection prospect_logs
    logs = db["prospect_logs"]
    logs.create_index([("prospect_id", 1), ("created_at", -1)])
    logs.create_index("action")

    print(f"[Prospects] Index créés ✓")

    # Stats au démarrage
    total   = col.count_documents({})
    sent    = col.count_documents({"status": "SENT"})
    bounced = col.count_documents({"status": "BOUNCED"})
    print(f"[Prospects] {total} total · {sent} envoyés · {bounced} rebondis")


# ── CRUD Prospects ───────────────────────────────────────────────────────────

def create_prospect(
    company_name:     str,
    contact_email:    str,
    contact_name:     str          = "",
    contact_phone:    str          = "",
    source_tender_id: str          = "",
    source_url:       str          = "",
    subject:          str          = "",
    body_html:        str          = "",
    body_text:        str          = "",
    call_to_action:   str          = "",
    score:            int          = 0,
    confidence:       int          = 0,
    campaign_id:      str          = "",
    sector:           str          = "",
    notes:            str          = "",
) -> Optional[str]:
    """
    Crée un nouveau prospect en base.

    Returns:
        ID du prospect (string), ou None si doublon (même email déjà prospecté)
    """
    db  = get_db()
    col = db["prospects"]

    # Hash unique sur l'email + le mois (évite de re-prospecter trop souvent)
    month_key = datetime.utcnow().strftime("%Y-%m")
    raw       = f"{contact_email.lower().strip()}_{month_key}".encode()
    email_hash = hashlib.md5(raw).hexdigest()

    doc = {
        "email_hash":       email_hash,
        "company_name":     company_name.strip()[:200],
        "contact_email":    contact_email.lower().strip(),
        "contact_name":     contact_name.strip()[:100],
        "contact_phone":    contact_phone.strip()[:50],
        "source_tender_id": source_tender_id,
        "source_url":       source_url[:500],
        "subject":          subject[:200],
        "body_html":        body_html,
        "body_text":        body_text,
        "call_to_action":   call_to_action[:200],
        "score":            score,
        "confidence":       confidence,
        "campaign_id":      campaign_id,
        "sector":           sector[:100],
        "notes":            notes[:500],
        "status":           "DRAFT",
        "sent_at":          None,
        "opened_at":        None,
        "replied_at":       None,
        "follow_up_count":  0,
        "last_follow_up":   None,
        "tags":             [],
        "created_at":       datetime.utcnow(),
        "updated_at":       datetime.utcnow(),
    }

    try:
        result = col.insert_one(doc)
        return str(result.inserted_id)
    except DuplicateKeyError:
        return None


def get_prospect(prospect_id: str) -> Optional[dict]:
    """Récupère un prospect par son ID."""
    col = get_db()["prospects"]
    doc = col.find_one({"_id": ObjectId(prospect_id)})
    if doc:
        doc["id"] = str(doc.pop("_id"))
        _serialize_dates(doc)
    return doc


def get_prospects(
    status:  str     = "all",
    campaign: str    = "all",
    sector:  str     = "all",
    limit:   int     = 50,
    page:    int     = 1,
) -> dict:
    """
    Liste paginée des prospects.

    Returns:
        {"items": [...], "total": N, "page": P, "pages": N}
    """
    col = get_db()["prospects"]
    query = {}
    if status != "all":
        query["status"] = status
    if campaign != "all":
        query["campaign_id"] = campaign
    if sector != "all":
        query["sector"] = sector

    total = col.count_documents(query)
    pages = max(1, (total + limit - 1) // limit)
    skip  = max(0, (page - 1) * limit)

    cursor = col.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)

    items = []
    for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        _serialize_dates(doc)
        items.append(doc)

    return {"items": items, "total": total, "page": page, "pages": pages}


def update_prospect_status(prospect_id: str, status: str, **extra) -> bool:
    """
    Met à jour le statut d'un prospect.

    Args:
        prospect_id: ID MongoDB
        status: Nouveau statut (PROSPECT_STATUS)
        extra: Champs supplémentaires à définir (ex: opened_at=datetime)

    Returns:
        True si modifié, False si prospect introuvable
    """
    col = get_db()["prospects"]
    update = {"$set": {"status": status, "updated_at": datetime.utcnow()}}

    # Met à jour automatiquement les timestamps selon le statut
    now = datetime.utcnow()
    if status == "SENT" and extra.get("sent_at") is None:
        update["$set"]["sent_at"] = now
    if status == "OPENED":
        update["$set"]["opened_at"] = now
    if status == "REPLIED":
        update["$set"]["replied_at"] = now
    if status == "FOLLOW_UP":
        update["$set"]["follow_up_count"] = extra.get("follow_up_count", 1)
        update["$set"]["last_follow_up"] = now

    # Champs supplémentaires
    for k, v in extra.items():
        if k not in ("follow_up_count",):
            update["$set"][k] = v

    result = col.update_one({"_id": ObjectId(prospect_id)}, update)
    return result.modified_count > 0


def mark_prospect_sent(prospect_id: str) -> bool:
    """Raccourci pour marquer un prospect comme envoyé."""
    return update_prospect_status(prospect_id, "SENT", sent_at=datetime.utcnow())


def get_prospects_to_send(limit: int = 10) -> list[dict]:
    """
    Récupère les prospects en brouillon (DRAFT) prêts à être envoyés.
    Priorité : score décroissant, puis date de création croissante.
    """
    col = get_db()["prospects"]
    cursor = col.find({"status": "DRAFT"}).sort([
        ("score", DESCENDING),
        ("created_at", DESCENDING),
    ]).limit(limit)

    items = []
    for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        _serialize_dates(doc)
        items.append(doc)
    return items


def get_prospects_for_follow_up(days_since_last: int = 7, limit: int = 10) -> list[dict]:
    """
    Récupère les prospects SENT ou FOLLOW_UP qui n'ont pas répondu
    et n'ont pas été relancés depuis X jours.
    """
    col = get_db()["prospects"]
    cutoff = datetime.utcnow() - timedelta(days=days_since_last)

    cursor = col.find({
        "status": {"$in": ["SENT", "FOLLOW_UP"]},
        "replied_at": None,
        "$or": [
            {"last_follow_up": {"$lt": cutoff}},
            {"last_follow_up": None},
        ],
    }).sort("sent_at", DESCENDING).limit(limit)

    items = []
    for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        _serialize_dates(doc)
        items.append(doc)
    return items


# ── Statistiques ──────────────────────────────────────────────────────────────

def get_prospect_stats() -> dict:
    """Statistiques globales de prospection."""
    col = get_db()["prospects"]
    total = col.count_documents({})
    by_status = {}
    for status in PROSPECT_STATUS:
        by_status[status] = col.count_documents({"status": status})

    # Taux de conversion
    sent_count = sum(by_status.get(s, 0) for s in ("SENT", "OPENED", "REPLIED", "FOLLOW_UP", "WON"))
    won_count  = by_status.get("WON", 0)
    conversion_rate = round(won_count / sent_count * 100, 1) if sent_count > 0 else 0

    # Top secteurs prospectés
    pipeline = [{"$group": {"_id": "$sector", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 5}]
    top_sectors = {r["_id"]: r["count"] for r in col.aggregate(pipeline) if r["_id"]}

    return {
        "total":           total,
        "by_status":       by_status,
        "sent":            sent_count,
        "won":             won_count,
        "conversion_rate": conversion_rate,
        "top_sectors":     top_sectors,
    }


# ── Campaigns ────────────────────────────────────────────────────────────────

def create_campaign(name: str, description: str = "", target_sectors: list = None) -> str:
    """Crée une nouvelle campagne de prospection."""
    col = get_db()["campaigns"]
    doc = {
        "name":            name.strip()[:200],
        "description":     description.strip()[:500],
        "target_sectors":  target_sectors or [],
        "total_prospects": 0,
        "sent_count":      0,
        "reply_count":     0,
        "status":          "ACTIVE",
        "created_at":      datetime.utcnow(),
        "updated_at":      datetime.utcnow(),
    }
    result = col.insert_one(doc)
    return str(result.inserted_id)


def get_campaigns(limit: int = 20) -> list[dict]:
    """Liste les campagnes récentes."""
    col = get_db()["campaigns"]
    cursor = col.find().sort("created_at", DESCENDING).limit(limit)
    items = []
    for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        _serialize_dates(doc)
        items.append(doc)
    return items


# ── Logs ──────────────────────────────────────────────────────────────────────

def log_prospect_action(prospect_id: str, action: str, details: str = ""):
    """Enregistre une action sur un prospect (envoi, ouverture, etc.)."""
    col = get_db()["prospect_logs"]
    col.insert_one({
        "prospect_id": prospect_id,
        "action":      action,
        "details":     details[:500],
        "created_at":  datetime.utcnow(),
    })


# ── Helpers ───────────────────────────────────────────────────────────────────

def _serialize_dates(doc: dict):
    """Convertit les datetime en string pour JSON."""
    for field in ("created_at", "updated_at", "sent_at", "opened_at",
                  "replied_at", "last_follow_up"):
        if isinstance(doc.get(field), datetime):
            doc[field] = doc[field].isoformat()
    doc.pop("_id", None)


def get_prospects_by_source_tender(tender_id: str) -> list[dict]:
    """Récupère tous les prospects générés à partir d'un AO spécifique."""
    col = get_db()["prospects"]
    cursor = col.find({"source_tender_id": tender_id}).sort("created_at", DESCENDING)
    items = []
    for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        _serialize_dates(doc)
        items.append(doc)
    return items
