"""build_showcase.py — Génère la page de présentation pour l'équipe"""
import os

CASES = [
    ("Digitalisation municipale", "D\u00e9veloppement Web | 85 M FCFA", "Mairie de Cocody"),
    ("Cybers\u00e9curit\u00e9 hospitali\u00e8re", "Cybers\u00e9curit\u00e9 | 45 M FCFA", "CHU de Treichville"),
    ("ERP industriel", "ERP / Gestion | 120 M FCFA", "SIT Yopougon"),
    ("R\u00e9seau bancaire multi-sites", "R\u00e9seau / Infra | 68 M FCFA", "Banque Atlantique CI"),
    ("Infog\u00e9rance minist\u00e9rielle", "Infog\u00e9rance | 36 M FCFA", "Minist\u00e8re \u00c9con. Num\u00e9rique"),
]
ICONS = ["\U0001f3db", "\U0001f3e5", "\U0001f3ed", "\U0001f3e6", "\U0001f3d7"]
COLORS = ["#f0a500", "#e74c3c", "#2ecc71", "#3498db", "#9b59b6"]

emails_html = []
for i in range(1, 6):
    path = f"A:\\Projets\\scrapp-infosoluces\\demo_prospection_{i}.html"
    if not os.path.exists(path):
        print(f"Warning: {path} not found")
        continue
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract the inner email table (the actual email content)
    start = content.find("<table width=\"620\"")
    end = content.rfind("</body>")
    if start > 0 and end > 0:
        inner = content[start:end]
    else:
        inner = content

    title, subtitle, org = CASES[i - 1]
    icon = ICONS[i - 1]
    color = COLORS[i - 1]

    emails_html.append(f"""
    <div class="case-card" id="case{i}" style="border-left:4px solid {color};">
        <div class="case-header">
            <span class="case-icon">{icon}</span>
            <div>
                <h2 style="color:{color};">{title}</h2>
                <p class="case-meta">{subtitle} &bull; {org}</p>
            </div>
            <span class="case-num">#{i}</span>
        </div>
        <div class="email-preview">
            {inner}
        </div>
    </div>
    """)

all_emails = "\n".join(emails_html)

