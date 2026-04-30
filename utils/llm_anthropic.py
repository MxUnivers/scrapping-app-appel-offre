"""
utils/llm.py — Analyse AO + Veille IT avec Claude API
"""
import os, json, re
from datetime import datetime
import anthropic

CURRENT_YEAR  = datetime.now().year
CURRENT_MONTH = datetime.now().strftime("%B %Y")

def _get_client():
    key = os.getenv("ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=key) if key else None

# =========================================================
# SYSTEM PROMPT — Expert AO + Veille IT Côte d'Ivoire
# =========================================================
SYSTEM_PROMPT = f"""
Tu es un expert en marchés publics, appels d'offres IT et veille technologique
en Afrique de l'Ouest, spécialisé Côte d'Ivoire.

Tu analyses des pages web pour INFOSOLUCES SARL (PME ivoirienne spécialisée en :
développement web/mobile, ERP, maintenance informatique, réseaux, cybersécurité,
infogérance, électricité industrielle).

Nous sommes en {CURRENT_MONTH}. L'année en cours est {CURRENT_YEAR}.

Règles importantes :
- Tu te concentres UNIQUEMENT sur la Côte d'Ivoire et l'Afrique de l'Ouest.
- Un AO est "actif" si sa deadline est après aujourd'hui ou inconnue.
- Un AO est "expiré" si sa deadline est clairement passée.
- Tu extrais le BUDGET si mentionné (en FCFA, EUR, USD ou toute devise).
- Tu lis et résumes les documents PDF/Word si leur contenu est fourni.
- Tu identifies la BU (Business Unit) concernée.
- Tu extrais les CONTACTS : nom du responsable/patron, poste, téléphone, email,
  adresse, site web, et tous les liens réseaux sociaux trouvés (LinkedIn, Twitter,
  Facebook, etc.) pour la structure ET pour le responsable personnellement.

Tu réponds UNIQUEMENT avec un objet JSON valide, sans texte avant ou après.
""".strip()

# =========================================================
# PROMPT PRINCIPAL — AO + Veille
# =========================================================
def _build_prompt(title: str, url: str, raw_text: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return f"""
Analyse cette page et retourne UN SEUL objet JSON :

{{
  "type": "ao | entreprise | salon | certification | ia | formation | microsoft | autre",
  "title": "Titre propre et complet",
  "bu": "Développement | Réseau | Sécurité | Matériel | Maintenance | Électricité | Veille | Autre",
  "sector": "sous-secteur précis (ex: ERP, Fibre optique, NSE4, Data Science...)",
  "budget": "montant EXACT si mentionné (ex: 45 000 000 FCFA), sinon chaîne vide",
  "budget_devise": "FCFA | EUR | USD | autre | vide",
  "deadline": "YYYY-MM-DD si trouvée, sinon chaîne vide",
  "localisation": "ville ou pays mentionné (ex: Abidjan, Côte d'Ivoire)",
  "description": "3-4 phrases résumant précisément ce qui est demandé ou l'info clé",
  "document_summary": "résumé du document joint si PDF/Word détecté, sinon chaîne vide",

  "contact": {{
    "organisation":   "nom de la structure / entreprise / organisme émetteur",
    "responsable":    "nom complet du responsable / DG / directeur / patron si trouvé",
    "poste":          "titre du poste (ex: DG, PDG, Directeur des achats, Chef projet)",
    "telephone":      "numéro de téléphone si trouvé, sinon vide",
    "email":          "adresse email de contact si trouvée, sinon vide",
    "adresse":        "adresse physique si trouvée, sinon vide",
    "site_web":       "URL du site officiel si trouvé, sinon vide",
    "linkedin":       "URL profil LinkedIn du responsable ou de la structure, sinon vide",
    "twitter":        "URL Twitter/X du responsable ou de la structure, sinon vide",
    "facebook":       "URL Facebook si trouvé, sinon vide",
    "autres_reseaux": "autres réseaux sociaux trouvés (Instagram, YouTube, etc.)"
  }},

  "score": entier 0-100,
  "score_reason": "1 phrase expliquant le score",
  "pertinent_infosoluces": true/false
}}

Règles de scoring (nous sommes le {today}) :
- 80-100 : AO IT actif en {CURRENT_YEAR}/{CURRENT_YEAR+1}, parfait pour INFOSOLUCES CI
- 60-79  : AO IT partiellement adapté, ou veille très utile (certification, salon, IA)
- 40-59  : information utile mais indirecte (formation, entreprise concurrente)
- 20-39  : peu pertinent ou AO expiré avant {CURRENT_YEAR}
- 0-19   : page de navigation, accueil, conditions générales

Si deadline < {today} → score maximum 25.
Si hors Côte d'Ivoire/Afrique de l'Ouest → score maximum 40.

URL    : {url}
Titre  : {title}
Texte  :
---
{raw_text[:5000]}
---
Réponds UNIQUEMENT avec l'objet JSON.
""".strip()

# =========================================================
# ANALYSE PRINCIPALE
# =========================================================
def analyze_tender(title: str, url: str, raw_text: str) -> dict:
    client = _get_client()
    if not client:
        raise RuntimeError("ANTHROPIC_API_KEY non définie dans .env")

    msg = client.messages.create(
        model      = "claude-haiku-4-5-20251001",
        max_tokens = 800,
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


# =========================================================
# LECTURE DE DOCUMENTS (PDF / Word)
# =========================================================
def analyze_document(title: str, url: str, doc_text: str) -> dict:
    """
    Analyse un document PDF ou Word extrait en texte.
    Retourne les mêmes champs que analyze_tender + document_summary complet.
    """
    client = _get_client()
    if not client:
        raise RuntimeError("ANTHROPIC_API_KEY non définie dans .env")

    prompt = f"""
Tu as reçu le contenu d'un document (PDF ou Word) lié à un appel d'offres
ou une information de veille en Côte d'Ivoire.

Retourne UN SEUL objet JSON :
{{
  "type": "ao | entreprise | salon | certification | ia | formation | microsoft | autre",
  "title": "Titre officiel du document",
  "bu": "Développement | Réseau | Sécurité | Matériel | Maintenance | Électricité | Veille | Autre",
  "sector": "sous-secteur précis",
  "budget": "montant EXACT si mentionné, sinon vide",
  "budget_devise": "FCFA | EUR | USD | autre | vide",
  "deadline": "YYYY-MM-DD si trouvée, sinon vide",
  "localisation": "Abidjan / Côte d'Ivoire / autre",
  "description": "Résumé détaillé du document en 4-5 phrases",
  "document_summary": "Points clés du document : exigences techniques, critères, livrables",
  "requirements": ["liste", "des", "exigences", "principales"],

  "contact": {{
    "organisation":   "nom de la structure émettrice du document",
    "responsable":    "nom du signataire / responsable / DG / directeur si mentionné",
    "poste":          "titre du poste (DG, PDG, Directeur des achats, Chef projet...)",
    "telephone":      "téléphone si trouvé, sinon vide",
    "email":          "email de contact si trouvé, sinon vide",
    "adresse":        "adresse physique si trouvée, sinon vide",
    "site_web":       "URL site officiel si trouvé, sinon vide",
    "linkedin":       "URL LinkedIn responsable ou structure, sinon vide",
    "twitter":        "URL Twitter/X, sinon vide",
    "facebook":       "URL Facebook, sinon vide",
    "autres_reseaux": "autres réseaux trouvés, sinon vide"
  }},

  "score": entier 0-100,
  "score_reason": "explication du score",
  "pertinent_infosoluces": true/false
}}

URL      : {url}
Titre    : {title}
Document :
---
{doc_text[:6000]}
---
Réponds UNIQUEMENT avec l'objet JSON.
""".strip()

    msg = client.messages.create(
        model      = "claude-haiku-4-5-20251001",
        max_tokens = 1000,
        system     = SYSTEM_PROMPT,
        messages   = [{"role": "user", "content": prompt}],
    )

    raw = msg.content[0].text.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"```\s*$",     "", raw).strip()

    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return {"error": "parsing_failed", "raw": raw[:200]}