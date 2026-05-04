"""
utils/llm_prospect.py
─────────────────────
Génération d'emails de prospection B2B personnalisés via DeepSeek.

Pipeline :
  1. Récupère un AO / opportunité avec contact entreprise
  2. DeepSeek rédige un email sur mesure (objet + corps)
  3. Sauvegarde dans la collection "prospects"
  4. Envoi via SMTP (notifier.py)

INFOSOLUCES SARL — Abidjan, Côte d'Ivoire
"""

import os, json, re, requests
from datetime import datetime
from typing import Optional

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL   = "deepseek-chat"

# ── Profil entreprise INFOSOLUCES (injecté dans le prompt) ───────────────────

INFOSOLUCES_PROFILE = """
INFOSOLUCES SARL — PME ivoirienne basée à Abidjan, Côte d'Ivoire.

Domaines d'expertise :
• Développement web & mobile (applications sur mesure, plateformes, portails)
• ERP / Progiciels de gestion (Odoo, Sage, solutions métier)
• Réseaux & Infrastructure (LAN/WAN, fibre optique, Wi-Fi, datacenter)
• Cybersécurité (audit, firewall, SOC, PKI, ISO 27001)
• Infogérance & Maintenance (TMA, helpdesk, supervision)
• Vente matériel IT (serveurs, équipements réseau, ordinateurs)

Réalisations clés :
• Portail marchés publics pour l'ANRMP
• Solution de e-gouvernement pour plusieurs mairies d'Abidjan
• Infrastructure réseau pour 3 hôpitaux publics
• Maintenance IT de 5 PME ivoiriennes (contrats pluriannuels)

🔗 Site web  : https://infosoluces.ci
📧 Contact   : aymarbly559@gmail.com
📞 Téléphone : +225 XX XX XX XX
""".strip()

# ── Prompts LLM ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""Tu es un expert en prospection B2B dans le secteur IT en Afrique de l'Ouest.
Tu travailles pour INFOSOLUCES SARL, une PME ivoirienne spécialisée en solutions IT.

{INFOSOLUCES_PROFILE}

Règles importantes :
- Écris en FRANÇAIS professionnel mais chaleureux — on est en Afrique, pas à Paris
- Sois précis : cite le besoin spécifique de l'entreprise cible
- Ne mens pas — ne prétends pas avoir réalisé ce qui n'a pas été fait
- Propose toujours une action concrète (rendez-vous, démo, devis gratuit)
- Termine par une signature professionnelle INFOSOLUCES
- Sois concis : max 3-4 paragraphes

Tu réponds UNIQUEMENT avec un objet JSON valide :
{{
  "subject": "Objet de l'email (max 80 car.)",
  "body_html": "Corps de l'email en HTML formaté, prêt à envoyer",
  "body_text": "Version texte brut du corps (alternative si le HTML est refusé)",
  "call_to_action": "L'action concrète proposée (ex: proposition technique, démo, rendez-vous)",
  "confidence": 0-100,
  "reasoning": "Pourquoi cet angle d'approche a été choisi"
}}
""".strip()


USER_PROMPT_TEMPLATE = """
Génère un email de prospection B2B pour INFOSOLUCES SARL.

Entreprise cible :
  Nom      : {organisation}
  Secteur  : {sector}
  Projet   : {title}
  Contexte : {description}

Contact identifié :
  Responsable : {responsable}
  Poste       : {poste}
  Email       : {email_contact}
  Téléphone   : {telephone}
  Adresse     : {adresse}

Informations supplémentaires :
  Budget     : {budget}
  Deadline   : {deadline}
  Localisation : {localisation}

Type d'opportunité : {type}  (ao, entreprise, salon, certification, etc.)
BU ciblée         : {bu}

Instructions pour le ton :
- Si c'est un AO en cours → ton réactif : "Nous avons identifié votre appel d'offres..."
- Si c'est une nouvelle entreprise → ton proactif : "Nous souhaiterions vous présenter..."
- Si contact nommé → personnalise avec le nom du responsable
- Si deadline proche → mentionne l'urgence

