from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from flask_cors import CORS
from scrapers.web_search import search_tenders
from models.database import init_db, get_all_tenders, get_stats
from models.users    import init_users, get_all_users
from utils.notifier  import notify_new_tenders, notify_urgent_tenders
import atexit
import os

app = Flask(__name__)
CORS(app)
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
            found = search_tenders(q, pre_filter=_is_worth_analyzing)
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
# scheduler.add_job(
#     func=scheduled_search, trigger="interval",
#     minutes=5, id="auto_search", max_instances=1,
# )

# PROD : lundi–vendredi à 07h, 12h, 17h
# scheduler.add_job(
#     func=scheduled_search, trigger="cron",
#     day_of_week="mon-fri", hour="7,12,17", minute=0,
#     id="search_semaine", max_instances=1,
# )

# WEEKEND : rappels AO urgents seulement
# scheduler.add_job(
#     func=notify_urgent_tenders, trigger="cron",
#     day_of_week="sat,sun", hour=9, minute=0,
#     id="search_weekend", max_instances=1,
# )

# scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ── Démarrage ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    init_users()
    print(f"\n[APP] Dashboard   → http://localhost:5000")
    print(f"[APP] Test email  → http://localhost:5000/api/test-email")
    print(f"[APP] Requêtes    → {len(ALL_QUERIES)} au total")
    print(f"[APP] Filtre CI   → {len(KEYWORDS_CI)} mots-clés (pré-filtre DeepSeek)")
    print(f"[APP] Catégories  → {list(SEARCH_QUERIES.keys())}\n")
    app.run(debug=True, port=5000, use_reloader=True)