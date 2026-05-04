from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from flask_cors import CORS
from scrapers.web_search import search_tenders
from models.database import init_db, get_db, get_all_tenders, get_stats , update_status
from models.users         import init_users, get_all_users
from utils.notifier       import notify_new_tenders, notify_urgent_tenders
from models.prospect_data import (
    init_prospects, create_prospect, get_prospects, get_prospect,
    get_prospect_stats, get_prospects_to_send, get_prospects_for_follow_up,
    update_prospect_status, mark_prospect_sent, log_prospect_action,
    PROSPECT_STATUS, get_campaigns, create_campaign,
)
from utils.llm_prospect   import generate_prospect_email, score_prospect_quality
from utils.doc_analyzer   import analyze_document, extract_text_from_file, send_document_report, DEFAULT_DOC_PROMPT
from models.users         import CATEGORIES
import atexit
import os
import random
import datetime as dt

app = Flask(__name__)
CORS(app)
scheduler = BackgroundScheduler()

# ══════════════════════════════════════════════════════════════════════════════
#  LOGGER DE REQUÊTES — Affiche chaque appel API dans la console
# ══════════════════════════════════════════════════════════════════════════════

@app.before_request
def log_request():
    """Log chaque requête API avec timestamp, méthode, chemin et paramètres."""
    if request.path.startswith("/api/"):
        ts = dt.datetime.now().strftime("%H:%M:%S")
        method = request.method
        path = request.path
        args = dict(request.args)
        if request.is_json and request.method in ("POST", "PATCH"):
            body = request.get_json(silent=True) or {}
            # Masquer les données sensibles
            safe_body = {k: (v[:20] + "..." if isinstance(v, str) and len(v) > 20 else v) for k, v in body.items()}
            print(f"  [API] {ts} {method} {path} ↴")
            print(f"        ⇢ args: {args}" if args else "", end="")
            print(f"        ⇢ body: {safe_body}" if safe_body else "")
        else:
            print(f"  [API] {ts} {method} {path}  args: {args}" if args else f"  [API] {ts} {method} {path}")


@app.after_request
def log_response(response):
    """Log le statut de la réponse."""
    if request.path.startswith("/api/"):
        ts = dt.datetime.now().strftime("%H:%M:%S")
        status = response.status_code
        icon = "✅" if status < 400 else ("⚠️" if status < 500 else "❌")
        print(f"  [API] {ts} {icon} {status}")
    return response


# ══════════════════════════════════════════════════════════════════════════════
#  LISTE DES ROUTES — Endpoint pour voir toutes les routes disponibles
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/routes", methods=["GET"])
def api_list_routes():
    """Retourne la liste de toutes les routes API disponibles."""
    rules = []
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith("/api/"):
            methods = [m for m in rule.methods if m in ("GET", "POST", "PATCH", "DELETE")]
            rules.append({
                "path": rule.rule,
                "methods": methods,
                "endpoint": rule.endpoint,
            })
    rules.sort(key=lambda r: r["path"])
    return jsonify({
        "total": len(rules),
        "routes": rules,
    })


# ══════════════════════════════════════════════════════════════════════════════
#  ÉTAT DU SCHEDULER — Voir les tâches automatiques à venir
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/scheduler", methods=["GET"])
def api_scheduler_status():
    """Retourne l'état du scheduler : tâches programmées et prochaine exécution."""
    jobs = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name or job.id,
            "trigger": str(job.trigger),
            "next_run": next_run.isoformat() if next_run else None,
            "next_run_human": _time_until(next_run) if next_run else "Désactivé",
        })
    jobs.sort(key=lambda j: j.get("next_run") or "")
    return jsonify({
        "total": len(jobs),
        "running": scheduler.running,
        "jobs": jobs,
    })


def _time_until(dt_from_schedule):
    """Retourne un texte lisible du temps restant avant la prochaine exécution."""
    now = dt.datetime.now(dt_from_schedule.tzinfo)
    diff = dt_from_schedule - now
    total_seconds = int(diff.total_seconds())
    if total_seconds <= 0:
        return "Imminent"
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}min")
    if seconds > 0 and hours == 0:
        parts.append(f"{seconds}s")
    return " ".join(parts) if parts else "Imminent"


# ── Routes dashboard ──────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    tenders = get_all_tenders()
    stats   = get_stats()
    users   = get_all_users()
    return render_template("dashboard.html", tenders=tenders, stats=stats, users=users)
@app.route("/api/tenders")
def api_tenders():
    try:
        sector = request.args.get("sector", "all")
        status = request.args.get("status", "all")
        page = request.args.get("page", 1, type=int)
        limit = request.args.get("limit", 20, type=int)

        if page < 1:
            page = 1
        if limit < 1 or limit > 100:
            limit = 20

        data = get_all_tenders(sector=sector, status=status, page=page, per_page=limit)
        return jsonify(data)
    except Exception as e:
        print(f"[ERREUR] /api/tenders : {str(e)}")
        return jsonify({"error": "Erreur interne lors de la récupération des appels d'offres"}), 500


@app.route("/api/search", methods=["POST"])
def api_search():
    try:
        data = request.get_json()
        query = data.get("query", "appel d'offres informatique Côte d'Ivoire")
        results = search_tenders(query)
        if results:
            notify_new_tenders(results)
        return jsonify({"status": "ok", "found": len(results), "results": results})
    except Exception as e:
        print(f"[ERREUR] /api/search : {str(e)}")
        return jsonify({"error": "Erreur lors de la recherche"}), 500


@app.route("/api/stats")
def api_stats():
    try:
        return jsonify(get_stats())
    except Exception as e:
        print(f"[ERREUR] /api/stats : {str(e)}")
        return jsonify({"error": "Impossible de récupérer les statistiques"}), 500


@app.route("/api/users")
def api_users():
    try:
        return jsonify(get_all_users())
    except Exception as e:
        print(f"[ERREUR] /api/users : {str(e)}")
        return jsonify({"error": "Erreur lors de la récupération des utilisateurs"}), 500


@app.route("/api/tender/<tender_id>/status", methods=["PATCH"])
def api_update_status(tender_id):
    try:
        data = request.get_json()
        status = data.get("status")
        if status not in ("Nouveau", "Lu", "Soumis", "Rejeté", "Traité"):
            return jsonify({"error": "Statut invalide"}), 400
        from models.database import update_status
        update_status(tender_id, status)
        return jsonify({"ok": True})
    except Exception as e:
        print(f"[ERREUR] /api/tender/{tender_id}/status : {str(e)}")
        return jsonify({"error": "Erreur lors de la mise à jour du statut"}), 500


@app.route("/api/tenders/<tender_id>/process", methods=["PATCH"])
def api_mark_processed(tender_id):
    try:
        from models.database import update_status
        update_status(tender_id, "Traité")
        return jsonify({"ok": True, "status": "Traité"})
    except Exception as e:
        print(f"[ERREUR] /api/tenders/{tender_id}/process : {str(e)}")
        return jsonify({"error": "Erreur lors du marquage 'Traité'"}), 500


