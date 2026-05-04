"""test_smtp.py — Vérification SMTP Gmail"""
from dotenv import load_dotenv
import os
load_dotenv("A:\\Projets\\scrapp-infosoluces\\.env")

host = os.getenv("SMTP_HOST")
port = int(os.getenv("SMTP_PORT", "587"))
user = os.getenv("SMTP_USER")
pw   = os.getenv("SMTP_PASSWORD", "")

print(f"SMTP_HOST: {host}")
print(f"SMTP_PORT: {port}")
print(f"SMTP_USER: {user}")
print(f"SMTP_PASS: longueur={len(pw)}")

print("\nTest connexion SMTP Gmail...")
import smtplib
try:
    server = smtplib.SMTP(host, port, timeout=10)
    server.ehlo()
    server.starttls()
    server.login(user, pw)
    print("Login SMTP REUSSI !")
    server.quit()
except smtplib.SMTPAuthenticationError as e:
    print(f"Erreur AUTHENTIFICATION: {e}")
    print("Cause possible: mot de passe incorrect ou mot de passe d'application Gmail requis")
except Exception as e:
    print(f"Autre erreur: {e}")
