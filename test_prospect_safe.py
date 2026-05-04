"""
test_prospect_safe.py — TEST SÉCURISÉ ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Envoie UNIQUEMENT à aymarbly559@gmail.com
Évite de déranger les autres membres de l'équipe.
"""
import sys, os, json
sys.path.insert(0, "A:\\Projets\\scrapp-infosoluces")
from dotenv import load_dotenv
load_dotenv("A:\\Projets\\scrapp-infosoluces\\.env")

TEST_EMAIL = "aymarbly559@gmail.com"  # ← Seul destinataire

print("=" * 60)
print("🧪 TEST PROSPECTION SÉCURISÉ")
print(f"📧 Destinataire UNIQUE : {TEST_EMAIL}")
print("⚠️  Aucun email ne sera envoyé à l'équipe")
print("=" * 60)

# ─── 1. Initialisation ────────────────────────────────────────
from models.database import init_db, save_tender, get_all_tenders
from models.prospect_data import init_prospects, create_prospect, get_prospects_to_send
from utils.llm_prospect import generate_prospect_email, score_prospect_quality
from utils.notifier import _send_email

init_db()
init_prospects()

# ─── 2. Créer un AO test avec contact (si pas déjà fait) ──────
test_tenders = get_all_tenders()
has_contact_test = any(
    t.get("contact") and t["contact"].get("organisation") == "Mairie de Cocody"
    for t in test_tenders
)

if not has_contact_test:
    print("\n📌 Injection d'un AO test avec contact...")
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
    save_tender(test_tender)
    print("✅ AO test injecté")
else:
    print("\n📌 AO test déjà existant dans la base")

# ─── 3. Générer email de prospection via DeepSeek ─────────────
print("\n🤖 Génération email prospection via DeepSeek...")
tenders = get_all_tenders()
candidate = None
for t in tenders:
    if t.get("contact") and t["contact"].get("email"):
        candidate = t
        break

if not candidate:
    print("❌ Aucun AO avec contact trouvé")
    sys.exit(1)

print(f"   Source: {candidate['contact']['organisation']}")
email = generate_prospect_email(candidate)
subject = email.get("subject", "")
print(f"   Sujet: {subject}")
print(f"   Confiance: {email.get('confidence', 0)}/100")
print(f"   Raison: {email.get('reasoning', '')[:100]}")

# ─── 4. Envoyer UNIQUEMENT à aymarbly559@gmail.com ────────────
print(f"\n📤 Envoi vers {TEST_EMAIL} (SEUL destinataire)...")
test_subject = f"[TEST PROSPECTION] {subject}"
html = email.get("body_html", "")
text = email.get("body_text", "")

ok = _send_email(TEST_EMAIL, test_subject, html)
if ok:
    print(f"✅ EMAIL ENVOYÉ avec succès !")
    print(f"   Sujet: {test_subject}")
    print(f"\n📬 Vérifie ta boîte mail : {TEST_EMAIL}")
    print(f"   (si pas dans la boîte de réception, regarde les SPAMS)")
else:
    print(f"❌ Échec envoi vers {TEST_EMAIL}")

# ─── 5. Afficher un résumé ─────────────────────────────────────
print("\n" + "=" * 60)
print("✅ TEST TERMINÉ — Résumé")
print("=" * 60)
print(f"📧 Testé avec : {TEST_EMAIL}")
print(f"📍 Aucun email envoyé à l'équipe")
print(f"📋 Commande pour relancer : python test_prospect_safe.py")
print("=" * 60)