@app.route("/api/tenders/<tender_id>")
def api_tender_detail(tender_id):
    try:
        from models.database import get_tender_by_id
        tender = get_tender_by_id(tender_id)
        if not tender:
            return jsonify({"error": "Appel d'offre introuvable"}), 404
        return jsonify(tender)
    except Exception as e:
        print(f"[ERREUR] /api/tenders/{tender_id} (détail) : {str(e)}")
        return jsonify({"error": "Erreur lors de la récupération du détail"}), 500
    

# # ── (Optionnel) Route dédiée pour "Traité" ─────────────────────────────────
# @app.route("/api/tenders/<tender_id>/process", methods=["PATCH"])
# def api_mark_processed(tender_id):
#     from models.database import update_status
#     update_status(tender_id, "Traité")
#     return jsonify({"ok": True, "status": "Traité"})





# ── Route TEST EMAIL ──────────────────────────────────────────────────────────

@app.route("/api/test-email")
def api_test_email():
    from utils.notifier import _send_email, _build_email_html
    from models.users import CATEGORIES

    fake_tender = {
        "id":          "test-000",
        "title":       "TEST — Développement portail marchés publics CI",
        "sector":      "Développement",
        "budget":      "45 000 000 FCFA",
        "deadline":    "2026-05-15",
        "description": "Ceci est un email de test du système AO Tracker INFOSOLUCES SARL.",
        "score":       85,
        "source_url":  "http://localhost:5000",
    }

    tenders = get_all_tenders()
    if tenders:
        fake_tender = tenders[0]

    sent_to = {}
    for cat_id, cat in CATEGORIES.items():
        for email in cat["emails"]:
            if email in sent_to:
                continue
            name    = email.split("@")[0].replace(".", " ").title()
            html    = _build_email_html(name, fake_tender, cat, urgent=False)
            subject = f"[TEST AO Tracker] {cat['label']} — {fake_tender['title'][:40]}"
            ok      = _send_email(email, subject, html)
            sent_to[email] = {"categorie": cat_id, "sent": ok}
            print(f"[TEST EMAIL] {cat_id} → {email} : {'✓' if ok else '✗'}")

    return jsonify({
        "status":  "ok",
        "tender":  fake_tender.get("title"),
        "envoyes": len([v for v in sent_to.values() if v["sent"]]),
        "details": sent_to,
    })


# ══════════════════════════════════════════════════════════════════════════════
#  GESTION DES UTILISATEURS / ÉQUIPES — Routes API
# ══════════════════════════════════════════════════════════════════════════════

from datetime import datetime
from bson import ObjectId
from pymongo.errors import DuplicateKeyError


@app.route("/api/users", methods=["GET"])
def api_list_users():
    """Liste tous les utilisateurs."""
    try:
        db = get_db()
        users = []
        for doc in db["users"].find().sort("full_name", 1):
            doc["id"] = str(doc.pop("_id"))
            users.append(doc)
        return jsonify({"items": users, "total": len(users)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/<user_id>", methods=["GET"])
def api_get_user(user_id):
    try:
        db = get_db()
        doc = db["users"].find_one({"_id": ObjectId(user_id)})
        if not doc:
            return jsonify({"error": "Utilisateur introuvable"}), 404
        doc["id"] = str(doc.pop("_id"))
        return jsonify(doc)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/users", methods=["POST"])
def api_create_user():
    try:
        data = request.get_json() or {}
        if not data.get("full_name") or not data.get("email"):
            return jsonify({"error": "Nom et email requis"}), 400

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
            "title":        data.get("title", ""),
            "created_at":   datetime.utcnow(),
            "updated_at":   datetime.utcnow(),
        }
        db = get_db()
        col = db["users"]
        col.create_index("username", unique=True)
        col.create_index("email", unique=True)
        result = col.insert_one(doc)
        doc["id"] = str(result.inserted_id)
        return jsonify({"status": "ok", "user": doc}), 201
    except DuplicateKeyError:
        return jsonify({"error": "Email ou nom d'utilisateur déjà pris"}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/<user_id>", methods=["PATCH"])
def api_update_user(user_id):
    try:
        data = request.get_json() or {}
        db = get_db()
        allowed = ("full_name", "email", "role", "categories", "sectors",
                   "score_min", "notify_email", "active", "phone", "title")
        update = {k: v for k, v in data.items() if k in allowed}
        if not update:
            return jsonify({"error": "Aucune donnée valide"}), 400
        update["updated_at"] = datetime.utcnow()
        result = db["users"].update_one(
            {"_id": ObjectId(user_id)}, {"$set": update}
        )
        if result.matched_count == 0:
            return jsonify({"error": "Introuvable"}), 404
        doc = db["users"].find_one({"_id": ObjectId(user_id)})
        doc["id"] = str(doc.pop("_id"))
        return jsonify({"status": "ok", "user": doc})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/<user_id>", methods=["DELETE"])
def api_delete_user(user_id):
    try:
        db = get_db()
        result = db["users"].update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"active": False, "updated_at": datetime.utcnow()}}
        )
        if result.matched_count == 0:
            return jsonify({"error": "Introuvable"}), 404
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/categories", methods=["GET"])
def api_list_categories():
    """Retourne les catégories disponibles."""
    cats = []
    for cid, cat in CATEGORIES.items():
        cats.append({
            "id": cid,
            "label": cat["label"],
            "emails": cat.get("emails", []),
        })
    return jsonify({"items": cats})


@app.route("/api/users/roles", methods=["GET"])
def api_list_roles():
    """Retourne les rôles disponibles."""
    return jsonify({
        "items": [
            {"id": "admin", "label": "Administrateur"},
            {"id": "member", "label": "Membre équipe"},
            {"id": "viewer", "label": "Lecteur"},
        ]
    })


# ══════════════════════════════════════════════════════════════════════════════
#  PROSPECTION EMAIL AUTOMATISÉE — Routes API
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/prospects")
def api_prospects():
    """Liste paginée des prospects."""
    try:
        status   = request.args.get("status", "all")
        campaign = request.args.get("campaign", "all")
        sector   = request.args.get("sector", "all")
        page     = request.args.get("page", 1, type=int)
        limit    = request.args.get("limit", 50, type=int)
        data = get_prospects(status=status, campaign=campaign, sector=sector, page=page, limit=limit)
        return jsonify(data)
    except Exception as e:
        print(f"[ERREUR] /api/prospects : {e}")
        return jsonify({"error": "Erreur récupération prospects"}), 500


@app.route("/api/prospects/stats")
def api_prospects_stats():
    """Statistiques de prospection."""
    return jsonify(get_prospect_stats())


