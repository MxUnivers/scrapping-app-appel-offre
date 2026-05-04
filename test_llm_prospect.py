"""
test_llm_prospect.py — Test de génération d'email de prospection DeepSeek
"""
import sys, os, re, json
sys.path.insert(0, "A:\\Projets\\scrapp-infosoluces")

# Charger depuis .env
from dotenv import load_dotenv
load_dotenv("A:\\Projets\\scrapp-infosoluces\\.env")

from utils.llm_prospect import generate_prospect_email, score_prospect_quality

mock_tender = {
    "title": "Appel d'offres pour la digitalisation des services municipaux",
    "sector": "Développement Web",
    "bu": "Développement",
    "type": "ao",
    "budget": "85 000 000",
    "budget_devise": "FCFA",
    "deadline": "2026-06-15",
    "localisation": "Abidjan, Côte d'Ivoire",
    "description": (
        "La mairie de Cocody recherche un prestataire pour développer un portail web "
        "de services municipaux en ligne. Le projet inclut un système de gestion des "
        "demandes administratives, un paiement en ligne des taxes, et un tableau de "
        "bord pour les agents municipaux."
    ),
    "score": 85,
    "score_reason": "AO IT actif en Côte d'Ivoire, budget conséquent",
    "contact": {
        "organisation": "Mairie de Cocody",
        "responsable": "Koffi N'Guessan",
        "poste": "Directeur des Systèmes d'Information",
        "email": "dsi@mairiecocody.ci",
        "telephone": "+225 27 22 44 55 66",
        "adresse": "Mairie de Cocody, Boulevard des Martyrs, Abidjan",
    },
    "pertinent_infosoluces": True,
}

print("Evaluation qualite prospect...")
quality = score_prospect_quality(mock_tender)
print(f"Score qualite: {quality}/100")

print("\nGeneration email prospection via DeepSeek...")
print("(cette etape prend ~30s)\n")
email = generate_prospect_email(mock_tender)

print("=" * 60)
print("SUJET:", email.get("subject", ""))
print("CTA:", email.get("call_to_action", ""))
print("CONFIANCE:", email.get("confidence", 0))
print("RAISON:", email.get("reasoning", ""))
print("=" * 60)

html = email.get("body_html", "")
text = re.sub(r"<[^>]+>", " ", html)
text = re.sub(r"\s+", " ", text).strip()
print("\nCORPS (texte uniquement):")
print(text)
print("=" * 60)

# Save result to file
result = {
    "test": "ok",
    "subject": email.get("subject"),
    "confidence": email.get("confidence"),
    "call_to_action": email.get("call_to_action"),
    "reasoning": email.get("reasoning"),
    "body_text": email.get("body_text", text),
}
with open("A:\\Projets\\scrapp-infosoluces\\test_prospect_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("\nResultat sauvegarde dans test_prospect_result.json")
