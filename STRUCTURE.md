ci_offres_aggregator/
│
├── app.py                      # Point d'entrée principal
├── config.py                   # Configuration globale
├── requirements.txt            # Toutes les dépendances
├── .env                        # Variables sensibles (MOTS DE PASSE)
├── .gitignore                  # Fichiers à ignorer
│
├── models/                     # Modèles MongoEngine
│   ├── __init__.py
│   ├── user.py                 # Modèle Utilisateur/Admin
│   ├── offre.py                # Modèle Offre/Emploi
│   └── subscription.py         # Modèle Abonnement Email
│
├── scrapers/                   # Scripts de scraping
│   ├── __init__.py
│   ├── base.py                 # Classe mère
│   ├── emploi_ci.py
│   ├── armp_ci.py
│   └── manager.py
│
├── services/                   # Services métier
│   ├── __init__.py
│   ├── email_service.py        # Envoi d'emails
│   └── auth_service.py         # Authentification
│
├── routes/                     # Routes API
│   ├── __init__.py
│   ├── api.py                  # Routes offres
│   ├── auth.py                 # Routes authentification
│   └── admin.py                # Routes administration
│
├── templates/                  # Templates emails HTML
│   ├── email_offres.html
│   └── email_welcome.html
│
├── logs/                       # Logs d'application
│   └── app.log
│
└── scripts/                    # Scripts utilitaires
    └── create_admin.py         # Créer admin par défaut