@app.route("/api/prospects/generate", methods=["POST"])
def api_generate_prospects():
    """
    Génère des emails de prospection à partir des AO récents.
    Corps : {"limit": 5, "test_email": "optionnel@email.com"}
    """
    try:
        data = request.get_json() or {}
        limit     = data.get("limit", 5)
        test_mode = bool(data.get("test_email"))
        test_email = data.get("test_email", "")

        # Récupérer les derniers AO avec contacts
        tenders = get_all_tenders()
        # Filtrer ceux qui ont un contact email
        candidates = [
            t for t in tenders
            if t.get("contact") and t["contact"].get("email")
            and t["contact"].get("organisation")
        ]
        # Trier par score décroissant
        candidates.sort(key=lambda t: t.get("score", 0), reverse=True)
        candidates = candidates[:limit]

        if not candidates:
            return jsonify({"status": "ok", "generated": 0,
                            "message": "Aucun AO avec contact email trouvé"})

        generated = []
        for tender in candidates:
            # Vérifier qualité du prospect
            quality = score_prospect_quality(tender)
            if quality < 30:
                print(f"  [PROSPECT] Qualité insuffisante ({quality}) — ignoré: {tender.get('title','')[:40]}")
                continue

            # Vérifier si déjà prospecté
            contact = tender.get("contact", {})
            existing = create_prospect(
                company_name     = contact.get("organisation", "Inconnue"),
                contact_email    = test_email or contact.get("email", ""),
                contact_name     = contact.get("responsable", ""),
                contact_phone    = contact.get("telephone", ""),
                source_tender_id = tender.get("id", ""),
                source_url       = tender.get("source_url", ""),
                sector           = tender.get("sector", ""),
                score            = quality,
            )
            if not existing:
                print(f"  [PROSPECT] Déjà existant (doublon): {contact.get('organisation','')[:30]}")
                continue

            # Générer l'email via DeepSeek
            try:
                email = generate_prospect_email(tender)
            except Exception as e:
                print(f"  [PROSPECT] Échec génération email: {e}")
                continue

            # Mettre à jour le prospect avec l'email généré
            update_prospect_status(existing, "DRAFT",
                subject=email.get("subject", ""),
                body_html=email.get("body_html", ""),
                body_text=email.get("body_text", ""),
                call_to_action=email.get("call_to_action", ""),
                confidence=email.get("confidence", 0),
            )
            generated.append({
                "id":             existing,
                "company":        contact.get("organisation", ""),
                "email":          test_email or contact.get("email", ""),
                "subject":        email.get("subject", ""),
                "confidence":     email.get("confidence", 0),
                "call_to_action": email.get("call_to_action", ""),
            })
            print(f"  [PROSPECT] ✓ {contact.get('organisation','')[:30]} → {email.get('subject','')[:50]}")

        return jsonify({
            "status":    "ok",
            "generated": len(generated),
            "candidates": len(candidates),
            "prospects":  generated,
            "test_mode":  test_mode,
            "test_email": test_email or None,
        })
    except Exception as e:
        print(f"[ERREUR] /api/prospects/generate : {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/prospects/send", methods=["POST"])
def api_send_prospects():
    """
    Envoie les emails de prospection en attente (DRAFT).
    Corps : {"limit": 5, "test_mode": true}
    """
    try:
        data      = request.get_json() or {}
        limit     = data.get("limit", 5)
        test_mode = data.get("test_mode", False)
        test_email = data.get("test_email", "")

        drafts = get_prospects_to_send(limit=limit)
        if not drafts:
            return jsonify({"status": "ok", "sent": 0,
                            "message": "Aucun prospect en attente"})

        from utils.notifier import _send_email

        sent = []
        for prospect in drafts:
            to_email = test_email or prospect["contact_email"]
            subject  = prospect.get("subject", "") or ""
            body_html = prospect.get("body_html", "") or ""

            if not subject or not body_html:
                print(f"  [SEND] Contenu vide — ignore {prospect.get('company_name','')[:30]}")
                continue

            ok = _send_email(to_email, subject, body_html)
            if ok:
                mark_prospect_sent(prospect["id"])
                log_prospect_action(prospect["id"], "SENT", f"Envoyé à {to_email}")
                sent.append({"id": prospect["id"], "to": to_email, "status": "SENT"})
                print(f"  [SEND] ✓ {prospect.get('company_name','')[:30]} → {to_email}")
            else:
                update_prospect_status(prospect["id"], "BOUNCED")
                log_prospect_action(prospect["id"], "BOUNCED", f"Échec envoi à {to_email}")
                sent.append({"id": prospect["id"], "to": to_email, "status": "BOUNCED"})

        return jsonify({
            "status":     "ok",
            "sent":       len([s for s in sent if s["status"] == "SENT"]),
            "bounced":    len([s for s in sent if s["status"] == "BOUNCED"]),
            "details":    sent,
            "test_mode":  test_mode,
        })
    except Exception as e:
        print(f"[ERREUR] /api/prospects/send : {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/prospects/follow-up", methods=["POST"])
def api_follow_up():
    """Génère et envoie des relances pour les prospects sans réponse."""
    try:
        data = request.get_json() or {}
        limit = data.get("limit", 5)

        from utils.llm_prospect import generate_follow_up_email
        from utils.notifier    import _send_email

        candidates = get_prospects_for_follow_up(days_since_last=7, limit=limit)
        if not candidates:
            return jsonify({"status": "ok", "follow_ups": 0,
                            "message": "Aucun prospect à relancer"})

        sent = []
        for prospect in candidates:
            previous = {
                "subject":  prospect.get("subject", ""),
                "body_text": prospect.get("body_text", ""),
            }
            try:
                email = generate_follow_up_email(prospect, previous)
            except Exception as e:
                print(f"  [FOLLOW-UP] Échec génération: {e}")
                continue

            ok = _send_email(prospect["contact_email"], email["subject"], email["body_html"])
            if ok:
                follow_count = (prospect.get("follow_up_count") or 0) + 1
                update_prospect_status(prospect["id"], "FOLLOW_UP",
                    follow_up_count=follow_count,
                    subject=email.get("subject", ""),
                    body_html=email.get("body_html", ""),
                    body_text=email.get("body_text", ""),
                )
                log_prospect_action(prospect["id"], "FOLLOW_UP",
                    f"Relance #{follow_count}: {email.get('subject','')}")
                sent.append({"id": prospect["id"], "to": prospect["contact_email"]})
                print(f"  [FOLLOW-UP] ✓ {prospect.get('company_name','')[:30]} relance #{follow_count}")

        return jsonify({
            "status":     "ok",
            "follow_ups": len(sent),
            "details":    sent,
        })
    except Exception as e:
        print(f"[ERREUR] /api/prospects/follow-up : {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/prospects/campaigns")
def api_campaigns():
    """Liste les campagnes."""
    return jsonify({"items": get_campaigns()})


@app.route("/api/prospects/campaigns", methods=["POST"])
def api_create_campaign():
    """Crée une campagne."""
    data = request.get_json() or {}
    name = data.get("name", "Campagne sans nom")
    desc = data.get("description", "")
    sectors = data.get("sectors", [])
    cid = create_campaign(name, desc, sectors)
    return jsonify({"status": "ok", "campaign_id": cid})


# ══════════════════════════════════════════════════════════════════════════════
#  ANALYSE DE DOCUMENTS — Routes API
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/documents/analyze", methods=["POST"])
def api_analyze_document():
    """Analyse un document texte via DeepSeek."""
    try:
        data = request.get_json() or {}
        text  = data.get("text", "")
        title = data.get("title", "Document sans titre")
        prompt = data.get("custom_prompt")

        if not text or len(text) < 50:
            return jsonify({"error": "Texte trop court (min 50 car.)"}), 400

        report = analyze_document(text, title, custom_prompt=prompt)

        # Envoyer le rapport aux équipes
        sent = send_document_report(report)

        return jsonify({
            "status": "ok",
            "report": report,
            "notified": len([s for s in sent if s["sent"]]),
        })
    except Exception as e:
        print(f"[ERREUR] /api/documents/analyze : {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/documents/upload", methods=["POST"])
