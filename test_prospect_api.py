"""test_prospect_api.py — Test du module de prospection"""
import requests, json

BASE = "http://localhost:5000"

print("=== 1. Stats générales ===")
r = requests.get(f"{BASE}/api/stats")
print(json.dumps(r.json(), indent=2))

print("\n=== 2. Derniers AO (5) ===")
r = requests.get(f"{BASE}/api/tenders?limit=5")
data = r.json()
if isinstance(data, list):
    print(f"{len(data)} AO trouvés")
    for t in data[:3]:
        c = t.get("contact", {}) or {}
        org = c.get("organisation", "-")[:25]
        email = c.get("email", "-")[:25]
        print(f"  - {t.get('title','?')[:50]} | {org} | {email}")
else:
    print(f"Total: {data.get('total',0)}")
    for t in data.get("items", [])[:3]:
        c = t.get("contact", {}) or {}
        print(f"  - {t.get('title','?')[:50]} | {c.get('organisation','-')[:25]}")

print("\n=== 3. Stats prospects ===")
r = requests.get(f"{BASE}/api/prospects/stats")
print(json.dumps(r.json(), indent=2))

print("\n=== 4. Campagnes ===")
r = requests.get(f"{BASE}/api/prospects/campaigns")
print(json.dumps(r.json(), indent=2))

print("\n✅ Tests terminés")
