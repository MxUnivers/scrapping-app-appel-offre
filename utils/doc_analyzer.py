"""
utils/doc_analyzer.py — Analyse automatique de documents
═══════════════════════════════════════════════════════════════
Pipeline :
  1. Réception d'un document (upload ou email)
  2. Extraction du texte (PDF, Word, image OCR)
  3. Analyse LLM (DeepSeek) avec prompt configurable
  4. Rapport généré + routage vers les équipes concernées
  5. Notification par email

INFOSOLUCES SARL — Abidjan, Côte d'Ivoire
"""
import os, json, re, requests, hashlib
from datetime import datetime
from typing import Optional

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL   = "deepseek-chat"

# ── Prompt par défaut pour l'analyse de documents ────────────────────────────
DEFAULT_DOC_PROMPT = """
Tu es un expert en analyse de documents pour INFOSOLUCES SARL,
une PME ivoirienne spécialisée en solutions IT (développement web/mobile,
ERP, réseaux, cybersécurité, infogérance, électricité industrielle).

Analyse le document ci-dessous et retourne UNIQUEMENT un JSON valide :
{
  "type": "ao | entreprise | salon | formation | certification | reglementation | autre",
  "titre": "Titre du document",
  "resume": "Résumé détaillé en 3-4 phrases",
  "points_cles": ["point1", "point2", "point3"],
  "pertinent_infosoluces": true/false,
  "bu_concernee": "Développement | Réseau | Sécurité | Matériel | Maintenance | Électricité | Veille | Autre",
  "secteur": "sous-secteur précis",
  "budget": "montant si mentionné, sinon vide",
  "deadline": "YYYY-MM-DD si trouvée, sinon vide",
  "emetteur": "organisation émettrice",
  "contact": {
    "nom": "",
    "poste": "",
    "email": "",
    "telephone": ""
  },
  "score": 0-100,
  "score_reason": "explication",
  "recommandation": "Que doit faire INFOSOLUCES avec ce document ?"
}
""".strip()


