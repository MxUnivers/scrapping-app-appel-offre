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
• Téléphonie sur IP (VoIP, solutions de communication unifiée)
• Business Intelligence & Intelligence Artificielle (BI, IA, datascience)
• Audit de systèmes d'information (diagnostic, optimisation, conformité)

Réalisations clés :
• Portail marchés publics pour l'ANRMP
• Solution de e-gouvernement pour plusieurs mairies d'Abidjan
• Infrastructure réseau pour 3 hôpitaux publics
• Maintenance IT de 5 PME ivoiriennes (contrats pluriannuels)

🌐 Site web  : https://infosoluces.ci
📧 Email     : contact@infosoluces.ci
📞 Téléphone : +225 27 22 52 40 88
📱 Mobile    : +225 01 73 73 73 97
📍 Adresse   : Rue des Bambous, Cocody Danga, Abidjan
🔵 Facebook  : https://www.facebook.com/Infosoluces/
💼 LinkedIn  : https://ci.linkedin.com/company/infosoluces
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
- Termine par une signature professionnelle INFOSOLUCES contenant les liens Facebook et LinkedIn
- Sois concis : max 3-4 paragraphes
- ADAPTE ta proposition au budget du client (sans mentionner le montant EXACT dans le texte)
  - Si budget faible → propose solution progressive/par phase
  - Si budget élevé → propose solution complète clé en main
- IMPORTANT : Ne mentionne JAMAIS le montant exact du budget dans le corps de l'email. Reste vague ("solution adaptée à votre budget", "devis personnalisé") sans donner de chiffres.

