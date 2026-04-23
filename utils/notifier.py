"""
utils/notifier.py
─────────────────
1. Analyse l'AO avec le LLM pour déterminer la/les catégorie(s)
2. Route vers les bons destinataires selon les 4 catégories INFOSOLUCES
3. Envoie les emails via SMTP
4. Garde un historique pour éviter les doublons
"""

import os, smtplib, json, re
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from datetime             import datetime, timedelta
from models.users         import CATEGORIES, log_notification, was_notified

# ── Config SMTP ───────────────────────────────────────────────────────────────

SMTP_HOST     = os.getenv("SMTP_HOST",     "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER",     "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM     = os.getenv("SMTP_FROM",     SMTP_USER)
EMAIL_ENABLED = bool(SMTP_USER and SMTP_PASSWORD)


# ── Classificateur LLM ────────────────────────────────────────────────────────

CLASSIFY_PROMPT = """
Tu es un classificateur d'appels d'offres pour INFOSOLUCES SARL (PME IT à Abidjan).

Voici les 4 catégories :

CAT1 — Développement / ERP / Infrastructure IT
  (développement web/mobile, application, ERP, logiciel, plateforme, système, cloud, infrastructure)

CAT2 — Réseau / Cloud / Sécurité / Marchés IT
  (réseau informatique, cybersécurité, cloud computing, VPN, firewall, datacenter, marchés IT)

CAT3 — Infogérance / Électronique / Réparation / Électricité / AO généraux
  (infogérance, réparation, électricité, énergie solaire, antivirus, fibre optique, maintenance électronique)

CAT4 — Vente matériel / Maintenance / Support
  (fourniture matériel informatique, ordinateurs, imprimantes, maintenance réseau, support technique, LAN/WAN)

Analyse cet appel d'offres et retourne UNIQUEMENT un JSON :
{
  "categories": ["CAT1", "CAT3"],   // liste des catégories applicables (1 à 4)
  "raison": "explication courte"
}

AO à analyser :
Titre       : {title}
Secteur     : {sector}
Description : {description}
""".strip()


def _classify_tender_llm(tender: dict) -> list[str]:
    """Utilise Claude pour déterminer les catégories de routage."""
    try:
        import anthropic
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            return _classify_tender_fallback(tender)

        client = anthropic.Anthropic(api_key=key)
        prompt = CLASSIFY_PROMPT.format(
            title       = tender.get("title", ""),
            sector      = tender.get("sector", ""),
            description = tender.get("description", ""),
        )
        msg = client.messages.create(
            model      = "claude-haiku-4-5-20251001",
            max_tokens = 200,
            messages   = [{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"```\s*$",     "", raw).strip()
        data = json.loads(raw)
        cats = data.get("categories", [])
        valid = [c for c in cats if c in CATEGORIES]
        print(f"  [LLM CLASS] {valid} — {data.get('raison','')[:60]}")
        return valid if valid else _classify_tender_fallback(tender)
    except Exception as e:
        print(f"  [LLM CLASS] Erreur: {e} → fallback règles")
        return _classify_tender_fallback(tender)


def _classify_tender_fallback(tender: dict) -> list[str]:
    """Classifie par mots-clés si le LLM échoue."""
    text = (
        tender.get("title","") + " " +
        tender.get("sector","") + " " +
        tender.get("description","")
    ).lower()

    matched = []
    for cat_id, cat in CATEGORIES.items():
        if any(kw.lower() in text for kw in cat["keywords"]):
            matched.append(cat_id)

    return matched if matched else ["CAT1", "CAT3"]  # défaut : dev + AO généraux


# ── Construction email ────────────────────────────────────────────────────────

def _build_email_html(recipient_name: str, tender: dict,
                      category: dict, urgent: bool = False) -> str:
    urgence = f"""
      <div style="background:#fff3cd;border-left:4px solid #e74c3c;padding:10px 14px;
                  margin-bottom:16px;font-size:13px;border-radius:4px;">
        🚨 <strong>URGENT</strong> — Deadline : <strong>{tender.get('deadline','')}</strong>
      </div>
    """ if urgent else ""

    deadline_style = "color:#e74c3c;font-weight:bold" if urgent else "color:#444"

    return f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;border-radius:8px;overflow:hidden;border:1px solid #e8e8e8;">

  <!-- Header -->
  <div style="background:#0d0f14;padding:18px 28px;display:flex;align-items:center;">
    <span style="color:#f0a500;font-size:20px;font-weight:bold;">AO·TRACKER</span>
    <span style="color:#6b7090;font-size:12px;margin-left:10px;">INFOSOLUCES SARL</span>
    <span style="margin-left:auto;background:#1a1e2a;color:#6b9fff;font-size:11px;
                 padding:3px 10px;border-radius:12px;">{category['label']}</span>
  </div>

  <!-- Corps -->
  <div style="padding:24px 28px;background:#ffffff;">
    <p style="color:#333;font-size:14px;margin:0 0 6px;">
      Bonjour <strong>{recipient_name}</strong>,
    </p>
    <p style="color:#666;font-size:13px;margin:0 0 20px;">
      Un nouvel appel d'offres correspond à votre domaine
      (<strong>{tender.get('sector','')}</strong>).
    </p>

    {urgence}

    <!-- Carte AO -->
    <div style="background:#f7f8fc;border-radius:8px;padding:18px;margin-bottom:20px;
                border-left:4px solid #f0a500;">
      <h2 style="font-size:15px;color:#0d0f14;margin:0 0 10px;line-height:1.4;">
        {tender.get('title','')}
      </h2>
      <p style="font-size:13px;color:#555;margin:0 0 14px;line-height:1.6;">
        {tender.get('description','')}
      </p>
      <table style="width:100%;font-size:12px;color:#666;border-collapse:collapse;">
        <tr>
          <td style="padding:5px 12px 5px 0;width:25%;color:#999;">Secteur</td>
          <td style="padding:5px 0;font-weight:600;color:#333;">{tender.get('sector','—')}</td>
          <td style="padding:5px 12px 5px 20px;width:20%;color:#999;">Score</td>
          <td style="padding:5px 0;color:#f0a500;font-weight:bold;">{tender.get('score',0)}/100</td>
        </tr>
        <tr>
          <td style="padding:5px 12px 5px 0;color:#999;">Budget</td>
          <td style="padding:5px 0;font-weight:600;color:#333;">{tender.get('budget','—') or '—'}</td>
          <td style="padding:5px 12px 5px 20px;color:#999;">Deadline</td>
          <td style="padding:5px 0;{deadline_style};">{tender.get('deadline','—') or '—'}</td>
        </tr>
      </table>
    </div>

    <a href="{tender.get('source_url','#')}"
       style="display:inline-block;background:#f0a500;color:#0d0f14;padding:11px 24px;
              border-radius:6px;font-size:13px;font-weight:bold;text-decoration:none;">
      Voir l'appel d'offres →
    </a>
  </div>

  <!-- Footer -->
  <div style="padding:12px 28px;background:#f4f6fb;font-size:11px;color:#aaa;text-align:center;">
    AO Tracker · INFOSOLUCES SARL · Abidjan, Côte d'Ivoire &nbsp;|&nbsp;
    {datetime.utcnow().strftime('%d/%m/%Y à %H:%M')} UTC
  </div>
</div>
"""


# ── Envoi SMTP ────────────────────────────────────────────────────────────────

def _send_email(to: str, subject: str, html: str) -> bool:
    if not EMAIL_ENABLED:
        print(f"    [EMAIL] Simulation → {to}")
        return True
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = SMTP_FROM
        msg["To"]      = to
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(SMTP_USER, SMTP_PASSWORD)
            srv.sendmail(SMTP_FROM, to, msg.as_string())
        return True
    except Exception as e:
        print(f"    [EMAIL] ✗ {to} : {e}")
        return False


# ── Dispatcher principal ──────────────────────────────────────────────────────

def notify_new_tenders(tenders: list[dict]) -> dict:
    """
    Pour chaque AO :
    1. LLM détermine les catégories (CAT1..CAT4)
    2. Collecte les destinataires uniques des catégories matchées
    3. Envoie un email à chacun (anti-doublon par tender_id)
    """
    today     = datetime.utcnow().strftime("%Y-%m-%d")
    in_7_days = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")
    summary   = {}

    for tender in tenders:
        tender_id = str(tender.get("id") or tender.get("hash", ""))
        deadline  = tender.get("deadline", "")
        urgent    = bool(deadline and today <= deadline <= in_7_days)

        print(f"\n  [NOTIF] AO : {tender.get('title','')[:50]}")

        # 1. Classification LLM
        cat_ids = _classify_tender_llm(tender)
        if not cat_ids:
            print(f"  [NOTIF] Aucune catégorie matchée — ignoré")
            continue

        # 2. Collecter destinataires uniques toutes catégories confondues
        recipients = {}  # email → (name, category)
        for cat_id in cat_ids:
            cat = CATEGORIES[cat_id]
            for email in cat["emails"]:
                if email not in recipients:
                    name = email.split("@")[0].replace(".", " ").title()
                    recipients[email] = {"name": name, "category": cat}

        print(f"  [NOTIF] Catégories: {cat_ids} → {len(recipients)} destinataires")

        # 3. Envoi
        for email, info in recipients.items():
            # Anti-doublon : clé = email + tender_id
            notif_key = f"{email}_{tender_id}"
            if was_notified(notif_key, tender_id):
                print(f"    ⟳ Déjà notifié : {email}")
                continue

            subject = (
                f"{'🚨 URGENT — ' if urgent else ''}"
                f"[{info['category']['label']}] "
                f"{tender.get('title','')[:45]}"
            )
            html = _build_email_html(info["name"], tender, info["category"], urgent)
            ok   = _send_email(email, subject, html)

            if ok:
                log_notification(notif_key, tender_id, "email")
                summary[email] = summary.get(email, 0) + 1
                print(f"    ✓ Envoyé → {email}")

    return summary


def notify_urgent_tenders() -> dict:
    """Notification dédiée aux AO urgents (deadline < 7 jours)."""
    from models.database import get_all_tenders
    today     = datetime.utcnow().strftime("%Y-%m-%d")
    in_7_days = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d")
    urgent = [
        t for t in get_all_tenders()
        if t.get("deadline")
        and today <= t["deadline"] <= in_7_days
        and t.get("status") not in ("Soumis", "Rejeté")
    ]
    if urgent:
        print(f"[NOTIF] {len(urgent)} AO urgents")
        return notify_new_tenders(urgent)
    return {}