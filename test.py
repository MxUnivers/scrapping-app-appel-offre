# test_email.py
import requests
import json

BASE_URL = "http://localhost:5000"
ADMIN_EMAIL = "admin@cioffres.ci"
ADMIN_PASS = "Admin123!"

def get_token():
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASS
    })
    return r.json()['data']['token']

def test_email():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    print("📧 Test 1: Email simple...")
    r = requests.post(f"{BASE_URL}/admin/emails/send-test", 
                     headers=headers, json={
                         "subject": "🧪 Test depuis script Python"
                     })
    print(f"   Résultat: {r.json()['status']}")
    
    print("📦 Test 2: Digest d'offres...")
    r = requests.post(f"{BASE_URL}/admin/emails/send-digest-test", 
                     headers=headers)
    print(f"   Résultat: {r.json()}")
    
    print("⚙️  Test 3: Changer fréquence à 5 min...")
    r = requests.post(f"{BASE_URL}/admin/emails/update-schedule", 
                     headers=headers, json={"minutes": 5})
    print(f"   Résultat: {r.json()['message']}")
    
    print("✅ Tests terminés!")

if __name__ == "__main__":
    test_email()