Génère UN SEUL objet JSON comme spécifié dans le système.
""".strip()


# ── API DeepSeek ──────────────────────────────────────────────────────────────

def _get_headers():
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY non définie dans .env")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
    }


def _call_deepseek(system: str, user: str, max_tokens: int = 1200) -> str:
    """Appel générique à l'API DeepSeek — retourne le texte brut."""
    payload = {
        "model":      DEEPSEEK_MODEL,
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    }
    resp = requests.post(
        DEEPSEEK_API_URL,
        headers=_get_headers(),
        json=payload,
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _parse_json(raw: str) -> dict:
    """Nettoie et parse le JSON retourné par le LLM."""
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"```\s*$",     "", raw).strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group())
            except Exception:
                parsed = None
        else:
            parsed = None

    if parsed is None:
        raise ValueError(f"JSON invalide reçu: {raw[:200]}")
    return parsed


# ── Principale : génération d'un email de prospection ─────────────────────────

def generate_prospect_email(tender: dict) -> dict:
    """
    Génère un email de prospection personnalisé à partir d'un AO/opportunité.

    Args:
        tender: Dictionnaire de l'opportunité (format analyse_tender)

    Returns:
        Dictionnaire avec subject, body_html, body_text, call_to_action, confidence
    """
    contact = tender.get("contact", {}) or {}

    user_prompt = USER_PROMPT_TEMPLATE.format(
        organisation  = contact.get("organisation", tender.get("source_url", "Entreprise")),
        sector        = tender.get("sector", ""),
        title         = tender.get("title", ""),
        description   = tender.get("description", ""),
        responsable   = contact.get("responsable", ""),
        poste         = contact.get("poste", ""),
        email_contact = contact.get("email", ""),
        telephone     = contact.get("telephone", ""),
        adresse       = contact.get("adresse", ""),
        budget        = tender.get("budget", ""),
        deadline      = tender.get("deadline", ""),
        localisation  = tender.get("localisation", ""),
        type          = tender.get("type", "ao"),
        bu            = tender.get("bu", ""),
    )

    raw = _call_deepseek(SYSTEM_PROMPT, user_prompt, max_tokens=1200)
    return _parse_json(raw)


def generate_follow_up_email(prospect: dict, previous_email: dict) -> dict:
    """
    Génère un email de relance pour un prospect déjà contacté.

    Args:
        prospect: Document MongoDB du prospect
        previous_email: Email précédent (subject, body)

    Returns:
        Nouvel email de relance
    """
    user_prompt = f"""
Génère un email de RELANCE pour INFOSOLUCES SARL.

Prospect :
  Entreprise : {prospect.get('company_name', '')}
  Contact    : {prospect.get('contact_name', '')}
  Email      : {prospect.get('contact_email', '')}

Email précédent envoyé le {prospect.get('sent_at', 'date inconnue')} :
  Objet : {previous_email.get('subject', '')}
  Corps : {previous_email.get('body_text', '')[:500]}

Instructions pour la relance :
- Ton courtois mais professionnel
- Rappelle le contexte de l'email précédent
- Propose une alternative si pas de réponse (téléphone, LinkedIn, autre contact)
- Ne sois pas insistant — propose de la valeur ajoutée

Génère UN SEUL objet JSON :
{{
  "subject": "Objet de la relance (max 80 car.)",
  "body_html": "Corps en HTML",
  "body_text": "Version texte brut",
  "call_to_action": "Action proposée",
  "confidence": 0-100,
  "reasoning": "Stratégie de relance"
}}
""".strip()

    raw = _call_deepseek(SYSTEM_PROMPT, user_prompt, max_tokens=1200)
    return _parse_json(raw)


def score_prospect_quality(tender: dict) -> int:
    """
    Évalue la qualité d'un prospect (0-100) avant d'investir un appel LLM.

    Critères :
    - Email de contact présent → +30
    - Nom du responsable présent → +25
    - Entreprise nommée → +20
    - Téléphone présent → +15
    - Budget mentionné → +10
    """
    contact = tender.get("contact", {}) or {}
    score = 0
    if contact.get("email"):        score += 30
    if contact.get("responsable"):  score += 25
    if contact.get("organisation"): score += 20
    if contact.get("telephone"):    score += 15
    if tender.get("budget"):        score += 10

    # Bonus si plusieurs infos contact
    filled = sum(1 for v in contact.values() if v)
    if filled >= 4:
        score += 10
    elif filled >= 3:
        score += 5

    return min(score, 100)
