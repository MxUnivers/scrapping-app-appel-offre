from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from scrapers.web_search import search_tenders
from models.database import init_db, get_all_tenders, get_stats
from models.users    import init_users, get_all_users
from utils.notifier  import notify_new_tenders, notify_urgent_tenders
import atexit

app = Flask(__name__)
scheduler = BackgroundScheduler()

# ── Routes dashboard ──────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    tenders = get_all_tenders()
    stats   = get_stats()
    users   = get_all_users()
    return render_template("dashboard.html", tenders=tenders, stats=stats, users=users)

@app.route("/api/tenders")
def api_tenders():
    sector = request.args.get("sector", "all")
    status = request.args.get("status", "all")
    return jsonify(get_all_tenders(sector=sector, status=status))

@app.route("/api/search", methods=["POST"])
def api_search():
    data    = request.get_json()
    query   = data.get("query", "appel d'offres informatique Côte d'Ivoire")
    results = search_tenders(query)
    if results:
        notify_new_tenders(results)
    return jsonify({"status": "ok", "found": len(results), "results": results})

@app.route("/api/stats")
def api_stats():
    return jsonify(get_stats())

@app.route("/api/users")
def api_users():
    return jsonify(get_all_users())

@app.route("/api/tender/<tender_id>/status", methods=["PATCH"])
def api_update_status(tender_id):
    data   = request.get_json()
    status = data.get("status")
    if status not in ("Nouveau", "Lu", "Soumis", "Rejeté"):
        return jsonify({"error": "Statut invalide"}), 400
    from models.database import update_status
    update_status(tender_id, status)
    return jsonify({"ok": True})

# ── Route TEST EMAIL ──────────────────────────────────────────────────────────

@app.route("/api/test-email")
def api_test_email():
    """
    Envoie un email de test à toutes les équipes.
    GET http://localhost:5000/api/test-email
    """
    from utils.notifier import _send_email, _build_email_html, CATEGORIES

    # AO fictif de test
    fake_tender = {
        "id":          "test-000",
        "title":       "TEST — Développement portail marchés publics CI",
        "sector":      "Développement",
        "budget":      "45 000 000 FCFA",
        "deadline":    "2026-05-15",
        "description": "Ceci est un email de test du système AO Tracker INFOSOLUCES SARL. "
                       "Si vous recevez cet email, la configuration fonctionne correctement.",
        "score":       85,
        "source_url":  "http://localhost:5000",
    }

    # Prendre un vrai AO si disponible
    tenders = get_all_tenders()
    if tenders:
        fake_tender = tenders[0]

    # Envoyer à tous les destinataires de toutes les catégories
    from models.users import CATEGORIES
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

# ── Scheduler ─────────────────────────────────────────────────────────────────