Tu réponds UNIQUEMENT avec un objet JSON valide :
{{
  "subject": "Objet de l'email (max 80 car.)",
  "body_text": "Corps de l'email en TEXTE BRUT uniquement. Signature avec les coordonnées INFOSOLUCES.",
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

Informations supplémentaires (À USAGE INTERNE — ne pas divulguer le budget exact) :
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


# ── Template HTML orange & bleu ───────────────────────────────────────────────

INFO_LOGO_URL = "https://res.cloudinary.com/dsgd2h3dx/image/upload/v1772619527/logo_rfv6lb.jpg"

def _build_prospect_html(body_text: str, subject: str) -> str:
    """
    Enveloppe le texte brut dans un template HTML moderne
    avec les couleurs INFOSOLUCES (orange #f0a500, bleu #0066cc)
    et un style IA/professionnel.
    """
    # Convertir les sauts de ligne en paragraphes HTML stylés
    paragraphs = body_text.strip().split("\n\n")
    body_html = "".join(
        f"""<p style="margin:0 0 16px 0;line-height:1.8;font-size:15px;
color:#2c2c2c;font-family:Georgia,'Times New Roman',serif;">{p.strip()}</p>"""
        for p in paragraphs if p.strip()
    )

    return f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
</head>
<body style="
  margin:0; padding:0;
  background:linear-gradient(135deg,#e8edf5 0%,#f5f0e8 100%);
  font-family:'Segoe UI',Arial,Helvetica,sans-serif;
">

<table width="100%" cellpadding="0" cellspacing="0" style="background:transparent;">
  <tr>
    <td align="center" style="padding:30px 12px;">

      <!-- ▸ CARTE PRINCIPALE ──────────────────────────────────── -->
      <table width="620" cellpadding="0" cellspacing="0" style="
        max-width:620px; width:100%;
        background:#ffffff;
        border-radius:16px;
        overflow:hidden;
        box-shadow:0 8px 40px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06);
      ">

        <!-- ▸ BANDE DÉGRADÉE HAUT ----------------------------- -->
        <tr>
          <td style="
            background:linear-gradient(135deg,#0d0f14 0%,#1a1d2e 40%,#0066cc 100%);
            padding:6px 0;
          ">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="width:8px;background:#f0a500;"></td>
                <td style="padding:0;"></td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- ▸ EN-TÊTE ORANGE + LOGO --------------------------- -->
        <tr>
          <td style="
            background:linear-gradient(135deg,#f0a500 0%,#e89200 60%,#d48000 100%);
            padding:0;
          ">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="padding:18px 28px;">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <!-- Logo -->
                      <td style="width:52px;">
                        <img src="{INFO_LOGO_URL}"
                             alt="INFOSOLUCES"
                             width="48" height="48"
                             style="border-radius:10px;display:block;
                                    box-shadow:0 2px 8px rgba(0,0,0,0.15);"
                             onerror="this.style.display='none'">
                      </td>
                      <!-- Nom entreprise -->
                      <td style="padding-left:14px;">
                        <span style="
                          color:#0d0f14;font-size:20px;font-weight:800;
                          letter-spacing:-0.3px;text-shadow:0 1px 2px rgba(255,255,255,0.15);
                        ">INFOSOLUCES</span>
                        <span style="
                          color:#3a2a0a;font-size:11px;display:block;
                          opacity:0.8;font-weight:500;
                        ">Solutions IT &bull; Abidjan, C&ocirc;te d'Ivoire</span>
                      </td>
                      <!-- Badge -->
                      <td align="right" style="vertical-align:middle;">
                        <span style="
                          background:#0066cc;color:#ffffff;
                          font-size:10px;padding:5px 14px;
                          border-radius:20px;font-weight:700;
                          letter-spacing:1px;text-transform:uppercase;
                          box-shadow:0 2px 6px rgba(0,102,204,0.3);
                        ">Proposition</span>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- ▸ BARRE ACCENT BLEU --------------------------------- -->
        <tr>
          <td style="
            background:linear-gradient(90deg,#0066cc 0%,#3399ff 50%,#0066cc 100%);
            height:5px;
          "></td>
        </tr>

        <!-- ▸ CORPS DE L'EMAIL ───────────────────────────────── -->
        <tr>
          <td style="padding:32px 34px 20px;background:#ffffff;">
            {body_html}
          </td>
        </tr>

        <!-- ▸ SÉPARATEUR ÉLÉGANT --------------------------------- -->
        <tr>
          <td style="padding:0 34px 24px;background:#ffffff;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="border-bottom:1px solid #eee;"></td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- ▸ BOUTONS CTA --------------------------------------- -->
        <tr>
          <td style="padding:0 34px 28px;background:#ffffff;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td align="center">
                  <table cellpadding="0" cellspacing="0">
                    <tr>
                      <!-- Bouton principal : Contact -->
                      <td style="
                        background:linear-gradient(135deg,#0066cc,#0052a3);
                        border-radius:8px;padding:0;
                        box-shadow:0 4px 12px rgba(0,102,204,0.35);
                      ">
                        <a href="https://infosoluces.ci/contact"
                           style="
                            display:inline-block;padding:13px 36px;
                            color:#ffffff;font-size:14px;font-weight:700;
                            text-decoration:none;border-radius:8px;
                            letter-spacing:0.3px;
                        ">
                          Nous contacter
                        </a>
                      </td>
                      <td width="14"></td>
                      <!-- Bouton secondaire : Site -->
                      <td style="
                        background:#0d0f14;border-radius:8px;padding:0;
                        box-shadow:0 4px 12px rgba(13,15,20,0.25);
                      ">
                        <a href="https://infosoluces.ci"
                           style="
                            display:inline-block;padding:13px 28px;
                            color:#f0a500;font-size:14px;font-weight:700;
                            text-decoration:none;border-radius:8px;
                            letter-spacing:0.3px;
                        ">
                          Site web
                        </a>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- ▸ FOOTER COORDONNÉES + RÉSEAUX ---------------------- -->
        <tr>
          <td style="
            background:linear-gradient(135deg,#0d0f14 0%,#1a1d2e 100%);
            padding:22px 30px;
          ">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <!-- Coordonnées -->
                <td style="font-size:12px;color:#888;line-height:1.6;">
                  <strong style="color:#f0a500;font-size:13px;">INFOSOLUCES SARL</strong><br>
                  Rue des Bambous, Cocody Danga, Abidjan<br>
                  T&eacute;l&nbsp;: +225 27 22 52 40 88
                  &nbsp;|&nbsp; Mobile : +225 01 73 73 73 97<br>
                  <a href="mailto:contact@infosoluces.ci"
                     style="color:#f0a500;text-decoration:none;">
                    contact@infosoluces.ci
                  </a>
                </td>
                <!-- Icônes réseaux sociaux avec badges colorés -->
                <td align="right" style="vertical-align:top;">
                  <!-- Site web -->
                  <table cellpadding="0" cellspacing="0" style="display:inline-block;margin-bottom:6px;">
                    <tr>
                      <td style="background:#f0a500;border-radius:4px 0 0 4px;padding:4px 6px;font-size:11px;">🌐</td>
                      <td style="background:rgba(240,165,0,0.15);border-radius:0 4px 4px 0;padding:4px 8px;">
                        <a href="https://infosoluces.ci"
                           style="color:#f0a500;text-decoration:none;font-size:11px;font-weight:600;">
                          Site web
                        </a>
                      </td>
                    </tr>
                  </table>
                  <br>
                  <!-- Facebook -->
                  <table cellpadding="0" cellspacing="0" style="display:inline-block;margin-bottom:6px;">
                    <tr>
                      <td style="background:#1877f2;border-radius:4px 0 0 4px;padding:4px 6px;font-size:11px;">f</td>
                      <td style="background:rgba(24,119,242,0.15);border-radius:0 4px 4px 0;padding:4px 8px;">
                        <a href="https://www.facebook.com/Infosoluces/"
                           style="color:#1877f2;text-decoration:none;font-size:11px;font-weight:600;">
                          Facebook
                        </a>
                      </td>
                    </tr>
                  </table>
                  <br>
                  <!-- LinkedIn -->
                  <table cellpadding="0" cellspacing="0" style="display:inline-block;">
                    <tr>
                      <td style="background:#0a66c2;border-radius:4px 0 0 4px;padding:4px 6px;font-size:11px;color:#fff;font-weight:bold;">in</td>
                      <td style="background:rgba(10,102,194,0.15);border-radius:0 4px 4px 0;padding:4px 8px;">
                        <a href="https://ci.linkedin.com/company/infosoluces"
                           style="color:#0a66c2;text-decoration:none;font-size:11px;font-weight:600;">
                          LinkedIn
                        </a>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- ▸ FIN DE LA CARTE ─────────────────────────────────── -->
      </table>

      <!-- ▸ MENTION LÉGALE MINI ──────────────────────────────── -->
      <table width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;margin-top:12px;">
        <tr>
          <td style="
            font-size:10px;color:#999;text-align:center;padding:8px 10px;
            line-height:1.5;
          ">
            Cet email vous a &eacute;t&eacute; envoy&eacute; par
            <strong style="color:#777;">INFOSOLUCES SARL</strong> dans le cadre
            d'une prospection commerciale.
          </td>
        </tr>
      </table>

    </td>
  </tr>
</table>

</body>
</html>'''


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
    result = _parse_json(raw)

    # Envelopper le body_text dans le template HTML orange & bleu
    body_text = result.get("body_text", "")
    subject   = result.get("subject", "")
    result["body_html"] = _build_prospect_html(body_text, subject)

    return result


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
