"""
utils/llm.py — Analyse AO avec Claude API
"""
import os, json, re
from datetime import datetime
import anthropic

CURRENT_YEAR  = datetime.now().year
CURRENT_MONTH = datetime.now().strftime("%B %Y")   # ex: "April 2026"

def _get_client():
    key = os.getenv("ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=key) if key else None

SYSTEM_PROMPT = f"""
Tu es un expert en marchés publics et appels d'offres IT en Afrique de l'Ouest.
Tu analyses des textes d'appels d'offres pour INFOSOLUCES SARL (PME ivoirienne :
développement web, ERP, maintenance informatique, réseaux).

Nous sommes en {CURRENT_MONTH}. L'année en cours est {CURRENT_YEAR}.
- Un AO est considéré "à venir" si sa deadline est après aujourd'hui.
- Un AO est "expiré" si sa deadline est avant {CURRENT_YEAR} ou déjà passée.
- Les AO sans date ou avec une date en {CURRENT_YEAR}/{CURRENT_YEAR + 1} sont prioritaires.

Tu réponds UNIQUEMENT avec un objet JSON valide, sans texte avant ou après.
""".strip()

def _build_prompt(title, url, raw_text):
    today = datetime.now().strftime("%Y-%m-%d")
    return f"""
Analyse cette page et retourne UN SEUL objet JSON (pas un tableau) :

{{
  "title": "Titre propre de l'AO (ou de la page si ce n'est pas un AO)",
  "sector": "Développement | Réseau | Sécurité | Matériel | Maintenance | Autre",
  "budget": "montant si mentionné, sinon chaîne vide",
  "deadline": "YYYY-MM-DD si trouvée, sinon chaîne vide",
  "description": "2-3 phrases résumant ce qui est demandé",
  "score": entier 0-100,
  "score_reason": "1 phrase expliquant le score"
}}

Règles de scoring (nous sommes le {today}) :
- 80-100 : vrai AO IT actif en {CURRENT_YEAR} ou {CURRENT_YEAR + 1}, parfait pour INFOSOLUCES
- 50-79  : AO IT partiellement adapté ou sans date précise
- 20-49  : page liée aux AO mais pas un AO direct, ou AO expiré avant {CURRENT_YEAR}
- 0-19   : page de navigation, accueil, conditions générales, code de conduite

Important : si la deadline trouvée est antérieure à {today}, baisser le score en dessous de 30.

URL    : {url}
Titre  : {title}
Texte  :
---
{raw_text[:4000]}
---
Réponds UNIQUEMENT avec l'objet JSON.
""".strip()

def analyze_tender(title: str, url: str, raw_text: str) -> dict:
    client = _get_client()
    if not client:
        raise RuntimeError("ANTHROPIC_API_KEY non définie dans .env")

    msg = client.messages.create(
        model      = "claude-haiku-4-5-20251001",
        max_tokens = 600,
        system     = SYSTEM_PROMPT,
        messages   = [{"role": "user", "content": _build_prompt(title, url, raw_text)}],
    )

    raw = msg.content[0].text.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"```\s*$",     "", raw).strip()

    parsed = None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group())
            except Exception:
                pass

    if parsed is None:
        raise ValueError(f"JSON invalide: {raw[:150]}")

    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else {}

    if not isinstance(parsed, dict):
        raise ValueError(f"Type inattendu: {type(parsed)}")

    return parsed