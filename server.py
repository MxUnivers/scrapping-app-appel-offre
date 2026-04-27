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
    from utils.notifier import _send_email, _build_email_html, CATEGORIES

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

SEARCH_QUERIES = {

    # ===========================================================
    # 1. APPELS D'OFFRES IT — Côte d'Ivoire (cœur de métier)
    # ===========================================================
    "ao_dev": [
        "appel d'offres développement logiciel Côte d'Ivoire 2026",
        "appel d'offres développement application web Abidjan 2026",
        "appel d'offres développement application mobile Côte d'Ivoire 2026",
        "appel d'offres ERP système gestion Côte d'Ivoire 2026",
        "appel d'offres digitalisation administration Côte d'Ivoire 2026",
        "appel d'offres plateforme e-gouvernement Côte d'Ivoire 2026",
        "appel d'offres site internet marché public Abidjan 2026",
        "software development tender Ivory Coast 2026",
    ],

    "ao_reseau": [
        "appel d'offres réseau informatique Côte d'Ivoire 2026",
        "appel d'offres installation fibre optique Côte d'Ivoire 2026",
        "appel d'offres déploiement Wi-Fi entreprise publique Abidjan 2026",
        "appel d'offres hébergement serveur datacenter Côte d'Ivoire 2026",
        "appel d'offres virtualisation infrastructure informatique CI 2026",
        "network infrastructure tender Ivory Coast 2026",
        "cloud computing services tender Côte d'Ivoire 2026",
    ],

    "ao_securite": [
        "appel d'offres sécurité informatique Côte d'Ivoire 2026",
        "appel d'offres audit sécurité système informatique CI 2026",
        "appel d'offres pare-feu firewall antivirus Côte d'Ivoire 2026",
        "appel d'offres SIEM SOC sécurité réseau CI 2026",
        "cybersecurity tender Ivory Coast 2026",
        "information security audit tender Abidjan 2026",
    ],

    "ao_materiel": [
        "appel d'offres fourniture matériel informatique Côte d'Ivoire 2026",
        "appel d'offres fourniture ordinateurs imprimantes marché public Abidjan 2026",
        "appel d'offres acquisition serveurs stockage Côte d'Ivoire 2026",
        "appel d'offres tablettes smartphones institution CI 2026",
        "IT hardware supply tender Ivory Coast 2026",
    ],

    "ao_maintenance": [
        "appel d'offres maintenance parc informatique Côte d'Ivoire 2026",
        "appel d'offres infogérance système informatique CI 2026",
        "appel d'offres support technique helpdesk Abidjan 2026",
        "appel d'offres tierce maintenance applicative TMA CI 2026",
        "managed IT services tender Ivory Coast 2026",
    ],

    "ao_electricite": [
        "appel d'offres électricité installation bâtiments publics Côte d'Ivoire 2026",
        "appel d'offres installation panneaux solaires Côte d'Ivoire 2026",
        "appel d'offres électrification rurale Côte d'Ivoire 2026",
        "appel d'offres groupes électrogènes onduleurs CI 2026",
        "solar energy electrical tender Ivory Coast 2026",
        "renewable energy project tender Côte d'Ivoire 2026",
    ],

    "ao_institutionnel": [
        "ANRMP Côte d'Ivoire appel d'offres informatique 2026",
        "marchés publics Côte d'Ivoire DMP avis informatique 2026",
        "avis appel d'offres officiel Côte d'Ivoire informatique 2026",
        "appel d'offres ONG organisations internationales Côte d'Ivoire IT 2026",
        "tender UNDP UNICEF Ivory Coast IT services 2026",
        "BAD BM appel d'offres informatique Côte d'Ivoire 2026",
        "public procurement Ivory Coast IT 2026",
    ],

    # ===========================================================
    # 2. VEILLE ENTREPRISES — Nouvelles sociétés CI
    # ===========================================================
    "entreprises_ci": [
        "nouvelles entreprises informatique Côte d'Ivoire 2026",
        "startup tech Abidjan lancée 2026",
        "nouvelle société IT créée Côte d'Ivoire 2026",
        "entreprise informatique Abidjan ouverture 2026",
        "tech company launched Ivory Coast 2026",
        "registre commerce entreprise informatique Abidjan 2026",
        "financement startup technologique Côte d'Ivoire 2026",
    ],

    # ===========================================================
    # 3. SALONS & ÉVÉNEMENTS — Côte d'Ivoire & Afrique
    # ===========================================================
    "salons_evenements": [
        "salon informatique technologie Abidjan 2026",
        "forum numérique Côte d'Ivoire 2026",
        "conférence IT Afrique de l'Ouest 2026",
        "tech event West Africa 2026",
        "Africa tech summit Abidjan 2026",
        "salon électronique réseau informatique CI 2026",
        "journée numérique Côte d'Ivoire 2026",
        "hackathon innovation Abidjan 2026",
        "AFRICA CEO Forum technologie 2026",
    ],

    # ===========================================================
    # 4. CERTIFICATIONS MICROSOFT — Nouvelles & Mises à jour
    # ===========================================================
    "certifications_microsoft": [
        "nouvelle certification Microsoft 2026",
        "Microsoft Azure certification update 2026",
        "Microsoft 365 certification nouveau 2026",
        "Microsoft Certified Partner Afrique 2026",
        "Microsoft certification retraite remplacement 2026",
        "AZ-900 AZ-104 AZ-305 Microsoft update 2026",
        "Microsoft fundamentals associate expert 2026",
        "Microsoft certification learning path 2026",
    ],

    # ===========================================================
    # 5. CERTIFICATIONS FORTINET — Nouvelles & Mises à jour
    # ===========================================================
    "certifications_fortinet": [
        "nouvelle certification Fortinet 2026",
        "Fortinet NSE update 2026",
        "Fortinet NSE4 NSE7 NSE8 certification 2026",
        "Fortinet certified professional update 2026",
        "Fortinet partner certification Afrique 2026",
        "FortiGate certification nouvelle version 2026",
    ],

    # ===========================================================
    # 6. CERTIFICATIONS RÉSEAU — Cisco, CompTIA, etc.
    # ===========================================================
    "certifications_reseau": [
        "nouvelle certification Cisco CCNA CCNP 2026",
        "Cisco certification update 2026",
        "CompTIA Network+ Security+ update 2026",
        "AWS certification cloud 2026",
        "Google Cloud certification 2026",
        "certification réseau sécurité informatique 2026",
        "CCIE CCDE Cisco expert 2026",
        "Juniper certification JNCIA JNCIS 2026",
    ],

    # ===========================================================
    # 7. INTELLIGENCE ARTIFICIELLE — Postes & Publications CI
    # ===========================================================
    "ia_postes_publications": [
        "recrutement intelligence artificielle Côte d'Ivoire 2026",
        "offre emploi data scientist Abidjan 2026",
        "offre emploi machine learning Côte d'Ivoire 2026",
        "poste ingénieur IA Afrique de l'Ouest 2026",
        "AI job opening Ivory Coast 2026",
        "publication recherche IA Afrique francophone 2026",
        "ChatGPT Gemini déploiement entreprise Côte d'Ivoire 2026",
        "transformation IA entreprise Abidjan 2026",
        "formation intelligence artificielle Côte d'Ivoire 2026",
    ],

    # ===========================================================
    # 8. MICROSOFT — Levées de fonds, Croissance, Performance
    # ===========================================================
    "microsoft_croissance": [
        "Microsoft Africa croissance investissement 2026",
        "Microsoft Afrique de l'Ouest expansion 2026",
        "Microsoft Côte d'Ivoire partenariat 2026",
        "Microsoft Azure datacenter Africa 2026",
        "Microsoft résultats financiers croissance 2026",
        "Microsoft partner network Afrique 2026",
        "Microsoft Teams Copilot déploiement Afrique 2026",
    ],

    # ===========================================================
    # 9. FORMATIONS IT — Tous secteurs CI
    # ===========================================================
    "formations_it": [
        "formation informatique Côte d'Ivoire 2026",
        "formation réseau Cisco Fortinet Abidjan 2026",
        "formation cybersécurité Côte d'Ivoire 2026",
        "formation développement web mobile Abidjan 2026",
        "formation infogérance système Côte d'Ivoire 2026",
        "formation électricité industrielle Abidjan 2026",
        "formation cloud computing Côte d'Ivoire 2026",
        "formation DevOps Python Java Côte d'Ivoire 2026",
        "programme formation IT Afrique francophone 2026",
        "bootcamp développement informatique Abidjan 2026",
    ],
}

