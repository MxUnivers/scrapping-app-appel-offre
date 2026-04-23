"""
test_search.py — Lance ce fichier pour diagnostiquer et tester la recherche.
Usage : python test_search.py
"""
import os, sys, socket, requests
from bs4 import BeautifulSoup

print("=" * 60)
print("  AO TRACKER — Diagnostic réseau & recherche")
print("=" * 60)

# ── 1. Test connectivité IPv4/IPv6 ────────────────────────────────────────────
print("\n[1] Connectivité internet")
for host in ["google.com", "bing.com", "serpapi.com"]:
    try:
        addrs = socket.getaddrinfo(host, 443)
        ipv4 = [a[4][0] for a in addrs if a[0] == socket.AF_INET]
        ipv6 = [a[4][0] for a in addrs if a[0] == socket.AF_INET6]
        print(f"  ✓ {host:<20} IPv4: {ipv4[0] if ipv4 else '—'}  IPv6: {'oui' if ipv6 else 'non'}")
    except Exception as e:
        print(f"  ✗ {host:<20} DNS échoue: {e}")

# ── 2. Test HTTP direct ───────────────────────────────────────────────────────
print("\n[2] Requêtes HTTP")
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0"}
sites = [
    ("Google",   "https://www.google.com/search?q=appel+offres+informatique&num=5"),
    ("Bing",     "https://www.bing.com/search?q=appel+offres+informatique"),
    ("SerpAPI",  "https://serpapi.com"),
]
for name, url in sites:
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"  {name:<12} HTTP {r.status_code}  ({len(r.text):,} chars)")
    except Exception as e:
        print(f"  {name:<12} ERREUR: {e}")

# ── 3. Test extraction résultats Bing ─────────────────────────────────────────
print("\n[3] Extraction résultats Bing")
try:
    session = requests.Session()
    session.headers.update(headers)
    session.get("https://www.bing.com", timeout=8)  # cookies
    r = session.get(
        "https://www.bing.com/search",
        params={"q": "appel offres informatique Abidjan", "count": 10},
        timeout=12
    )
    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    for li in soup.select("li.b_algo h2 a"):
        href = li.get("href","")
        if href.startswith("http") and "bing.com" not in href:
            results.append({"title": li.get_text(strip=True), "url": href})
    print(f"  Trouvé : {len(results)} résultats")
    for r in results[:3]:
        print(f"    · {r['title'][:55]}")
        print(f"      {r['url'][:70]}")
except Exception as e:
    print(f"  ERREUR: {e}")

# ── 4. Test DDGS ──────────────────────────────────────────────────────────────
print("\n[4] DuckDuckGo (ddgs)")
try:
    from ddgs import DDGS
    with DDGS() as ddgs:
        results = list(ddgs.text("appel offres informatique CI", max_results=5))
    print(f"  Trouvé : {len(results)} résultats")
    for r in results[:3]:
        print(f"    · {r['title'][:55]}")
except ImportError:
    print("  ✗ ddgs non installé → pip install ddgs")
except Exception as e:
    print(f"  ✗ Erreur: {e}")

# ── 5. Test SerpAPI ───────────────────────────────────────────────────────────
print("\n[5] SerpAPI")
key = os.getenv("SERPAPI_KEY")
if not key:
    print("  ✗ SERPAPI_KEY absent dans .env")
    print("    → Créer compte gratuit sur https://serpapi.com (100 req/mois)")
else:
    try:
        r = requests.get(
            "https://serpapi.com/search",
            params={"q": "appel offres informatique", "api_key": key, "num": 5},
            timeout=15,
        )
        data = r.json()
        results = data.get("organic_results", [])
        print(f"  Trouvé : {len(results)} résultats")
        for res in results[:3]:
            print(f"    · {res.get('title','')[:55]}")
    except Exception as e:
        print(f"  ✗ Erreur: {e}")

print("\n" + "=" * 60)
print("  Résumé : copiez ce log et partagez-le si besoin")
print("=" * 60)