# Deployer on vps 
podman build -t scrapp-infosoluces .
 systemctl restart container-scrapp-infosoluces

# AO Tracker — INFOSOLUCES SARL

Système de surveillance automatique des appels d'offres IT (Réseau, Développement, Sécurité, Matériel).

---

## 🚀 Démarrage rapide

### 1. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 2. Configurer les clés API
```bash
cp .env.example .env
# Editer .env et renseigner ANTHROPIC_API_KEY
```

### 3. Initialiser la base et lancer
```bash
python app.py
```
→ Ouvrir http://localhost:5000

---

## 📁 Structure du projet

```
ao_tracker/
├── app.py                  # Point d'entrée Flask
├── requirements.txt
├── .env.example
├── tenders.db              # SQLite (créé automatiquement)
│
├── models/
│   └── database.py         # CRUD SQLite
│
├── scrapers/
│   └── web_search.py       # Crawling + scraping + pipeline
│
├── utils/
│   └── llm.py              # Analyse Claude API
│
└── templates/
    └── dashboard.html      # Interface web
```

---

## 🔌 API REST

| Méthode | Route | Description |
|---------|-------|-------------|
| GET | `/` | Dashboard principal |
| GET | `/api/tenders` | Liste JSON des AO (filtres: sector, status) |
| POST | `/api/search` | Lance une recherche manuelle `{"query": "..."}` |
| GET | `/api/stats` | Statistiques globales |

---

## ⚙️ Configuration (.env)

| Variable | Requis | Description |
|----------|--------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | Clé Claude API (analyse LLM) |
| `GOOGLE_CSE_KEY` | ⬜ | Google Custom Search (optionnel) |
| `GOOGLE_CSE_CX` | ⬜ | ID moteur Google CSE (optionnel) |

Sans `GOOGLE_CSE_KEY`, le système utilise DuckDuckGo automatiquement.

---

## 🔄 Recherche automatique

Le scheduler tourne toutes les **6 heures** avec ces requêtes par défaut :
- `"appel d'offres informatique Côte d'Ivoire 2025"`
- `"appel d'offres développement logiciel Abidjan"`
- `"tender IT network security Ivory Coast"`
- `"marché public informatique ANRMP CI"`