showcase = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>INFOSOLUCES &middot; D\u00e9mo Prospection IA</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{
    font-family:'Segoe UI',Arial,sans-serif;
    background:linear-gradient(135deg,#0d0f14 0%,#1a1d2e 100%);
    color:#fff;
    min-height:100vh;
  }}
  .hero {{
    text-align:center;
    padding:50px 20px 35px;
    background:linear-gradient(135deg,#f0a500 0%,#e89200 60%,#d48000 100%);
    color:#0d0f14;
    position:relative;
    overflow:hidden;
  }}
  .hero::after {{
    content:'';
    position:absolute;
    top:0;left:0;right:0;bottom:0;
    background:url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%230d0f14' fill-opacity='0.04'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
    pointer-events:none;
  }}
  .hero-content {{ position:relative; z-index:1; }}
  .hero-icon {{ font-size:44px; margin-bottom:10px; }}
  .hero h1 {{ font-size:30px; font-weight:800; letter-spacing:-0.5px; }}
  .hero p {{ font-size:15px; opacity:0.7; margin-top:4px; }}
  .hero .badge {{
    display:inline-block; background:#0066cc; color:#fff;
    padding:5px 20px; border-radius:20px; font-size:12px; font-weight:700;
    margin-top:12px; text-transform:uppercase; letter-spacing:1px;
    box-shadow:0 2px 8px rgba(0,102,204,0.3);
  }}
  .stats {{
    display:flex; justify-content:center; gap:30px;
    padding:18px; background:rgba(255,255,255,0.05);
    margin-top:16px; border-radius:10px; max-width:500px; margin-left:auto;margin-right:auto;
  }}
  .stat {{ text-align:center; }}
  .stat-num {{ font-size:22px; font-weight:800; color:#f0a500; }}
  .stat-label {{ font-size:11px; color:#888; }}
  .nav {{
    display:flex; justify-content:center; gap:8px;
    padding:14px 10px; flex-wrap:wrap;
    position:sticky; top:0; z-index:100;
    background:rgba(13,15,20,0.95);
    backdrop-filter:blur(12px);
    border-bottom:1px solid rgba(255,255,255,0.08);
  }}
  .nav a {{
    color:#f0a500; text-decoration:none; font-size:12px; font-weight:600;
    padding:8px 16px; border-radius:8px;
    background:rgba(240,165,0,0.08);
    transition:all 0.2s; white-space:nowrap;
  }}
  .nav a:hover {{ background:rgba(240,165,0,0.2); transform:translateY(-1px); }}
  .container {{ max-width:680px; margin:auto; padding:20px 12px; }}
  .case-card {{
    background:#151829; border-radius:12px; overflow:hidden;
    margin-bottom:24px; border:1px solid rgba(255,255,255,0.08);
    transition:transform 0.2s;
  }}
  .case-card:hover {{ transform:translateY(-2px); }}
  .case-header {{
    display:flex; align-items:center; gap:12px;
    padding:16px 20px;
    background:rgba(255,255,255,0.03);
    border-bottom:1px solid rgba(255,255,255,0.06);
    position:relative;
  }}
  .case-icon {{ font-size:28px; }}
  .case-header h2 {{ font-size:16px; font-weight:700; }}
  .case-meta {{ font-size:12px; color:#888; margin-top:2px; }}
  .case-num {{
    margin-left:auto; font-size:13px; font-weight:800;
    color:rgba(255,255,255,0.15); letter-spacing:1px;
  }}
  .email-preview {{
    background:#ffffff; color:#333;
    font-size:14px; line-height:1.6;
  }}
  .email-preview table {{ max-width:100% !important; }}
  .email-preview img {{ max-width:100% !important; height:auto; }}
  .footer {{
    text-align:center; padding:30px 20px; color:#555; font-size:12px; line-height:1.8;
  }}
  .footer strong {{ color:#f0a500; }}
  .footer .bar {{ display:inline-block; width:40px; height:2px; background:#f0a500; margin:0 10px; vertical-align:middle; }}
</style>
</head>
<body>

<div class="hero">
  <div class="hero-content">
    <div class="hero-icon">\U0001f680</div>
    <h1>Prospection B2B Automatis\u00e9e</h1>
    <p>5 emails personnalis\u00e9s g\u00e9n\u00e9r\u00e9s par DeepSeek &middot; Template orange &amp; bleu</p>
    <div class="badge">\u2699\ufe0f Propuls\u00e9 par l\u2019IA &middot; INFOSOLUCES SARL</div>
    <div class="stats">
      <div class="stat"><div class="stat-num">5</div><div class="stat-label">Cas concrets</div></div>
      <div class="stat"><div class="stat-num">100%</div><div class="stat-label">Personnalis\u00e9s IA</div></div>
      <div class="stat"><div class="stat-num">30s</div><div class="stat-label">Par email</div></div>
    </div>
  </div>
</div>

<div class="nav">
  <a href="#case1">\U0001f3db Digitalisation</a>
  <a href="#case2">\U0001f3e5 Cyber</a>
  <a href="#case3">\U0001f3ed ERP</a>
  <a href="#case4">\U0001f3e6 R\u00e9seau</a>
  <a href="#case5">\U0001f3d7 Infog\u00e9rance</a>
</div>

<div class="container">
  {all_emails}
</div>

<div class="footer">
  <span class="bar"></span>
  G\u00e9n\u00e9r\u00e9 par <strong>Spyke</strong> &middot; AO Tracker INFOSOLUCES<br>
  <span style="font-size:10px;">4 mai 2026</span>
  <span class="bar"></span>
</div>

</body>
</html>"""

with open("A:\\Projets\\scrapp-infosoluces\\showcase_equipe.html", "w", encoding="utf-8") as f:
    f.write(showcase)

print("Fichier cr\u00e9\u00e9 : showcase_equipe.html")
print("Ouvre-le dans le navigateur pour montrer \u00e0 l\u2019\u00e9quipe !")
