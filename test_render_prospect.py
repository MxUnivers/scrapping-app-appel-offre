"""
test_render_prospect.py — Génère l'email de prospection et sauvegarde en HTML visualisable
"""
import sys, os
sys.path.insert(0, "A:\\Projets\\scrapp-infosoluces")
from dotenv import load_dotenv
load_dotenv("A:\\Projets\\scrapp-infosoluces\\.env")

from utils.llm_prospect import generate_prospect_email

mock_tender = {
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

print("Generation email DeepSeek...")
email = generate_prospect_email(mock_tender)

html = email.get("body_html", "")
subject = email.get("subject", "")
cta = email.get("call_to_action", "")
confidence = email.get("confidence", 0)
reasoning = email.get("reasoning", "")

full_html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="margin:0;padding:20px;background:#f0f0f0;font-family:Arial,Helvetica,sans-serif;">

<div style="max-width:620px;margin:20px auto;background:#ffffff;border-radius:10px;overflow:hidden;border:1px solid #ddd;box-shadow:0 2px 12px rgba(0,0,0,0.08);">

  <!-- Header -->
  <div style="background:#0d0f14;padding:18px 28px;">
    <span style="color:#f0a500;font-size:20px;font-weight:bold;">AO·TRACKER</span>
    <span style="color:#6b7090;font-size:12px;margin-left:10px;">INFOSOLUCES SARL</span>
    <span style="float:right;background:#f0a500;color:#0d0f14;font-size:11px;padding:3px 12px;border-radius:12px;font-weight:bold;">TEST</span>
  </div>

  <!-- Corps -->
  <div style="padding:28px;">
    {html}
  </div>

  <!-- Footer -->
  <div style="padding:14px 28px;background:#f4f6fb;font-size:11px;color:#888;text-align:center;border-top:1px solid #e8e8e8;">
    INFOSOLUCES SARL · Abidjan, Côte d'Ivoire<br>
    contact@infosoluces.ci
  </div>

</div>

<!-- Debug info -->
<div style="max-width:620px;margin:10px auto;padding:15px;background:#f9f9f9;border-radius:8px;border:1px solid #ddd;font-size:12px;color:#555;">
  <p><strong>Informations de debug :</strong></p>
  <table style="width:100%;border-collapse:collapse;">
    <tr><td style="padding:3px 8px;color:#888;">Sujet</td><td style="padding:3px 8px;">{subject}</td></tr>
    <tr><td style="padding:3px 8px;color:#888;">CTA</td><td style="padding:3px 8px;">{cta}</td></tr>
    <tr><td style="padding:3px 8px;color:#888;">Confiance</td><td style="padding:3px 8px;">{confidence}/100</td></tr>
    <tr><td style="padding:3px 8px;color:#888;">Stratégie</td><td style="padding:3px 8px;">{reasoning[:200]}</td></tr>
  </table>
</div>

</body>
</html>"""

output_path = "A:\\Projets\\scrapp-infosoluces\\apercu_prospection.html"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(full_html)

print(f"Fichier cree : apercu_prospection.html")
print(f"Chemin complet : {output_path}")
print(f"\nSujet     : {subject}")
print(f"CTA       : {cta}")
print(f"Confiance : {confidence}/100")
print(f"Strategie : {reasoning[:150]}")
print(f"\n✅ Ouvre le fichier dans ton navigateur pour voir le rendu!")
