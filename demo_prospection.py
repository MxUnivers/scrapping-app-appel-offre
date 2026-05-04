"""
demo_prospection.py — Démonstration complète du module de prospection
═══════════════════════════════════════════════════════════════════
1. Génère un email de prospection personnalisé via DeepSeek
2. Applique le template orange & bleu avec logo
3. Sauvegarde le rendu HTML
4. Affiche le résumé dans la console

Usage : python demo_prospection.py
        (ou double-clic sur demo_prospection.bat)
"""
import sys, os, json
sys.path.insert(0, "A:\\Projets\\scrapp-infosoluces")
from dotenv import load_dotenv
load_dotenv("A:\\Projets\\scrapp-infosoluces\\.env")

from utils.llm_prospect import generate_prospect_email, score_prospect_quality

# ═══════════════════════════════════════════════════════════
# Données de démonstration (remplace par de vrais AO plus tard)
# ═══════════════════════════════════════════════════════════

DEMO_TENDERS = [
    # ── CAS 1 : DÉVELOPPEMENT WEB / PORTAIL ─────────────────────
    {
        "title": "Appel d'offres pour la digitalisation des services municipaux de Cocody",
        "sector": "Développement Web",
        "bu": "Développement",
        "type": "ao",
        "budget": "85 000 000",
        "budget_devise": "FCFA",
        "deadline": "2026-06-15",
        "localisation": "Abidjan, Côte d'Ivoire",
        "description": "La mairie de Cocody recherche un prestataire pour développer un portail web de services municipaux en ligne : gestion des demandes administratives, paiement en ligne des taxes, tableau de bord agents.",
        "score": 88,
        "score_reason": "AO IT actif en CI, budget conséquent, cœur de métier INFOSOLUCES",
        "source_url": "https://anrmp.ci/appel-offres-digitalisation-cocody-2026",
        "contact": {
            "organisation": "Mairie de Cocody",
            "responsable": "Koffi N'Guessan",
            "poste": "Directeur des Systèmes d'Information",
            "email": "dsi@mairiecocody.ci",
            "telephone": "+225 27 22 44 55 66",
            "adresse": "Mairie de Cocody, Boulevard des Martyrs, Abidjan",
        },
        "pertinent_infosoluces": True,
    },
    # ── CAS 2 : CYBERSÉCURITÉ / SANTÉ ──────────────────────────
    {
        "title": "Appel d'offres pour la sécurisation du réseau informatique du CHU de Treichville",
        "sector": "Cybersécurité",
        "bu": "Sécurité",
        "type": "ao",
        "budget": "45 000 000",
        "budget_devise": "FCFA",
        "deadline": "2026-07-30",
        "localisation": "Abidjan, Côte d'Ivoire",
        "description": "Le CHU de Treichville lance un appel d'offres pour la sécurisation complète de son infrastructure réseau : firewall, segmentation, antivirus centralisé, audit de sécurité et formation du personnel.",
        "score": 82,
        "score_reason": "AO cybersécurité en CI, secteur santé porteur pour INFOSOLUCES",
        "source_url": "https://anrmp.ci/appel-offres-securisation-chu-treichville",
        "contact": {
            "organisation": "CHU de Treichville",
            "responsable": "Dr Kouamé Jean-Baptiste",
            "poste": "Directeur Général",
            "email": "dg@chu-treichville.ci",
            "telephone": "+225 27 21 35 67 89",
            "adresse": "CHU de Treichville, Abidjan",
        },
        "pertinent_infosoluces": True,
    },
    # ── CAS 3 : ERP / GESTION D'ENTREPRISE ─────────────────────
    {
        "title": "Appel d'offres pour l'acquisition et le déploiement d'un ERP dans une PME industrielle à Abidjan",
        "sector": "ERP",
        "bu": "Développement",
        "type": "ao",
        "budget": "120 000 000",
        "budget_devise": "FCFA",
        "deadline": "2026-08-20",
        "localisation": "Abidjan, Côte d'Ivoire",
        "description": "Une PME industrielle basée à Yopougon recherche un intégrateur pour déployer un ERP couvrant la gestion des stocks, la comptabilité, les ressources humaines et la production. Le projet inclut la formation des équipes et la maintenance sur 2 ans.",
        "score": 90,
        "score_reason": "Projet ERP conséquent en CI, formation incluse, parfait pour le savoir-faire INFOSOLUCES",
        "source_url": "https://anrmp.ci/appel-offres-erp-pme-yopougon",
        "contact": {
            "organisation": "Société Ivoirienne de Transformation (SIT)",
            "responsable": "M. Traoré Adama",
            "poste": "Directeur Administratif et Financier",
            "email": "da.sit@pmegroupe.ci",
            "telephone": "+225 27 21 48 00 11",
            "adresse": "Zone Industrielle de Yopougon, Abidjan",
        },
        "pertinent_infosoluces": True,
    },
    # ── CAS 4 : RÉSEAU / INFRASTRUCTURE ─────────────────────────
    {
        "title": "Appel d'offres pour la mise en place d'un réseau interconnecté pour 5 agences bancaires en Côte d'Ivoire",
        "sector": "Réseau",
        "bu": "Réseau",
        "type": "ao",
        "budget": "68 000 000",
        "budget_devise": "FCFA",
        "deadline": "2026-09-01",
        "localisation": "Abidjan, Bouaké, Yamoussoukro, San-Pédro, Korhogo",
        "description": "Une banque régionale souhaite interconnecter ses 5 agences avec un réseau privé sécurisé (VPN MPLS). Le projet inclut l'équipement Cisco, la fibre optique, le câblage structuré, la téléphonie IP et la supervision centralisée.",
        "score": 85,
        "score_reason": "Projet réseau multi-sites en CI, équipements Cisco, VoIP incluse",
        "source_url": "https://anrmp.ci/appel-offres-reseau-banque-5-agences",
        "contact": {
            "organisation": "Banque Atlantique Côte d'Ivoire",
            "responsable": "M. Yao Laurent",
            "poste": "Directeur des Systèmes d'Information",
            "email": "dsi@banqueatlantique.ci",
            "telephone": "+225 27 20 33 44 55",
            "adresse": "Plateau, Avenue Noguès, Abidjan",
        },
        "pertinent_infosoluces": True,
    },
    # ── CAS 5 : INFOGÉRANCE / MAINTENANCE ───────────────────────
    {
        "title": "Appel d'offres pour l'infogérance du parc informatique d'un ministère à Abidjan",
        "sector": "Infogérance",
        "bu": "Maintenance",
        "type": "ao",
        "budget": "36 000 000",
        "budget_devise": "FCFA",
        "deadline": "2026-10-15",
        "localisation": "Abidjan, Plateau, Côte d'Ivoire",
        "description": "Un ministère lance un contrat d'infogérance de 12 mois pour la maintenance de 350 postes de travail, 15 serveurs, l'assistance helpdesk (8h-18h), la gestion des licences et la sécurité du SI. Le prestataire devra assurer la continuité de service avec des SLA stricts.",
        "score": 78,
        "score_reason": "Contrat infogérance annuel, parc conséquent, secteur public stratégique",
        "source_url": "https://anrmp.ci/appel-offres-infogerance-ministere",
        "contact": {
            "organisation": "Ministère de l'Économie Numérique",
            "responsable": "M. N'Dri Germain",
            "poste": "Directeur des Ressources Informatiques",
            "email": "dri@economie-numerique.gouv.ci",
            "telephone": "+225 27 20 31 00 22",
            "adresse": "Plateau, Tour D, Abidjan",
        },
        "pertinent_infosoluces": True,
    },
]

