import requests, sys

tests = [
    ("API Routes", "http://127.0.0.1:5000/api/routes"),
    ("Scheduler", "http://127.0.0.1:5000/api/scheduler"),
    ("Stats", "http://127.0.0.1:5000/api/stats"),
    ("Users", "http://127.0.0.1:5000/api/users"),
    ("Categories", "http://127.0.0.1:5000/api/users/categories"),
    ("Config LLM", "http://127.0.0.1:5000/api/config/llm"),
    ("Prospects", "http://127.0.0.1:5000/api/prospects"),
    ("Page Dashboard", "http://127.0.0.1:8000/admin/dashboard"),
    ("Page Prospects", "http://127.0.0.1:8000/admin/prospects"),
    ("Page Team", "http://127.0.0.1:8000/admin/team"),
    ("Page LLM Config", "http://127.0.0.1:8000/admin/settings/llm"),
    ("Page Docs", "http://127.0.0.1:8000/admin/docawait"),
]

ok = 0
for name, url in tests:
    try:
        r = requests.get(url, timeout=10, allow_redirects=True)
        if r.status_code == 200:
            print(f"  ✅ {name}")
            ok += 1
        else:
            print(f"  ❌ {name} ({r.status_code})")
    except Exception as e:
        print(f"  ❌ {name} ({e})")

print(f"\n✅ {ok}/{len(tests)} OK")