def api_upload_document():
    """Upload + analyse d'un fichier (PDF, DOCX, TXT, image)."""
    try:
        if "file" not in request.files:
            return jsonify({"error": "Aucun fichier fourni"}), 400

        file = request.files["file"]
        filename = file.filename or "document"
        custom_prompt = request.form.get("custom_prompt")

        # Sauvegarder temporairement
        import tempfile
        temp_dir = tempfile.gettempdir()
        safe_name = filename.replace(" ", "_").replace("/", "_")
        temp_path = os.path.join(temp_dir, f"doc_analysis_{safe_name}")
        file.save(temp_path)

        # Extraire le texte
        text = extract_text_from_file(temp_path)
        try:
            os.remove(temp_path)
        except:
            pass

        if not text or len(text) < 20:
            return jsonify({"error": "Impossible d'extraire le texte du document"}), 400

        # Analyser
        report = analyze_document(text, filename, custom_prompt=custom_prompt)
        sent = send_document_report(report)

        return jsonify({
            "status": "ok",
            "filename": filename,
            "text_length": len(text),
            "report": report,
            "notified": len([s for s in sent if s["sent"]]),
        })
    except Exception as e:
        print(f"[ERREUR] /api/documents/upload : {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/documents/default-prompt", methods=["GET"])
def api_default_prompt():
    """Retourne le prompt par défaut pour l'analyse de documents."""
    return jsonify({"prompt": DEFAULT_DOC_PROMPT})


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION LLM — Routes API
# ══════════════════════════════════════════════════════════════════════════════

# Stockage simple des configs en mémoire (NB: pourra être dans MongoDB)
_llm_config = {
    "prompt_analyse_doc": DEFAULT_DOC_PROMPT,
    "prompt_prospection": None,  # Utilise celui de llm_prospect.py
    "schedule_enabled":   True,
    "schedule_hours":     [8, 9, 10, 14, 15, 17],  # Heures d'exécution
    "schedule_interval":  "daily",  # daily, hourly, custom
    "model":              "deepseek-chat",
    "temperature":        0.7,
    "max_results":        10,
}


@app.route("/api/config/llm", methods=["GET"])
def api_get_llm_config():
    """Retourne la configuration LLM actuelle."""
    return jsonify(_llm_config)


@app.route("/api/config/llm", methods=["PATCH"])
def api_update_llm_config():
    """Met à jour la configuration LLM."""
    try:
        data = request.get_json() or {}
        for key in ("prompt_analyse_doc", "schedule_enabled", "schedule_hours",
                     "schedule_interval", "model", "temperature", "max_results"):
            if key in data:
                _llm_config[key] = data[key]
        return jsonify({"status": "ok", "config": _llm_config})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEDULER — Auto-expiration des AO
# ══════════════════════════════════════════════════════════════════════════════

def scheduled_expire_tenders():
    """
    Passe automatiquement en "Expiré" les AO dont la deadline est dépassée.
    Exécution quotidienne.
    """
    today = dt.datetime.utcnow().strftime("%Y-%m-%d")
    print(f"\n[EXPIRE] ⏰ Vérification des deadlines dépassées (date: {today})")

    from bson import ObjectId
    from models.database import get_db

    db = get_db()
    col = db["tenders"]

    # AO avec deadline passée ET encore en statut actif
    expired = col.update_many(
        {
            "deadline": {"$lt": today},
            "status": {"$in": ["Nouveau", "Lu"]},
        },
        {"$set": {"status": "Expiré", "updated_at": dt.datetime.utcnow()}}
    )

    if expired.modified_count > 0:
        print(f"[EXPIRE] ✅ {expired.modified_count} AO marqués comme Expirés")
    else:
        print(f"[EXPIRE] ℹ️  Aucun AO à expirer")


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEDULER — Analyse documentaire mensuelle
# ══════════════════════════════════════════════════════════════════════════════

def scheduled_document_check():
    """
    Vérifie les nouveaux documents dans un dossier surveillé.
    NB: Pour l'instant, placeholder — l'analyse se fait via l'API upload.
    """
    print(f"\n[DOC-CHECK] ⏰ Vérification documentaire...")
    print(f"[DOC-CHECK] ℹ️  L'analyse se fait via l'API /api/documents/analyze")


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEDULER — Prospection automatique
# ══════════════════════════════════════════════════════════════════════════════

def scheduled_prospect_generate():
    """
    Scheduler : génère des emails de prospection à partir des nouveaux AO.
    - Utilise les AO avec score >= 50 qui ont des contacts.
    - S'arrête à max 10 prospects par cycle pour gérer le budget DeepSeek.
    """
    import datetime
    now = datetime.datetime.now().strftime('%H:%M:%S')
    print(f"\n[PROSPECT-GEN] ⏰ {now} — Génération d'emails de prospection")

    tenders = get_all_tenders()
    candidates = [
        t for t in tenders
        if t.get("contact") and t["contact"].get("email")
        and t["contact"].get("organisation")
        and t.get("score", 0) >= 50
    ]
    candidates.sort(key=lambda t: t.get("score", 0), reverse=True)
    candidates = candidates[:10]

    if not candidates:
        print("  [PROSPECT-GEN] Aucun candidat")
        return

    generated = 0
    for tender in candidates:
        contact = tender.get("contact", {})
        quality = score_prospect_quality(tender)
        if quality < 30:
            continue

        existing = create_prospect(
            company_name     = contact.get("organisation", ""),
            contact_email    = contact.get("email", ""),
            contact_name     = contact.get("responsable", ""),
            contact_phone    = contact.get("telephone", ""),
            source_tender_id = tender.get("id", ""),
            source_url       = tender.get("source_url", ""),
            sector           = tender.get("sector", ""),
            score            = quality,
        )
        if not existing:
            continue

        try:
            email = generate_prospect_email(tender)
            update_prospect_status(existing, "DRAFT",
                subject=email.get("subject", ""),
                body_html=email.get("body_html", ""),
                body_text=email.get("body_text", ""),
                call_to_action=email.get("call_to_action", ""),
                confidence=email.get("confidence", 0),
            )
            generated += 1
            print(f"  [PROSPECT-GEN] ✓ {contact.get('organisation','')[:30]}")
        except Exception as e:
            print(f"  [PROSPECT-GEN] ✗ {e}")

        # Petite pause entre chaque appel DeepSeek
        import time
        time.sleep(random.uniform(1, 3))

    print(f"  [PROSPECT-GEN] ✅ {generated} emails générés")


def scheduled_prospect_send_all():
    """
    Scheduler : envoie les emails de prospection en attente vers TOUS les destinataires réels.
    - S'exécute après generation pour envoyer les DRAFT.
    - Limité à 5 par cycle pour respecter les limites SMTP.
    """
    import datetime
    now = datetime.datetime.now().strftime('%H:%M:%S')
    print(f"\n[PROSPECT-SEND] ⏰ {now} — Envoi des emails de prospection")

    from utils.notifier import _send_email

    drafts = get_prospects_to_send(limit=5)
    if not drafts:
        print("  [PROSPECT-SEND] Aucun prospect en attente")
        return

    sent = 0
    bounced = 0
    for prospect in drafts:
        subject    = prospect.get("subject", "") or ""
        body_html  = prospect.get("body_html", "") or ""
        to_email   = prospect["contact_email"]

        if not subject or not body_html:
            continue

        ok = _send_email(to_email, subject, body_html)
        if ok:
            mark_prospect_sent(prospect["id"])
            log_prospect_action(prospect["id"], "SENT", f"Auto → {to_email}")
            sent += 1
            print(f"  [PROSPECT-SEND] ✓ {prospect.get('company_name','')[:25]} → {to_email}")
        else:
            update_prospect_status(prospect["id"], "BOUNCED")
            log_prospect_action(prospect["id"], "BOUNCED", f"Auto bounce → {to_email}")
            bounced += 1

    print(f"  [PROSPECT-SEND] ✅ {sent} envoyés · {bounced} rebondis")