# ═══════════════════════════════════════════════════════════
# Démo
# ═══════════════════════════════════════════════════════════

print("=" * 65)
print("  🚀 DÉMONSTRATION PROSPECTION INFOSOLUCES")
print("  Génération d'emails B2B personnalisés via DeepSeek")
print("=" * 65)

for i, tender in enumerate(DEMO_TENDERS, 1):
    contact = tender.get("contact", {}) or {}
    print(f"\n{'─' * 65}")
    print(f"  📋 CAS {i} : {contact.get('organisation', 'Inconnue')}")
    print(f"     {tender['title'][:55]}...")
    print(f"     Budget : {tender.get('budget', 'N/R')} {tender.get('budget_devise', '')}  |  Deadline : {tender.get('deadline', 'N/R')}")
    print(f"     Contact : {contact.get('responsable', 'N/R')} · {contact.get('email', 'N/R')}")

    quality = score_prospect_quality(tender)
    print(f"\n     📊 Qualité prospect : {quality}/100")

    print(f"\n     🤖 Génération email DeepSeek en cours...")
    email = generate_prospect_email(tender)

    subject = email.get("subject", "")
    cta = email.get("call_to_action", "")
    confidence = email.get("confidence", 0)
    reasoning = email.get("reasoning", "")[:120]

    print(f"     ✅ Email généré !")
    print(f"     📧 Sujet : {subject}")
    print(f"     🎯 CTA   : {cta}")
    print(f"     💯 Score : {confidence}/100")

    # Sauvegarder le HTML
    filename = f"demo_prospection_{i}.html"
    filepath = os.path.join("A:\\Projets\\scrapp-infosoluces", filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(email.get("body_html", ""))

    print(f"     💾 Fichier : {filename}")

    # Résumé en texte clair
    body_text = email.get("body_text", "")
    print(f"\n     📝 Aperçu du message :")
    for line in body_text.strip().split("\n")[:6]:
        print(f"        {line}")
    print()

# Résumé final
print("=" * 65)
print("  ✅ DÉMO TERMINÉE")
print(f"  {len(DEMO_TENDERS)} emails générés")
print()
print("  📁 Fichiers créés dans A:\\Projets\\scrapp-infosoluces :")
for i in range(1, len(DEMO_TENDERS) + 1):
    print(f"     - demo_prospection_{i}.html  (ouvre dans le navigateur)")
print()
print("  💡 Ouvre les fichiers HTML dans ton navigateur")
print("     pour voir le rendu final avec le logo et les couleurs !")
print("=" * 65)
