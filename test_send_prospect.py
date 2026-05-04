"""
test_send_prospect.py — Injection AO test + génération + envoi email
"""
import sys, os, json
sys.path.insert(0, "A:\\Projets\\scrapp-infosoluces")
from dotenv import load_dotenv
load_dotenv("A:\\Projets\\scrapp-infosoluces\\.env")

from models.database import init_db, save_tender
from models.prospect_data import init_prospects
from utils.llm_prospect import generate_prospect_email, score_prospect_quality
from utils.notifier import _send_email

init_db()
init_prospects()

# 1. Creer un AO test avec contact
test_tender = {
    "title": "Appel d'offres pour la digitalisation des services municipaux de Cocody",
    "sector": "Developpement Web",
    "bu": "Developpement",
    "type": "ao",
    "budget": "85 000 000",
    "budget_devise": "FCFA",
    "deadline": "2026-06-15",
    "localisation": "Abidjan, Cote d Ivoire",
    "description": "La mairie de Cocody cherche un prestataire pour developper un portail web de services municipaux en ligne avec gestion des demandes, paiement en ligne, tableau de bord.",
    "score": 85,
    "score_reason": "AO IT actif en CI",
    "source_url": "https://anrmp.ci/appel-offres-digitalisation-cocody-2026",
    "contact": {
        "organisation": "Mairie de Cocody",
        "responsable": "Koffi N Guessan",
        "poste": "Directeur des Systemes d Information",
        "email": "dsi@mairiecocody.ci",
        "telephone": "+225 27 22 44 55 66",
        "adresse": "Mairie de Cocody, Abidjan",
    },
    "pertinent_infosoluces": True,
}

is_new = save_tender(test_tender)
if is_new:
    print("1. AO test sauvegarde dans la DB ✓")
else:
    print("1. AO test deja existant (doublon)")

# 2. Generer email de prospection
print("2. Generation email prospection via DeepSeek...", flush=True)
email = generate_prospect_email(test_tender)
subject = email.get("subject", "")
print(f"   Sujet: {subject}")
print(f"   Confiance: {email.get('confidence', 0)}/100")

# 3. Envoyer vers aymarbly559@gmail.com
to_email = "aymarbly559@gmail.com"
test_subject = f"[TEST PROSPECTION] {subject}"
html = email.get("body_html", "")
print(f"3. Envoi vers {to_email}...", flush=True)
ok = _send_email(to_email, test_subject, html)
if ok:
    print("   ✅ EMAIL ENVOYE avec succes !")
    print(f"   Sujet: {test_subject}")
else:
    print("   ❌ Erreur: echec envoi email")
    print(f"   SMTP_USER={os.getenv('SMTP_USER', 'NON DEFINI')}")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    print(f"   SMTP_PASSWORD defini={bool(smtp_pass)}")