def scheduled_prospect_send_test():
    """
    Scheduler TEST : envoie les emails de prospection UNIQUEMENT vers aymarbly559@gmail.com
    pour validation avant envoi réel.
    """
    import datetime
    now = datetime.datetime.now().strftime('%H:%M:%S')
    print(f"\n[PROSPECT-TEST] ⏰ {now} — Envoi test vers aymarbly559@gmail.com")

    from utils.notifier import _send_email

    test_email = "aymarbly559@gmail.com"
    drafts = get_prospects_to_send(limit=3)

    if not drafts:
        print("  [PROSPECT-TEST] Aucun prospect en attente")
        return

    sent = 0
    for prospect in drafts:
        subject    = prospect.get("subject", "") or ""
        body_html  = prospect.get("body_html", "") or ""

        if not subject or not body_html:
            continue

        # Ajouter [TEST] dans le sujet pour les identifier
        test_subject = f"[TEST PROSPECTION] {subject}"
        ok = _send_email(test_email, test_subject, body_html)
        if ok:
            log_prospect_action(prospect["id"], "TEST_SENT",
                f"Test envoyé à {test_email}")
            sent += 1
            print(f"  [PROSPECT-TEST] ✓ Test → {test_email} : {subject[:40]}")
        else:
            print(f"  [PROSPECT-TEST] ✗ Échec test")

    print(f"  [PROSPECT-TEST] ✅ {sent} emails test envoyés")


# ── Scheduler ─────────────────────────────────────────────────────────────────

