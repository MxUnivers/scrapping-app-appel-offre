"""
send_to_team.py — Envoie les emails de prospection à toute l'équipe
═══════════════════════════════════════════════════════════════════
1. Génère 5 emails personnalisés via DeepSeek
2. Envoie chaque email à l'équipe concernée selon sa catégorie
3. Affiche le résumé des envois
"""
import sys, os, json, time
sys.path.insert(0, "A:\\Projets\\scrapp-infosoluces")
from dotenv import load_dotenv
load_dotenv("A:\\Projets\\scrapp-infosoluces\\.env")

from utils.llm_prospect import generate_prospect_email, score_prospect_quality
from utils.notifier import _send_email
from models.users import CATEGORIES

# ═══════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════

SAFE_MODE = False  # True = envoie UNIQUEMENT à aymarbly559@gmail.com

DEMO_TENDERS = [
    {
        "title": "Digitalisation des services municipaux de Cocody",
        "sector": "Développement Web", "bu": "Développement", "type": "ao",
        "budget": "85 000 000", "budget_devise": "FCFA", "deadline": "2026-06-15",
        "localisation": "Abidjan, Côte d'Ivoire",
        "description": "Portail web de services municipaux : gestion demandes, paiement en ligne, tableau de bord agents.",
        "score": 88, "source_url": "https://anrmp.ci/appel-offres-cocody",
        "contact": {
            "organisation": "Mairie de Cocody",
            "responsable": "Koffi N'Guessan",
            "poste": "Directeur des Systèmes d'Information",
            "email": "dsi@mairiecocody.ci",
        },
        "pertinent_infosoluces": True,
    },
    {
        "title": "Sécurisation réseau CHU de Treichville",
        "sector": "Cybersécurité", "bu": "Sécurité", "type": "ao",
        "budget": "45 000 000", "budget_devise": "FCFA", "deadline": "2026-07-30",
        "localisation": "Abidjan",
        "description": "Sécurisation complète réseau : firewall, segmentation, antivirus, audit, formation.",
        "score": 82, "source_url": "https://anrmp.ci/appel-offres-chu",
        "contact": {
            "organisation": "CHU de Treichville",
            "responsable": "Dr Kouamé Jean-Baptiste",
            "poste": "Directeur Général",
            "email": "dg@chu-treichville.ci",
        },
        "pertinent_infosoluces": True,
    },
    {
        "title": "Déploiement ERP pour PME industrielle",
        "sector": "ERP", "bu": "Développement", "type": "ao",
        "budget": "120 000 000", "budget_devise": "FCFA", "deadline": "2026-08-20",
        "localisation": "Yopougon, Abidjan",
        "description": "ERP couvrant stocks, compta, RH, production + formation + maintenance 2 ans.",
        "score": 90, "source_url": "https://anrmp.ci/appel-offres-erp",
        "contact": {
            "organisation": "Société Ivoirienne de Transformation (SIT)",
            "responsable": "M. Traoré Adama",
            "poste": "Directeur Administratif et Financier",
            "email": "da.sit@pmegroupe.ci",
        },
        "pertinent_infosoluces": True,
    },
    {
        "title": "Réseau interconnecté pour 5 agences bancaires",
        "sector": "Réseau", "bu": "Réseau", "type": "ao",
        "budget": "68 000 000", "budget_devise": "FCFA", "deadline": "2026-09-01",
        "localisation": "Abidjan, Bouaké, Yamoussoukro, San-Pédro, Korhogo",
        "description": "VPN MPLS, équipements Cisco, fibre optique, câblage, VoIP, supervision centralisée.",
        "score": 85, "source_url": "https://anrmp.ci/appel-offres-banque",
        "contact": {
            "organisation": "Banque Atlantique CI",
            "responsable": "M. Yao Laurent",
            "poste": "Directeur des Systèmes d'Information",
            "email": "dsi@banqueatlantique.ci",
        },
        "pertinent_infosoluces": True,
    },
    {
        "title": "Infogérance parc informatique ministère",
        "sector": "Infogérance", "bu": "Maintenance", "type": "ao",
        "budget": "36 000 000", "budget_devise": "FCFA", "deadline": "2026-10-15",
        "localisation": "Plateau, Abidjan",
        "description": "Contrat 12 mois : 350 PC, 15 serveurs, helpdesk 8h-18h, licences, sécurité SI.",
        "score": 78, "source_url": "https://anrmp.ci/appel-offres-infogerance",
        "contact": {
            "organisation": "Ministère de l'Économie Numérique",
            "responsable": "M. N'Dri Germain",
            "poste": "Directeur des Ressources Informatiques",
            "email": "dri@economie-numerique.gouv.ci",
        },
        "pertinent_infosoluces": True,
    },
]