# Aplatir toutes les requêtes pour le scheduler
ALL_QUERIES = [q for queries in SEARCH_QUERIES.values() for q in queries]


def scheduled_search():
    import datetime
    print(f"\n[SCHEDULER] ⏰ {datetime.datetime.now().strftime('%H:%M:%S')} — {len(ALL_QUERIES)} requêtes")
    all_new = []
    for q in ALL_QUERIES:
        try:
            found = search_tenders(q)
            all_new.extend(found)
        except Exception as e:
            print(f"[SCHEDULER] ⚠️  Erreur requête '{q[:40]}...': {e}")

    if all_new:
        print(f"[SCHEDULER] ✅ {len(all_new)} nouveaux résultats → notifications")
        summary = notify_new_tenders(all_new)
        print(f"[SCHEDULER] Envoyés : {summary}")
    else:
        print("[SCHEDULER] ℹ️  Aucun nouveau résultat.")

    notify_urgent_tenders()


# TEST : toutes les 5 min (décommenter en dev)
# scheduler.add_job(
#     func=scheduled_search, trigger="interval",
#     minutes=5, id="auto_search", max_instances=1,
# )

# PROD : lundi–vendredi à 07h, 12h, 17h
scheduler.add_job(
    func=scheduled_search, trigger="cron",
    day_of_week="mon-fri", hour="7,12,17", minute=0,
    id="search_semaine", max_instances=1,
)

# WEEKEND : rappels AO urgents seulement
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
    print(f"\n[APP] Dashboard   → http://localhost:5000")
    print(f"[APP] Test email  → http://localhost:5000/api/test-email")
    print(f"[APP] Requêtes    → {len(ALL_QUERIES)} au total")
    print(f"[APP] Catégories  → {list(SEARCH_QUERIES.keys())}\n")
    app.run(debug=True, port=5000, use_reloader=False)