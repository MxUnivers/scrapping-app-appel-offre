import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'votre-cle-secrete-par-defaut-changez-moi')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-changez-moi')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    
    # MongoDB
    MONGODB_SETTINGS = {
        'host': os.getenv('MONGODB_URI', 'mongodb://localhost:27017'),
        'db': os.getenv('MONGODB_DB', 'ci_offres_db'),
        'username': os.getenv('MONGODB_USER', ''),
        'password': os.getenv('MONGODB_PASS', ''),
        'authentication_source': 'admin'
    }
    
    # Email (SMTP)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', '')
    
    # Scheduler
    SCHEDULER_INTERVAL_MINUTES = int(os.getenv('SCHEDULER_INTERVAL', '10'))
    
    # Admin par défaut
    DEFAULT_ADMIN_EMAIL = os.getenv('DEFAULT_ADMIN_EMAIL', 'admin@cioffres.ci')
    DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', 'Admin123!')
    
    # Pagination
    DEFAULT_PAGE_SIZE = 200
    MAX_PAGE_SIZE = 100
        # LinkedIn
    LINKEDIN_MAX_RESULTS = int(os.getenv('LINKEDIN_MAX_RESULTS', '20'))
    LINKEDIN_DELAY_MIN = float(os.getenv('LINKEDIN_DELAY_MIN', '8'))
    LINKEDIN_DELAY_MAX = float(os.getenv('LINKEDIN_DELAY_MAX', '15'))
    LINKEDIN_MAX_SCROLLS = int(os.getenv('LINKEDIN_MAX_SCROLLS', '5'))

    
       # ============================================
    # 🔍 WEB SEARCH CONFIGURATION
    # ============================================
    
    # Activer/désactiver le web search
    WEB_SEARCH_ENABLED = os.getenv('WEB_SEARCH_ENABLED', 'false').lower() == 'true'
    
    # API Serper.dev (optionnel, plus fiable que DuckDuckGo)
    SERPER_API_KEY = os.getenv('SERPER_API_KEY', '')
    
    # Paramètres de recherche
    WEB_SEARCH_MAX_RESULTS = int(os.getenv('WEB_SEARCH_MAX_RESULTS', '20'))
    WEB_SEARCH_MAX_PAGES = int(os.getenv('WEB_SEARCH_MAX_PAGES', '100'))
    WEB_SEARCH_DOWNLOAD_DOCS = os.getenv('WEB_SEARCH_DOWNLOAD_DOCS', 'true').lower() == 'true'
    
    # Dossier de téléchargement
    WEB_SEARCH_DOWNLOAD_FOLDER = os.getenv('WEB_SEARCH_DOWNLOAD_FOLDER', 'downloads/web_search')
    
    # Mots-clés personnalisés (override ceux du scraper)
    WEB_SEARCH_KEYWORDS = os.getenv('WEB_SEARCH_KEYWORDS', '').split('|') if os.getenv('WEB_SEARCH_KEYWORDS') else None