SEARCH_QUERIES = {
    "ao_dev": [
        '"appel d\'offres" "développement logiciel" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "développement application web" "Abidjan" 2026',
        '"appel d\'offres" "développement application mobile" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "ERP" OR "progiciel de gestion" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "système d\'information" "administration publique" "CI" 2026',
        '"appel d\'offres" "digitalisation" OR "transformation numérique" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "plateforme e-gouvernement" OR "portail web" "CI" 2026',
        '"avis d\'appel d\'offres" "développement" "site internet" "marché public" "Abidjan" 2026',
        '"tender" OR "RFP" "software development" "Ivory Coast" 2026',
        '"tender" "web application" OR "mobile app" "Ivory Coast" 2026',
        'site:anrmp.ci "développement" OR "logiciel" OR "application" 2026',
        'site:dmp.gouv.ci "développement" OR "numérique" 2026',
        '"appel d\'offres" "intranet" OR "extranet" "entreprise publique" "CI" 2026',
        '"appel d\'offres" "dématérialisation" OR "GED" "Côte d\'Ivoire" 2026',
        '"request for proposal" "ERP" OR "CRM" "Abidjan" 2026',
    ],
    "ao_reseau": [
        '"appel d\'offres" "réseau informatique" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "infrastructure réseau" "Abidjan" 2026',
        '"appel d\'offres" "fibre optique" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "câblage réseau" OR "câblage structuré" "CI" 2026',
        '"appel d\'offres" "Wi-Fi" OR "réseau sans fil" "bâtiment public" "CI" 2026',
        '"appel d\'offres" "datacenter" OR "centre de données" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "hébergement serveur" OR "colocation" "CI" 2026',
        '"appel d\'offres" "cloud computing" OR "infrastructure cloud" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "virtualisation" OR "VMware" OR "Hyper-V" "CI" 2026',
        '"appel d\'offres" "LAN" OR "WAN" OR "MPLS" "Côte d\'Ivoire" 2026',
        '"tender" "network infrastructure" OR "LAN WAN" "Ivory Coast" 2026',
        '"tender" "cloud services" OR "hosting" "Ivory Coast" 2026',
        'site:anrmp.ci "réseau" OR "infrastructure" OR "câblage" 2026',
        '"avis d\'appel d\'offres" "réseau" site:*.ci 2026',
        '"appel d\'offres" "déploiement" "réseau" "école" OR "hôpital" OR "mairie" "CI" 2026',
    ],
    "ao_securite": [
        '"appel d\'offres" "sécurité informatique" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "cybersécurité" "Abidjan" 2026',
        '"appel d\'offres" "audit sécurité" "système d\'information" "CI" 2026',
        '"appel d\'offres" "firewall" OR "pare-feu" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "antivirus" OR "endpoint protection" "CI" 2026',
        '"appel d\'offres" "SIEM" OR "SOC" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "pentest" OR "test d\'intrusion" "CI" 2026',
        '"appel d\'offres" "chiffrement" OR "PKI" OR "certificat SSL" "CI" 2026',
        '"appel d\'offres" "sauvegarde" OR "backup" OR "PRA" "Côte d\'Ivoire" 2026',
        '"tender" "cybersecurity" OR "information security" "Ivory Coast" 2026',
        '"tender" "firewall" OR "SOC" OR "SIEM" "Ivory Coast" 2026',
        'site:anrmp.ci "sécurité" OR "cybersécurité" 2026',
        '"avis d\'appel d\'offres" "sécurité" "données" site:*.ci 2026',
        '"appel d\'offres" "ISO 27001" OR "conformité sécurité" "CI" 2026',
        '"request for proposal" "cybersecurity audit" "Ivory Coast" 2026',
    ],
    "ao_materiel": [
        '"appel d\'offres" "fourniture matériel informatique" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "fourniture ordinateurs" "marché public" "Abidjan" 2026',
        '"appel d\'offres" "fourniture imprimantes" OR "scanners" "CI" 2026',
        '"appel d\'offres" "acquisition serveurs" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "équipements réseau" "switches" OR "routeurs" "CI" 2026',
        '"appel d\'offres" "tablettes" OR "smartphones" "institution" "CI" 2026',
        '"appel d\'offres" "stockage" OR "NAS" OR "SAN" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "vidéoprojecteurs" OR "écrans interactifs" "CI" 2026',
        '"appel d\'offres" "consommables informatiques" "marché public" "CI" 2026',
        '"tender" "IT hardware" OR "computers" OR "servers" "Ivory Coast" 2026',
        '"tender" "supply" "network equipment" "Ivory Coast" 2026',
        'site:anrmp.ci "fourniture" "informatique" OR "matériel" 2026',
        '"avis d\'appel d\'offres" "ordinateurs" OR "équipements" site:*.ci 2026',
        '"appel d\'offres" "UPS" OR "onduleurs" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "mobilier informatique" OR "rack serveur" "CI" 2026',
    ],
    "ao_maintenance": [
        '"appel d\'offres" "maintenance parc informatique" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "infogérance" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "TMA" OR "tierce maintenance applicative" "CI" 2026',
        '"appel d\'offres" "support technique" "helpdesk" "Abidjan" 2026',
        '"appel d\'offres" "maintenance préventive" "équipements informatiques" "CI" 2026',
        '"appel d\'offres" "télémaintenance" OR "supervision" "réseau" "CI" 2026',
        '"appel d\'offres" "contrat de maintenance" "logiciel" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "MCO" OR "maintien en condition opérationnelle" "CI" 2026',
        '"tender" "managed IT services" OR "IT support" "Ivory Coast" 2026',
        '"tender" "maintenance contract" "IT" "Ivory Coast" 2026',
        'site:anrmp.ci "maintenance" "informatique" 2026',
        '"avis d\'appel d\'offres" "maintenance" "parc" site:*.ci 2026',
        '"appel d\'offres" "exploitation" "système d\'information" "CI" 2026',
        '"appel d\'offres" "SLA" OR "niveau de service" "informatique" "CI" 2026',
        '"appel d\'offres" "hotline" OR "centre de support" "CI" 2026',
    ],
    "ao_electricite": [
        '"appel d\'offres" "installation électrique" "bâtiment public" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "travaux électriques" "Abidjan" 2026',
        '"appel d\'offres" "panneaux solaires" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "énergie solaire" OR "photovoltaïque" "CI" 2026',
        '"appel d\'offres" "électrification rurale" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "groupe électrogène" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "onduleur" OR "UPS" OR "alimentation secourue" "CI" 2026',
        '"appel d\'offres" "tableau électrique" OR "armoire électrique" "CI" 2026',
        '"appel d\'offres" "câblage électrique" "école" OR "hôpital" OR "mairie" "CI" 2026',
        '"appel d\'offres" "éclairage LED" OR "éclairage public" "Côte d\'Ivoire" 2026',
        '"tender" "solar energy" OR "photovoltaic" "Ivory Coast" 2026',
        '"tender" "electrical works" OR "power supply" "Ivory Coast" 2026',
        'site:anrmp.ci "électricité" OR "énergie" OR "solaire" 2026',
        '"appel d\'offres" "réseau électrique" "maintenance" "CI" 2026',
        '"appel d\'offres" "hybride solaire" OR "mini-réseau" "CI" 2026',
    ],
    "ao_institutionnel": [
        'site:anrmp.ci 2026',
        'site:dmp.gouv.ci 2026',
        '"ANRMP" "avis" "informatique" OR "numérique" "2026"',
        '"DMP Côte d\'Ivoire" "appel d\'offres" "IT" 2026',
        '"appel d\'offres" "PNUD" OR "UNDP" "informatique" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "UNICEF" "IT" OR "numérique" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "Banque Mondiale" OR "World Bank" "IT" "Côte d\'Ivoire" 2026',
        '"appel d\'offres" "BAD" OR "Banque Africaine de Développement" "IT" "CI" 2026',
        '"appel d\'offres" "Union Européenne" "numérique" "Côte d\'Ivoire" 2026',
        'site:undp.org "procurement" "Ivory Coast" OR "Côte d\'Ivoire" "IT" 2026',
        'site:ungm.org "Ivory Coast" "IT" OR "ICT" 2026',
        '"request for proposal" OR "RFP" "IT" "Abidjan" 2026',
        '"avis de sollicitation" "informatique" "Côte d\'Ivoire" 2026',
        '"consultation restreinte" "informatique" site:*.ci 2026',
        '"expression d\'intérêt" "IT" OR "numérique" "Côte d\'Ivoire" 2026',
    ],
    "entreprises_ci": [
        '"nouvelle entreprise" "informatique" "Abidjan" 2026',
        '"startup" "tech" "Côte d\'Ivoire" "lancée" OR "créée" 2026',
        '"levée de fonds" "startup" "Côte d\'Ivoire" 2026',
        '"financement" "tech" OR "numérique" "Abidjan" 2026',
        'inurl:linkedin.com/company "informatique" "Abidjan" "2025" OR "2026"',
        '"ouverture" "agence" OR "bureau" "IT" "Abidjan" 2026',
        '"incubateur" OR "accélérateur" "startup" "Côte d\'Ivoire" 2026',
        '"seed" OR "série A" "startup" "Afrique de l\'Ouest" "tech" 2026',
        '"nouvelle société" "numérique" OR "informatique" "Côte d\'Ivoire" 2026',
        '"expansion" "entreprise IT" "Afrique" "Abidjan" 2026',
        '"partenariat" "technologique" "entreprise" "Côte d\'Ivoire" 2026',
        '"Tech hub" OR "innovation hub" "Abidjan" 2026',
        '"registre commerce" "RCCM" "informatique" "Abidjan" 2026',
        '"acquisition" OR "fusion" "entreprise IT" "Côte d\'Ivoire" 2026',
        '"prix" OR "award" "startup" "technologie" "Côte d\'Ivoire" 2026',
    ],
    "salons_evenements": [
        '"salon" "informatique" OR "numérique" "Abidjan" 2026',
        '"forum" "technologie" OR "digital" "Côte d\'Ivoire" 2026',
        '"conférence" "IT" OR "tech" "Abidjan" 2026',
        '"Africa tech" "summit" OR "forum" 2026',
        '"hackathon" "Abidjan" OR "Côte d\'Ivoire" 2026',
        '"AFRICA CEO Forum" 2026',
        '"Smart Africa" "événement" OR "conférence" 2026',
        '"journée" OR "semaine" "numérique" "Côte d\'Ivoire" 2026',
        '"expo" OR "exhibition" "informatique" "Abidjan" 2026',
        '"Africa Fintech" OR "AfricaTech" "2026"',
        '"West Africa" "tech event" OR "digital summit" 2026',
        '"GITEX Africa" 2026',
        '"Innovation" "technologie" "prix" OR "concours" "CI" 2026',
        '"webinaire" OR "webinar" "IT" "Côte d\'Ivoire" 2026',
        '"meetup" "développeurs" OR "tech" "Abidjan" 2026',
    ],
    "certifications_microsoft": [
        'site:learn.microsoft.com "new certification" 2026',
        'site:learn.microsoft.com "exam" "retire" 2026',
        '"Microsoft Certified" "nouveau" OR "mise à jour" 2026',
        '"AZ-900" OR "AZ-104" OR "AZ-305" "update" OR "new exam" 2026',
        '"MS-900" OR "MS-102" OR "MS-700" "update" 2026',
        '"SC-900" OR "SC-200" OR "SC-300" "update" 2026',
        '"AI-900" OR "AI-102" "Azure AI" "update" 2026',
        '"DP-900" OR "DP-203" OR "DP-300" "update" 2026',
        '"Microsoft certification" "retire" OR "replaced" 2026',
        '"Microsoft partner" "Gold" OR "Solutions Partner" "Africa" 2026',
        '"Microsoft Certified" "Associate" OR "Expert" "new path" 2026',
        'site:microsoft.com/en-us/learning "certification" "2026"',
        '"Power Platform" certification "update" 2026',
        '"Dynamics 365" certification "new" OR "update" 2026',
        '"Microsoft fabric" OR "Copilot" certification "2026"',
    ],
    "certifications_fortinet": [
        'site:training.fortinet.com 2026',
        '"Fortinet NSE" "update" OR "new version" 2026',
        '"NSE 4" OR "NSE 7" OR "NSE 8" "FortiGate" "update" 2026',
        '"Fortinet Certified" "new" OR "retire" 2026',
        '"FortiGate Administrator" certification "update" 2026',
        '"FortiAnalyzer" OR "FortiManager" certification "2026"',
        '"Fortinet" "partner" "certification" "Africa" 2026',
        '"Fortinet NSE" "exam" "retire" OR "replaced" 2026',
        '"Fortinet certified professional" "update" 2026',
        '"FortiEDR" OR "FortiXDR" certification "2026"',
        '"Fortinet" "new exam" OR "nouvelle certification" 2026',
        '"Fortinet Security Fabric" certification "2026"',
        'inurl:fortinet.com "certification" "2026"',
        '"Fortinet" "training" "Afrique" OR "Africa" 2026',
        '"NSE Institute" "new course" OR "update" 2026',
    ],
    "certifications_reseau": [
        'site:learningnetwork.cisco.com "new" OR "update" OR "retire" 2026',
        '"CCNA" "update" OR "new version" OR "retire" 2026',
        '"CCNP" "Enterprise" OR "Security" OR "Data Center" "update" 2026',
        '"CCIE" "new lab" OR "update" 2026',
        '"CompTIA Network+" OR "Security+" "update" OR "new version" 2026',
        '"CompTIA CySA+" OR "CASP+" OR "PenTest+" "update" 2026',
        '"AWS Certified" "new" OR "update" 2026',
        '"AWS Solutions Architect" OR "AWS SysOps" "update" 2026',
        '"Google Cloud" "Professional" certification "update" 2026',
        '"Google Cloud Associate" OR "Professional Data Engineer" "2026"',
        '"Juniper JNCIA" OR "JNCIS" OR "JNCIP" "update" 2026',
        '"Palo Alto" "PCNSA" OR "PCNSE" "update" 2026',
        'site:cisco.com "certification" "new" OR "update" "2026"',
        '"certification réseau" "nouvelle" "2026"',
        '"Check Point" "CCSA" OR "CCSE" "update" 2026',
    ],
    "ia_postes_publications": [
        'site:linkedin.com/jobs "data scientist" "Abidjan" 2026',
        'site:linkedin.com/jobs "machine learning" OR "IA" "Côte d\'Ivoire" 2026',
        '"offre emploi" "intelligence artificielle" OR "IA" "Abidjan" 2026',
        '"recrutement" "data engineer" OR "MLOps" "Côte d\'Ivoire" 2026',
        '"poste" "ingénieur IA" OR "AI engineer" "Afrique de l\'Ouest" 2026',
        '"AI job" OR "data science job" "Ivory Coast" 2026',
        '"publication" OR "recherche" "intelligence artificielle" "Afrique" 2026',
        '"déploiement" "ChatGPT" OR "Copilot" OR "Gemini" "entreprise" "CI" 2026',
        '"transformation IA" "PME" OR "entreprise" "Côte d\'Ivoire" 2026',
        '"formation" "intelligence artificielle" OR "deep learning" "Abidjan" 2026',
        '"AI startup" "West Africa" OR "Ivory Coast" 2026',
        '"LLM" OR "modèle de langage" "Afrique" "application" 2026',
        '"prix IA" OR "AI award" "Afrique" 2026',
        '"gouvernance IA" OR "éthique IA" "Afrique" 2026',
        '"computer vision" OR "NLP" "projet" "Côte d\'Ivoire" 2026',
    ],
    "microsoft_croissance": [
        'site:news.microsoft.com "Africa" OR "Afrique" 2026',
        '"Microsoft" "investissement" "Afrique" 2026',
        '"Microsoft Africa" "expansion" OR "partenariat" 2026',
        '"Microsoft Azure" "datacenter" "Africa" 2026',
        '"Microsoft" "Côte d\'Ivoire" OR "Abidjan" 2026',
        '"Microsoft Copilot" "Afrique de l\'Ouest" 2026',
        '"Microsoft Teams" "déploiement" "Afrique" 2026',
        '"Microsoft" "résultats financiers" "croissance" "Afrique" 2026',
        '"Microsoft partner network" "Africa" "2026"',
        '"Microsoft" "startup" "Afrique" "programme" 2026',
        '"Microsoft" "gouvernement" "Côte d\'Ivoire" "accord" 2026',
        '"Microsoft" "AI" "Africa" "initiative" 2026',
        '"Microsoft for Startups" "Africa" 2026',
        '"Microsoft" "formation" "jeunes" "Afrique" 2026',
        'site:aka.ms OR site:microsoft.com "Africa" "2026"',
    ],
    "formations_it": [
        '"formation" "Cisco" OR "CCNA" "Abidjan" OR "Côte d\'Ivoire" 2026',
        '"formation" "Fortinet" OR "NSE" "Abidjan" 2026',
        '"formation" "cybersécurité" "Côte d\'Ivoire" 2026',
        '"formation" "développement web" OR "PHP" OR "React" "Abidjan" 2026',
        '"formation" "Python" OR "Java" OR "DevOps" "Côte d\'Ivoire" 2026',
        '"formation" "cloud" OR "Azure" OR "AWS" "Abidjan" 2026',
        '"formation" "infogérance" OR "administration système" "CI" 2026',
        '"formation" "électricité industrielle" "Abidjan" 2026',
        '"bootcamp" "développement" OR "informatique" "Abidjan" 2026',
        '"formation certifiante" "informatique" "Côte d\'Ivoire" 2026',
        '"programme" "formation IT" "Afrique francophone" 2026',
        '"centre de formation" "informatique" "Abidjan" 2026',
        '"bourse" OR "financement" "formation" "IT" "Côte d\'Ivoire" 2026',
        '"formation en ligne" OR "e-learning" "informatique" "Afrique" 2026',
        '"certification" "formation" "réseau" OR "sécurité" "Abidjan" 2026',
    ],
}