# ─── MAPPING BU → CATÉGORIES ÉQUIPE ─────────────────────
BU_TO_CATEGORIES = {
    "Développement": ["CAT1"],
    "Sécurité":      ["CAT2"],
    "Réseau":        ["CAT2"],
    "Maintenance":   ["CAT3", "CAT4"],
    "Veille":        ["CAT1", "CAT2", "CAT3", "CAT4"],
}

# ═══════════════════════════════════════════════════════════
# Envoi
# ═══════════════════════════════════════════════════════════

print("=" * 65)
print("  📬 ENVOI PROSPECTION À L'ÉQUIPE")
print("=" * 65)
if SAFE_MODE:
    print("  ⚠️  MODE SÉCURISÉ : envoi UNIQUEMENT à aymarbly559@gmail.com")
else:
    print("  🚀 MODE RÉEL : envoi à toute l'équipe INFOSOLUCES")
print()

sent_log = []  # Pour éviter les doublons

for i, tender in enumerate(DEMO_TENDERS, 1):
    contact = tender.get("contact", {})
    bu = tender.get("bu", "Veille")

    print(f"\n{'─' * 65}")
    print(f"  [{i}/5] {contact['organisation']}")

    # 1. Générer email
    print(f"  🤖 Génération DeepSeek...")
    email = generate_prospect_email(tender)
    subject = email.get("subject", "")
    html = email.get("body_html", "")
    cta = email.get("call_to_action", "")
    print(f"     Sujet : {subject[:70]}")

    # 2. Déterminer les catégories destinataires
    cats = BU_TO_CATEGORIES.get(bu, ["CAT1", "CAT3"])
    recipients = []
    for cat_id in cats:
        cat = CATEGORIES.get(cat_id)
        if not cat:
            continue
        for addr in cat["emails"]:
            if addr not in sent_log:
                if SAFE_MODE:
                    # Mode safe : remplacer TOUS les destinataires par aymarbly
                    addr = "aymarbly559@gmail.com"
                recipients.append(addr)
                sent_log.append(addr)

    # 3. Envoyer
    sent_count = 0
    for addr in recipients:
        ok = _send_email(addr, subject, html)
        if ok:
            sent_count += 1
            print(f"     ✓ Envoyé → {addr}")
        else:
            print(f"     ✗ Échec → {addr}")

    print(f"     ✅ {sent_count}/{len(recipients)} envoyés")
    print(f"     🎯 CTA : {cta}")

    # Pause entre chaque AO
    if i < len(DEMO_TENDERS):
        print(f"\n  ⏳ Pause 3 secondes avant le prochain...")
        time.sleep(3)

# Résumé
print()
print("=" * 65)
print("  ✅ ENVOI TERMINÉ")
unique_sent = len(set(sent_log))
print(f"  📬 {len(DEMO_TENDERS)} emails générés")
print(f"  👥 {unique_sent} destinataires contactés")
if SAFE_MODE:
    print(f"  ⚠️  Mode sécurisé → seul aymarbly559@gmail.com a reçu")
else:
    print(f"  🚀 Envoi réel à toute l'équipe")
print("=" * 65)
