"""test_doc_upload_fix.py — Test l'upload de document après correction du tempdir"""
import requests, os, tempfile

BASE = "http://127.0.0.1:5000"

# Créer un fichier test
tmp = tempfile.gettempdir()
test_path = os.path.join(tmp, "test_doc_ao_mairie.txt")
with open(test_path, "w", encoding="utf-8") as f:
    f.write("""
APPEL D'OFFRE POUR LA FOURNITURE DE MATERIEL INFORMATIQUE

La mairie de Cocody lance un appel d'offres pour la fourniture de 50 ordinateurs,
30 imprimantes et 10 serveurs pour ses services municipaux. Le projet inclut
l'installation, la configuration et la maintenance pendant 1 an.

Budget : 25 000 000 FCFA
Deadline : 30 juin 2026

Contact :
M. Kone, Direction des Achats
Email : kone@mairiecocody.ci
Tel : +225 27 22 44 55 66
    """)

print("Upload du document test...")
with open(test_path, "rb") as f:
    r = requests.post(
        f"{BASE}/api/documents/upload",
        files={"file": ("test_ao_materiel.txt", f)},
        timeout=90,
    )

print(f"Status: {r.status_code}")
data = r.json()

if r.status_code == 200:
    report = data.get("report", {})
    print(f"\nAnalyse reussie !")
    print(f"  Type: {report.get('type', '?')}")
    print(f"  Score: {report.get('score', '?')}/100")
    print(f"  Pertinent InfoSolutces: {report.get('pertinent_infosoluces', '?')}")
    print(f"  BU concernee: {report.get('bu_concernee', '?')}")
    print(f"  Emetteur: {report.get('emetteur', '?')}")
    print(f"  Resume: {report.get('resume', '?')[:150]}")
    print(f"  Recommandation: {report.get('recommandation', '?')[:150]}")
    print(f"\nNotifications envoyees: {data.get('notified', 0)}")
else:
    print(f"Erreur: {data}")

# Nettoyage
try:
    os.remove(test_path)
except:
    pass

print("\nTest termine!")