ALL_QUERIES = [q for queries in SEARCH_QUERIES.values() for q in queries]

# =========================================================
# FILTRE PRÉ-LLM — évite d'appeler DeepSeek inutilement
# Réduit les appels DeepSeek de ~4 500 → ~1 500 par cycle
# =========================================================
KEYWORDS_CI = [
    # Géographie
    "côte d'ivoire", "cote d'ivoire", "abidjan", "ivory coast",
    "ci", "yopougon", "cocody", "plateau", "marcory",
    # AO
    "appel d'offres", "avis d'appel", "marché public", "tender",
    "rfp", "request for proposal", "procurement", "sollicitation",
    "consultation", "expression d'intérêt",
    # Institutions CI
    "anrmp", "dmp", "bceao", "dgmp", "marchespublics.ci",
    # Afrique
    "afrique de l'ouest", "west africa", "afrique francophone",
    "afrique", "africa",
    # Certifications (pas géo-spécifiques mais utiles)
    "fortinet", "cisco", "microsoft certified", "aws certified",
    "google cloud", "comptia",
    # IA / Tech veille
    "intelligence artificielle", "data scientist", "machine learning",
]

def _is_worth_analyzing(title: str, snippet: str) -> bool:
    """
    Filtre rapide AVANT d'appeler DeepSeek.
    Retourne True si le contenu semble pertinent pour INFOSOLUCES.
    Économise ~66% des appels LLM.
    """
    text = (title + " " + snippet).lower()
    return any(kw.lower() in text for kw in KEYWORDS_CI)


