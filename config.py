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

    # APRÈS (compatible Atlas + localhost)
    _mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
    _mongo_user = os.getenv('MONGODB_USER', '')
    _mongo_pass = os.getenv('MONGODB_PASS', '')

    # Ajouter user/pass seulement s'ils sont définis (sinon Atlas plante)
    if _mongo_user and _mongo_pass:
        MONGODB_SETTINGS['username'] = _mongo_user
        MONGODB_SETTINGS['password'] = _mongo_pass
        MONGODB_SETTINGS['authentication_source'] = 'admin'
    

    
    # Email (SMTP)
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    # BUG CORRIGÉ #2a : MAIL_DEFAULT_SENDER était vide → Flask-Mail refuse d'envoyer
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER') or os.getenv('MAIL_USERNAME', '')
    
    # =========================================================
    # BUG CORRIGÉ #2b : Variables email absentes du Config
    # email_service.py fait current_app.config['EMAIL_SENDING_ENABLED'] etc.
    # → KeyError si non définies ici
    # =========================================================
    EMAIL_SENDING_ENABLED = os.getenv('EMAIL_SENDING_ENABLED', 'true').lower() == 'true'
    EMAIL_TEST_MODE = os.getenv('EMAIL_TEST_MODE', 'false').lower() == 'true'
    EMAIL_SCHEDULE_MINUTES = int(os.getenv('EMAIL_SCHEDULE_MINUTES', '1440'))
    EMAIL_BATCH_LIMIT = int(os.getenv('EMAIL_BATCH_LIMIT', '20'))
    EMAIL_TEST_RECIPIENT = os.getenv('EMAIL_TEST_RECIPIENT') or os.getenv('DEFAULT_ADMIN_EMAIL', '')
    
    # Scheduler
    SCHEDULER_INTERVAL_MINUTES = int(os.getenv('SCHEDULER_INTERVAL', '5'))
    SCRAPING_ENABLED = os.getenv('SCRAPING_ENABLED', 'true').lower() == 'true'
    
    # Admin par défaut
    DEFAULT_ADMIN_EMAIL = os.getenv('DEFAULT_ADMIN_EMAIL', 'admin@cioffres.ci')
    DEFAULT_ADMIN_PASSWORD = os.getenv('DEFAULT_ADMIN_PASSWORD', 'Admin123!')
    DEFAULT_ADMIN_FIRST_NAME = os.getenv('DEFAULT_ADMIN_FIRST_NAME', 'Admin')
    DEFAULT_ADMIN_LAST_NAME = os.getenv('DEFAULT_ADMIN_LAST_NAME', 'CI Offres')
    
    # Admins additionnels (pour envoi emails)
    ADMIN_EMAILS = [
        e for e in [
            os.getenv('DEFAULT_ADMIN_EMAIL', ''),
            os.getenv('ADMIN_2_EMAIL', ''),
            os.getenv('ADMIN_3_EMAIL', ''),
        ] if e
    ]
    
    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    
    # LinkedIn
    LINKEDIN_MAX_RESULTS = int(os.getenv('LINKEDIN_MAX_RESULTS', '20'))
    LINKEDIN_DELAY_MIN = float(os.getenv('LINKEDIN_DELAY_MIN', '8'))
    LINKEDIN_DELAY_MAX = float(os.getenv('LINKEDIN_DELAY_MAX', '15'))
    LINKEDIN_MAX_SCROLLS = int(os.getenv('LINKEDIN_MAX_SCROLLS', '5'))
    
    # ============================================
    # WEB SEARCH CONFIGURATION
    # ============================================
    WEB_SEARCH_ENABLED = os.getenv('WEB_SEARCH_ENABLED', 'true').lower() == 'true'
    SERPER_API_KEY = os.getenv('SERPER_API_KEY', '')
    WEB_SEARCH_MAX_RESULTS = int(os.getenv('WEB_SEARCH_MAX_RESULTS', '20'))
    WEB_SEARCH_MAX_PAGES = int(os.getenv('WEB_SEARCH_MAX_PAGES', '100'))
    WEB_SEARCH_DOWNLOAD_DOCS = os.getenv('WEB_SEARCH_DOWNLOAD_DOCS', 'true').lower() == 'true'
    WEB_SEARCH_DOWNLOAD_FOLDER = os.getenv('WEB_SEARCH_DOWNLOAD_FOLDER', 'downloads/web_search')
    WEB_SEARCH_KEYWORDS = (
        os.getenv('WEB_SEARCH_KEYWORDS', '').split('|')
        if os.getenv('WEB_SEARCH_KEYWORDS') else None
    )

    # Frontend URL (pour les liens dans les emails)
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5000')
