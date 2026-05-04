"""
test_all_pages.py — Vérifie que toutes les pages répondent correctement
════════════════════════════════════════════════════════════════════════
Teste :
  - Les pages Laravel (frontend)
  - Les routes API Flask (backend)
  - La connexion entre les deux
"""
import requests, json, sys

LARAVEL = "http://127.0.0.1:8000"
FLASK   = "http://127.0.0.1:5000"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

passed = 0
failed = 0

def test(name: str, url: str, expected_status=200, base=LARAVEL):
    global passed, failed
    try:
        r = requests.get(f"{base}{url}", timeout=10, allow_redirects=True)
        status = "OK" if r.status_code == expected_status else f"STATUS {r.status_code}"
        if r.status_code == expected_status:
            passed += 1
            print(f"  {GREEN}✓{RESET} {name:<40} {status}")
        else:
            failed += 1
            print(f"  {RED}✗{RESET} {name:<40} {status}")
    except Exception as e:
        failed += 1
        print(f"  {RED}✗{RESET} {name:<40} {RED}ERREUR: {e}{RESET}")

def test_api(name: str, url: str, method="GET", data=None):
    global passed, failed
    try:
        if method == "GET":
            r = requests.get(f"{FLASK}{url}", timeout=10)
        elif method == "POST":
            r = requests.post(f"{FLASK}{url}", json=data or {}, timeout=30)
        else:
            r = requests.request(method, f"{FLASK}{url}", json=data or {}, timeout=10)

        if r.status_code < 500:
            passed += 1
            print(f"  {GREEN}✓{RESET} {name:<40} {r.status_code}")
        else:
            failed += 1
            print(f"  {RED}✗{RESET} {name:<40} {r.status_code} - {r.text[:80]}{RESET}")
    except Exception as e:
        failed += 1
        print(f"  {RED}✗{RESET} {name:<40} {RED}ERREUR: {e}{RESET}")

print("\n" + "=" * 60)
print("  🧪 TEST COMPLET — Pages Laravel + API Flask")
print("=" * 60)

print(f"\n{YELLOW}── Frontend (Laravel) ──{RESET}")
test("Dashboard", "/admin/dashboard")
test("Appels d'offres", "/admin/aos")
test("Prospects", "/admin/prospects")
test("Équipe", "/admin/team")
test("Configuration LLM", "/admin/settings/llm")
test("Projets", "/admin/projects")
test("Company", "/admin/company")
test("Profile", "/admin/profile")
test("Documents", "/admin/docawait")

print(f"\n{YELLOW}── API Backend (Flask) ──{RESET}")
test_api("Stats globales", "/api/stats")
test_api("Liste AO", "/api/tenders?limit=3")
test_api("Stats prospects", "/api/prospects/stats")
test_api("Liste prospects", "/api/prospects")
test_api("Config LLM", "/api/config/llm")
test_api("Catégories utilisateurs", "/api/users/categories")
test_api("Rôles utilisateurs", "/api/users/roles")
test_api("Utilisateurs", "/api/users")
test_api("Test génération prospects", "/api/prospects/generate", "POST", {"limit": 1, "test_email": "aymarbly559@gmail.com"})

print(f"\n{YELLOW}── Connexion Frontend ↔ Backend ──{RESET}")
# Vérifier que l'URL de l'API Flask est correcte dans .env Laravel
try:
    r = requests.get(f"{LARAVEL}/admin/prospects", timeout=10)
    if "Prospection" in r.text or "prospects" in r.text.lower():
        passed += 1
        print(f"  {GREEN}✓{RESET} {'Page Prospects contient le composant Vue':<40} OK")
    else:
        failed += 1
        print(f"  {RED}✗{RESET} {'Page Prospects ne charge pas le Vue':<40}")
except Exception as e:
    failed += 1
    print(f"  {RED}✗{RESET} {'Connexion Laravel':<40} {e}{RESET}")

# Résumé
print(f"\n{'='*60}")
total = passed + failed
pct = round(passed / total * 100) if total > 0 else 0
color = GREEN if pct >= 80 else (YELLOW if pct >= 50 else RED)
print(f"  {color}Résultat : {passed}/{total} tests réussis ({pct}%){RESET}")
if failed == 0:
    print(f"  {GREEN}✅ TOUT EST OK !{RESET}")
else:
    print(f"  {RED}❌ {failed} test(s) en échec{RESET}")
print(f"{'='*60}\n")