def _get_headers():
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY non définie")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _call_deepseek(system: str, user: str, max_tokens: int = 1500) -> str:
    """Appel générique DeepSeek."""
    payload = {
        "model": DEEPSEEK_MODEL,
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    resp = requests.post(DEEPSEEK_API_URL, headers=_get_headers(), json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _parse_json(raw: str) -> dict:
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"```\s*$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group())
    raise ValueError(f"JSON invalide: {raw[:200]}")


# ── Extraction du texte d'un document (PDF/Word/image) ───────────────────────

def extract_text_from_file(filepath: str) -> str:
    """
    Extrait le texte d'un fichier selon son extension.
    Supporte : PDF, DOCX, TXT, images (OCR)
    """
    ext = os.path.splitext(filepath)[1].lower()

    # PDF
    if ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(filepath)
            return "\n".join(p.extract_text() or "" for p in reader.pages)[:10000]
        except Exception as e:
            return f"[Erreur extraction PDF: {e}]"

    # DOCX
    elif ext == ".docx":
        try:
            from docx import Document
            doc = Document(filepath)
            return "\n".join(p.text for p in doc.paragraphs)[:10000]
        except Exception as e:
            return f"[Erreur extraction DOCX: {e}]"

    # TXT
    elif ext == ".txt":
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()[:10000]

    # Images (OCR via pytesseract)
    elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff"):
        try:
            import pytesseract
            from PIL import Image
            return pytesseract.image_to_string(Image.open(filepath))[:10000]
        except Exception as e:
            return f"[Erreur OCR: {e}]"

    return f"[Format non supporté: {ext}]"


# ── Analyse LLM du document ──────────────────────────────────────────────────

def analyze_document(
    doc_text: str,
    title: str = "Document sans titre",
    custom_prompt: str = None,
) -> dict:
    """
    Analyse un document via DeepSeek et retourne un rapport structuré.

    Args:
        doc_text: Texte extrait du document
        title: Titre du document
        custom_prompt: Prompt personnalisé (optionnel)

    Returns:
        Rapport d'analyse structuré
    """
    system = custom_prompt or DEFAULT_DOC_PROMPT
    user = f"""
Document à analyser :
Titre : {title}
Date   : {datetime.now().strftime('%Y-%m-%d')}

Contenu :
---
{doc_text[:8000]}
---

Analyse ce document et retourne le JSON comme spécifié.
"""
    raw = _call_deepseek(system, user, max_tokens=1500)
    result = _parse_json(raw)
    result["date_analyse"] = datetime.now().isoformat()
    result["titre_original"] = title

    # Hash unique pour déduplication
    h = hashlib.md5((title + doc_text[:200]).encode()).hexdigest()
    result["hash"] = h

    return result


# ── Routage du rapport vers les équipes ─────────────────────────────────────

BU_TO_RECIPIENTS = {
    "Développement": ["CAT1"],
    "Réseau":        ["CAT2"],
    "Sécurité":      ["CAT2", "CAT3"],
    "Matériel":      ["CAT4"],
    "Maintenance":   ["CAT3", "CAT4"],
    "Électricité":   ["CAT3"],
    "Veille":        ["CAT1", "CAT2", "CAT3", "CAT4"],
    "Autre":         ["CAT1"],
}

def route_document_report(report: dict) -> list[str]:
    """
    Détermine les catégories d'équipe qui doivent recevoir le rapport.
    Retourne la liste des catégories (CAT1, CAT2, etc.)
    """
    bu = report.get("bu_concernee", "Veille")
    cats = BU_TO_RECIPIENTS.get(bu, ["CAT1", "CAT3"])

    # Si pertinent uniquement pour une BU spécifique, ne notifier que celle-là
    if report.get("pertinent_infosoluces"):
        return cats
    else:
        # Peu pertinent → notifier uniquement la veille
        return ["CAT1"]


def send_document_report(report: dict):
    """
    Envoie le rapport d'analyse aux équipes concernées par email.
    """
    from models.users import CATEGORIES
    from utils.notifier import _send_email
    from models.database import get_db

    cats = route_document_report(report)
    recipients = set()

    for cat_id in cats:
        cat = CATEGORIES.get(cat_id)
        if cat:
            for email in cat.get("emails", []):
                recipients.add(email)

    # Construire l'email
    subject = f"[ANALYSE DOC] {report.get('titre', '')[:50]}"
    score = report.get("score", 0)
    pertinent = report.get("pertinent_infosoluces", False)

    badge = "✅ PERTINENT" if pertinent else "ℹ️ Information"
    html = f"""
    <div style="font-family:Arial;max-width:600px;margin:auto;">
      <div style="background:#f0a500;padding:15px;color:#0d0f14;font-weight:bold;font-size:18px;">
        📄 Analyse de document
      </div>
      <div style="padding:20px;background:#fff;border:1px solid #ddd;">
        <h2 style="color:#333;">{report.get('titre', '')}</h2>
        <p style="color:{'#27ae60' if pertinent else '#888'};font-weight:bold;">{badge} | Score: {score}/100</p>
        <p style="color:#555;line-height:1.6;">{report.get('resume', '')}</p>
        <hr>
        <p><strong>Recommandation :</strong> {report.get('recommandation', 'Aucune')}</p>
        <p style="color:#888;font-size:11px;">Analyse effectuée le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>
      </div>
    </div>
    """

    sent = []
    for email in recipients:
        ok = _send_email(email, subject, html)
        sent.append({"email": email, "sent": ok})
        print(f"  [DOC RAPPORT] {'✓' if ok else '✗'} → {email}")

    # Sauvegarder dans la base
    db = get_db()
    db["documents_analyses"].insert_one({
        **report,
        "recipients": list(recipients),
        "sent_at": datetime.utcnow(),
    })

    return sent
