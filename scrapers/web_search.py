"""
scrapers/web_search.py  — AO Tracker INFOSOLUCES
Stratégies (cascade) : SerpAPI → DDGS → Bing → Sites directs
Fix IPv4 inclus pour réseaux IPv6-only.
"""

import os, re, time, random, socket, requests
from bs4 import BeautifulSoup
from utils.llm import analyze_tender
from models.database import save_tender

# ── Force IPv4 globalement ────────────────────────────────────────────────────
_orig_create = None
try:
    from urllib3.util.connection import create_connection as _orig_create
    import urllib3.util.connection as _conn

    def _force_ipv4(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                    source_address=None, socket_options=None):
        host, port = address
        addrs = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        if addrs:
            return _orig_create((addrs[0][4][0], port), timeout, source_address, socket_options)
        return _orig_create(address, timeout, source_address, socket_options)

    _conn.create_connection = _force_ipv4
except Exception:
    pass

# ── User-Agents ───────────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
]

def _h():
    return {
        "User-Agent":      random.choice(USER_AGENTS),
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept":          "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection":      "keep-alive",
        "Referer":         "https://www.google.com/",
    }

# ── 1. SerpAPI ────────────────────────────────────────────────────────────────
def _search_serpapi(query, n=10):
    key = os.getenv("SERPAPI_KEY")
    if not key:
        return []
    try:
        r = requests.get("https://serpapi.com/search",
            params={"q": query, "api_key": key, "num": n, "hl": "fr", "gl": "ci"},
            timeout=15)
        return [{"url": x["link"], "title": x["title"]}
                for x in r.json().get("organic_results", []) if "link" in x]
    except Exception as e:
        print(f"  [SerpAPI] {e}"); return []

# ── 2. DDGS ───────────────────────────────────────────────────────────────────
def _search_ddgs(query, n=10):
    try:
        from ddgs import DDGS
        with DDGS() as d:
            return [{"url": r["href"], "title": r["title"]}
                    for r in d.text(query, max_results=n)]
    except ImportError:
        print("  [DDGS] Non installé → pip install ddgs"); return []
    except Exception as e:
        print(f"  [DDGS] {e}"); return []

# ── 3. Bing scraping ──────────────────────────────────────────────────────────
def _search_bing(query, n=10):
    try:
        s = requests.Session()
        s.headers.update(_h())
        s.get("https://www.bing.com", timeout=8)
        time.sleep(0.8)
        resp = s.get("https://www.bing.com/search",
                     params={"q": query, "count": n, "setlang": "fr"}, timeout=15)
        if resp.status_code != 200:
            print(f"  [Bing] HTTP {resp.status_code}"); return []
        soup = BeautifulSoup(resp.text, "html.parser")
        results, seen = [], set()
        # Essai de plusieurs sélecteurs (Bing change régulièrement)
        for sel in ["li.b_algo h2 a", "li.b_algo a[href]", "h2 a[href]", ".b_title a"]:
            for a in soup.select(sel):
                href = a.get("href","")
                if (href.startswith("http") and "bing.com" not in href
                        and "microsoft.com" not in href and href not in seen):
                    t = a.get_text(strip=True)
                    if t:
                        results.append({"url": href, "title": t})
                        seen.add(href)
            if results:
                break
        return results[:n]
    except Exception as e:
        print(f"  [Bing] {e}"); return []

# ── 4. Sites directs ──────────────────────────────────────────────────────────
def _scrape(name, url, base):
    try:
        r = requests.get(url, headers=_h(), timeout=15)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for a in soup.select("a[href]"):
            t = a.get_text(strip=True)
            h = a["href"]
            if len(t) > 10 and any(k in t.lower() for k in
                    ["appel","offre","marché","tender","informatique","it","logiciel"]):
                if not h.startswith("http"):
                    h = base + h
                out.append({"url": h, "title": t[:120]})
        return out[:10]
    except Exception as e:
        print(f"  [{name}] {e}"); return []

