"""test_routes_detailed.py"""
import requests, sys
BASE = "http://127.0.0.1:5000"

routes_to_test = [
    ("GET", "/api/users"),
    ("POST", "/api/users", {"full_name": "Test User", "email": "test@test.ci"}),
    ("GET", "/api/users/categories"),
    ("GET", "/api/users/roles"),
    ("GET", "/api/stats"),
    ("GET", "/api/tenders?limit=1"),
    ("GET", "/api/prospects"),
]

for test_item in routes_to_test:
    method = test_item[0]
    path = test_item[1]
    data = test_item[2] if len(test_item) > 2 else None

    try:
        if method == "GET":
            r = requests.get(BASE + path, timeout=10)
            r.raise_for_status()
            print(f"✅ {method} {path} → {r.status_code} {len(r.text)} bytes")
        elif method == "POST":
            r = requests.post(BASE + path, json=data, timeout=10)
            print(f"{'✅' if r.status_code < 400 else '❌'} {method} {path} → {r.status_code}")
            if r.status_code >= 400:
                print(f"   Response: {r.text[:200]}")
    except Exception as e:
        print(f"❌ {method} {path} → ERROR: {e}")