SEARCH_QUERIES = [

    # ── Développement / Logiciel / ERP / Web / Mobile ─────────────────────────
    "appel d'offres développement logiciel Côte d'Ivoire 2026",
    "appel d'offres développement application web Abidjan",
    "appel d'offres développement application mobile Côte d'Ivoire",
    "solution ERP appel d'offres Afrique francophone",
    "appel d'offres système de gestion informatisé CI",
    "plateforme digitale gouvernement appel d'offres Côte d'Ivoire",
    "création site internet marché public Abidjan",
    "appel d'offres digitalisation administration publique CI",
    "software development tender Ivory Coast",
    "IT system tender West Africa 2026",
    "appel d'offres intranet extranet entreprise CI",
    "développement plateforme e-gouvernement appel d'offres",

    # ── Réseau / Infrastructure / Cloud ───────────────────────────────────────
    "appel d'offres réseau informatique Côte d'Ivoire 2026",
    "network infrastructure tender West Africa",
    "appel d'offres installation fibre optique Côte d'Ivoire",
    "maintenance réseau LAN WAN marché public CI",
    "appel d'offres déploiement Wi-Fi entreprise publique Abidjan",
    "cloud computing services tender Africa",
    "appel d'offres hébergement serveur datacenter CI",
    "IT infrastructure tender Ivory Coast government",
    "appel d'offres virtualisation infrastructure informatique CI",
    "network cabling tender West Africa",

    # ── Sécurité informatique / Cybersécurité ─────────────────────────────────
    "cybersecurity services tender Africa 2026",
    "appel d'offres sécurité informatique Côte d'Ivoire",
    "audit sécurité système informatique appel d'offres CI",
    "appel d'offres antivirus protection endpoint entreprise CI",
    "appel d'offres pare-feu firewall administration publique",
    "cybersecurity audit tender West Africa",
    "appel d'offres SIEM SOC sécurité réseau CI",
    "information security tender Ivory Coast government",

    # ── Matériel / Fourniture / Vente IT ──────────────────────────────────────
    "appel d'offres fourniture matériel informatique Côte d'Ivoire",
    "fourniture ordinateurs imprimantes marché public Abidjan",
    "appel d'offres équipements informatiques gouvernement CI",
    "tender supply computers equipment Ivory Coast",
    "appel d'offres acquisition serveurs stockage CI",
    "fourniture matériel bureautique appel d'offres Abidjan",
    "IT hardware supply tender West Africa 2026",
    "appel d'offres tablettes smartphones institution CI",

    # ── Maintenance / Infogérance / Support ───────────────────────────────────
    "appel d'offres maintenance parc informatique Côte d'Ivoire",
    "infogérance système informatique marché public CI",
    "appel d'offres support technique helpdesk entreprise Abidjan",
    "maintenance réseau informatique appel d'offres CI 2026",
    "managed IT services tender West Africa",
    "appel d'offres tierce maintenance applicative TMA CI",
    "IT support maintenance tender Ivory Coast",
    "appel d'offres supervision monitoring réseau CI",

    # ── Électricité / Énergie / Solaire ───────────────────────────────────────
    "appel d'offres électricité Côte d'Ivoire 2026",
    "installation électrique bâtiments publics CI",
    "solar energy project tender West Africa",
    "énergie renouvelable appel d'offres Afrique francophone",
    "appel d'offres installation panneaux solaires CI",
    "électrification rurale appel d'offres Côte d'Ivoire",
    "electrical works tender Ivory Coast government",
    "appel d'offres groupes électrogènes onduleurs CI",
    "renewable energy tender West Africa 2026",
    "appel d'offres maintenance réseau électrique CI",

    # ── Sources institutionnelles CI / Afrique ────────────────────────────────
    "ANRMP Côte d'Ivoire appel d'offres informatique",
    "marchés publics Côte d'Ivoire DMP avis",
    "tenders government Ivory Coast portal 2026",
    "avis d'appel d'offres officiel Côte d'Ivoire informatique",
    "public procurement Africa IT tenders 2026",
    "opportunités marchés publics Afrique francophone IT",
    "consultation entreprises marché public Abidjan IT",
    "appel d'offres ONG organisations internationales CI",
    "tender UNDP UNICEF West Africa IT services",
    "BAD BM appel d'offres informatique Afrique de l'Ouest",
]

def scheduled_search():
    import datetime
    print(f"\n[SCHEDULER] ⏰ {datetime.datetime.now().strftime('%H:%M:%S')}")
    all_new = []
    for q in SEARCH_QUERIES:
        found = search_tenders(q)
        all_new.extend(found)
    if all_new:
        print(f"[SCHEDULER] {len(all_new)} nouveaux AO → notifications")
        summary = notify_new_tenders(all_new)
        print(f"[SCHEDULER] Envoyés : {summary}")
    else:
        print("[SCHEDULER] Aucun nouvel AO.")
    notify_urgent_tenders()

# TEST : toutes les 5 min
# scheduler.add_job(
#     func=scheduled_search, trigger="interval",
#     minutes=5, id="auto_search", max_instances=1,
# )

# PROD : lundi–vendredi à 07h, 12h, 17h  ← décommenter en production
scheduler.add_job(
    func=scheduled_search, trigger="cron",
    day_of_week="mon-fri", hour="7,12,17", minute=0,
    id="search_semaine", max_instances=1,
)
scheduler.add_job(
    func=notify_urgent_tenders, trigger="cron",
    day_of_week="sat,sun", hour=9, minute=0,
    id="search_weekend", max_instances=1,
)

scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ── Démarrage ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    init_users()
    print("\n[APP] Dashboard  → http://localhost:5000")
    print("[APP] Test email → http://localhost:5000/api/test-email")
    print("[APP] Scheduler  → toutes les 5 minutes\n")
    app.run(debug=True, port=5000, use_reloader=False)