def _search_direct_sites():
    sources = [
        ("ANRMP",  "https://www.anrmp.ci/index.php/marches-publics/avis-de-marche", "https://www.anrmp.ci"),
        ("UNGM",   "https://www.ungm.org/Public/Notice?noticeType=0&topic=IT",       "https://www.ungm.org"),
        ("DevEx",  "https://www.devex.com/jobs/search?type=tender&region=west-africa","https://www.devex.com"),
    ]
    all_r = []
    for name, url, base in sources:
        r = _scrape(name, url, base)
        print(f"  [Direct] {name:<8} → {len(r)} liens")
        all_r.extend(r)
    return all_r

# ── Extraction contenu ────────────────────────────────────────────────────────
def _extract_page_text(url):
    try:
        r = requests.get(url, headers=_h(), timeout=15)
        r.raise_for_status()
        if "pdf" in r.headers.get("Content-Type","").lower() or url.lower().endswith(".pdf"):
            try:
                import io, pypdf
                reader = pypdf.PdfReader(io.BytesIO(r.content))
                return "\n".join(p.extract_text() or "" for p in reader.pages)[:8000]
            except Exception:
                return re.sub(r"[^\x20-\x7E\n]"," ",
                              r.content.decode("latin-1",errors="ignore"))[:4000]
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script","style","nav","footer","header","aside"]):
            t.decompose()
        return re.sub(r"\n{3,}","\n\n", soup.get_text(separator="\n",strip=True))[:8000]
    except Exception as e:
        print(f"    [PAGE] {url[:55]}: {e}"); return ""

# ── Filtre pertinence ─────────────────────────────────────────────────────────
KW = ["appel d'offres","tender","marché public","informatique","développement",
      "logiciel","réseau","sécurité","IT","software","web","infrastructure","cloud"]

def _relevant(text):
    t = text.lower()
    return any(k.lower() in t for k in KW)

def _dedup(items):
    seen, out = set(), []
    for i in items:
        u = i.get("url","")
        if u and u not in seen:
            seen.add(u); out.append(i)
    return out

# ── Pipeline principal ────────────────────────────────────────────────────────
def search_tenders(query, max_results=10):
    print(f"\n[SEARCH] {query}")
    urls = []

    if os.getenv("SERPAPI_KEY"):
        urls = _search_serpapi(query, max_results)
        print(f"  [SerpAPI] {len(urls)}")

    if not urls:
        urls = _search_ddgs(query, max_results)
        print(f"  [DDGS]    {len(urls)}")

    if not urls:
        urls = _search_bing(query, max_results)
        print(f"  [Bing]    {len(urls)}")

    direct = _search_direct_sites()
    urls   = _dedup(urls + direct)
    print(f"  [TOTAL]   {len(urls)} URLs uniques")

    if not urls:
        print("  ⚠ 0 résultats — lance python test_search.py pour diagnostiquer")
        return []

    saved = []
    for item in urls:
        url, title = item["url"], item.get("title", "")
        print(f"  → {url[:70]}")
        text = _extract_page_text(url)
        if not text or not _relevant(text):
            print("    ✗ Non pertinent"); continue
        try:
            structured = analyze_tender(title=title, url=url, raw_text=text)
        except Exception as e:
            print(f"    ✗ LLM: {e}")
            structured = {"title": title, "sector": "Autre", "budget": "",
                          "deadline": "", "description": text[:250], "score": 30}
        structured.update({"source_url": url, "raw_text": text})

        # Ne pas sauvegarder les pages de navigation / hors sujet
        score = int(structured.get("score", 0))
        if score < 20:
            print(f"    ✗ Score trop bas ({score}) — page ignorée")
            continue

        is_new = save_tender(structured)
        print(f"    {'✓ Nouveau' if is_new else '⟳ Doublon'}: "
              f"{structured.get('title','')[:50]} | score {score}")
        if is_new:
            saved.append(structured)
        time.sleep(random.uniform(1.2, 2.5))

    print(f"[SEARCH] {len(saved)} nouveaux AO sauvegardés\n")
    return saved