# =========================================================
# SCHEDULER
# =========================================================

def scheduled_search():
    import datetime
    print(f"\n[SCHEDULER] ⏰ {datetime.datetime.now().strftime('%H:%M:%S')} — {len(ALL_QUERIES)} requêtes")
    all_new = []
    skipped = 0

    for q in ALL_QUERIES:
        try:
            found = search_tenders(q)
            all_new.extend(found)
        except Exception as e:
            print(f"[SCHEDULER] ⚠️  Erreur '{q[:40]}...': {e}")

    if all_new:
        print(f"[SCHEDULER] ✅ {len(all_new)} nouveaux → notifications")
        summary = notify_new_tenders(all_new)
        print(f"[SCHEDULER] Envoyés : {summary}")
    else:
        print("[SCHEDULER] ℹ️  Aucun nouveau résultat.")

    notify_urgent_tenders()












# TEST : toutes les 5 min
scheduler.add_job(
    func=scheduled_search, trigger="interval",
    minutes=5, id="auto_search", max_instances=1,
)

# PROD : lundi–vendredi à 07h
# scheduler.add_job(
#     func=scheduled_search,
#     trigger="cron",
#     day_of_week="mon,thu",  # 2 jours seulement
#     hour=7,
#     minute=0,
#     id="search_semaine",
#     max_instances=1,
# )

# WEEKEND : rappels AO urgents seulement
# scheduler.add_job(
#     func=notify_urgent_tenders, trigger="cron",
#     day_of_week="sat,sun", hour=9, minute=0,
#     id="search_weekend", max_instances=1,
# )


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEDULER JOBS — Prospection
# ══════════════════════════════════════════════════════════════════════════════

# TEST : génération de prospection toutes les 30 minutes (envoi TEST vers aymarbly)
# scheduler.add_job(
#     func=scheduled_prospect_generate, trigger="interval",
#     minutes=30, id="prospect_generate", max_instances=1,
# )
# scheduler.add_job(
#     func=scheduled_prospect_send_test, trigger="interval",
#     minutes=35, id="prospect_send_test", max_instances=1,
# )

# PROD : génération tous les jours à 08h, envoi à 09h
# scheduler.add_job(
#     func=scheduled_prospect_generate, trigger="cron",
#     hour=8, minute=0, id="prospect_gen_am", max_instances=1,
# )
# scheduler.add_job(
#     func=scheduled_prospect_send_all, trigger="cron",
#     hour=9, minute=0, id="prospect_send_am", max_instances=1,
# )
# scheduler.add_job(
#     func=scheduled_prospect_generate, trigger="cron",
#     hour=14, minute=0, id="prospect_gen_pm", max_instances=1,
# )
# scheduler.add_job(
#     func=scheduled_prospect_send_all, trigger="cron",
#     hour=15, minute=0, id="prospect_send_pm", max_instances=1,
# )

# RELANCE : tous les jours à 10h (prospects sans réponse depuis 7+ jours)
# scheduler.add_job(
#     func=lambda: _run_follow_up(), trigger="interval",
#     hours=24, id="prospect_follow_up", max_instances=1,
# )

def _run_follow_up():
    """Wrapper pour les relances automatiques."""
    import datetime
    now = datetime.datetime.now().strftime('%H:%M:%S')
    print(f"\n[FOLLOW-UP] ⏰ {now} — Relances automatiques")

    from utils.llm_prospect import generate_follow_up_email
    from utils.notifier    import _send_email

    candidates = get_prospects_for_follow_up(days_since_last=7, limit=5)
    if not candidates:
        print("  [FOLLOW-UP] Aucun prospect à relancer")
        return

    sent = 0
    for prospect in candidates:
        previous = {
            "subject":  prospect.get("subject", ""),
            "body_text": prospect.get("body_text", ""),
        }
        try:
            email = generate_follow_up_email(prospect, previous)
        except Exception as e:
            print(f"  [FOLLOW-UP] ✗ {e}")
            continue

        ok = _send_email(prospect["contact_email"], email["subject"], email["body_html"])
        if ok:
            follow_count = (prospect.get("follow_up_count") or 0) + 1
            update_prospect_status(prospect["id"], "FOLLOW_UP",
                follow_up_count=follow_count,
                subject=email.get("subject", ""),
                body_html=email.get("body_html", ""),
                body_text=email.get("body_text", ""),
            )
            log_prospect_action(prospect["id"], "FOLLOW_UP",
                f"Auto relance #{follow_count}")
            sent += 1
            print(f"  [FOLLOW-UP] ✓ {prospect.get('company_name','')[:25]} relance #{follow_count}")

    print(f"  [FOLLOW-UP] ✅ {sent} relances envoyées")


# ══════════════════════════════════════════════════════════════════════════════
#  SCHEDULER JOBS — Auto-expiration & Documents
# ══════════════════════════════════════════════════════════════════════════════

# Auto-expiration des AO (quotidien à 02h00)
scheduler.add_job(
    func=scheduled_expire_tenders, trigger="cron",
    hour=2, minute=0, id="expire_tenders", max_instances=1,
)

# Vérification documentaire (quotidien à 06h00)
scheduler.add_job(
    func=scheduled_document_check,
    trigger="cron",
    day="1,15",   # deux fois par mois
    hour=6,
    minute=0,
    id="doc_check",
    max_instances=1,
)


scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ── Démarrage ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    init_users()
    init_prospects()
    print(f"\n{'='*60}")
    print(f"  🚀 AO TRACKER — INFOSOLUCES SARL")
    print(f"{'='*60}")
    print(f"  Dashboard     → http://localhost:5000")
    print(f"  Test email    → http://localhost:5000/api/test-email")
    print(f"  Prospects     → http://localhost:5000/api/prospects")
    print(f"  Générer       → POST /api/prospects/generate")
    print(f"  Envoyer       → POST /api/prospects/send")
    print(f"  Relancer      → POST /api/prospects/follow-up")
    print(f"  Stats         → /api/prospects/stats")
    print(f"  Campagnes     → /api/prospects/campaigns")
    print(f"  Docs Analyse  → POST /api/documents/analyze")
    print(f"  Docs Upload   → POST /api/documents/upload")
    print(f"  Config LLM    → GET  /api/config/llm")
    print(f"  Requêtes      → {len(ALL_QUERIES)} au total")
    print(f"  Filtre CI     → {len(KEYWORDS_CI)} mots-clés")
    print(f"  Catégories    → {list(SEARCH_QUERIES.keys())}")
    print(f"  Scheduler      → /api/scheduler")
    print(f"  Prospection   → Test toutes les 30 min")
    print(f"  Auto-expire   → Quotidien 02h00")
    print(f"{'='*60}\n")

    # Afficher les tâches programmées dans la console
    print(f"  ⏰ Tâches programmées :")
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        if next_run:
            human = _time_until(next_run)
            print(f"     • {job.id:<25} prochaine exécution dans {human}")
        else:
            print(f"     • {job.id:<25} désactivé")
    print()
    app.run(debug=True, port=5000, use_reloader=True)