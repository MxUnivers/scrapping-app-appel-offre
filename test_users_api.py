"""test_users_api.py"""
import requests
BASE = "http://127.0.0.1:5000"

for path in ["/api/users", "/api/users/categories", "/api/users/roles"]:
    r = requests.get(BASE + path, timeout=5)
    print(f"GET {path}: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        if "items" in data:
            print(f"  -> {len(data['items'])} items")
        if "total" in data:
            print(f"  -> {data['total']} total")
        if "error" in data:
            print(f"  -> ERROR: {data['error']}")
