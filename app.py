#!/usr/bin/env python3
"""
CI Offres Aggregator - Application Principale
Point d'entrée de l'application Flask
"""

from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from mongoengine import connect
from config import Config
from apscheduler.schedulers.background import BackgroundScheduler
from scrapers.manager import run_all_scrapers
from scripts.create_admin import create_default_admin
from services.email_service import email_service
from models.subscription import EmailSubscription
from datetime import datetime, timedelta
import logging
import os

# Configuration des logs
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def create_app():
    """Factory pattern pour créer l'application Flask"""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # CORS pour API
    CORS(app, origins=["*"])
    
    # JWT
    JWTManager(app)
    
    # Connexion MongoDB
    try:
        connect(**app.config['MONGODB_SETTINGS'])
        logger.info("✅ Connecté à MongoDB")
        create_default_admin()
    except Exception as e:
        logger.error(f"❌ Erreur connexion MongoDB: {e}")
        raise
    
    # Initialisation Email
    try:
        email_service.init_app(app)
        logger.info("✅ Service Email initialisé")
    except Exception as e:
        logger.warning(f"⚠️  Service Email: {e}")
    
    # Import des routes (après init pour éviter circular import)
    from routes.api import api_bp
    from routes.auth import auth_bp
    from routes.admin import admin_bp
    
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    # Route santé
    @app.route('/health')
    def health():
        return jsonify({
            'status': 'running',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0'
        })
    
    @app.route('/')
    def index():
        return jsonify({
            'name': 'CI Offres Aggregator',
            'version': '1.0.0',
            'endpoints': {
                'api': '/api/offres',
                'auth': '/auth/login',
                'admin': '/admin/dashboard',
                'health': '/health'
            }
        })
    
    # Scheduler
    scheduler = BackgroundScheduler()
    
    def scraping_job():
        """Tâche de scraping automatique"""
        if not app.config.get('SCRAPING_ENABLED', True):
            logger.info("⏭️  Scraping désactivé - skip")
            return
        logger.info("🔄 [SCHEDULER] Démarrage du scraping automatique...")
        # logger.info("🔄 [SCHEDULER] Démarrage du scraping automatique...")
        try:
            result = run_all_scrapers()
            logger.info(f"✅ [SCHEDULER] Scraping terminé: {result.get('total_offres', 0)} offres")
        except Exception as e:
            logger.error(f"❌ [SCHEDULER] Erreur scraping: {e}")
    
    def email_job():
        """Tâche d'envoi d'emails automatique"""
        if not current_app.config.get('EMAIL_SENDING_ENABLED', True):
            logger.info("⏭️  Envoi emails désactivé - skip")
            return
        
        logger.info("📧 [SCHEDULER] Envoi des emails automatiques...")
        try:
            count = email_service.send_daily_digest()
            logger.info(f"✅ [SCHEDULER] Emails envoyés à {count} abonnés")
        except Exception as e:
            logger.error(f"❌ [SCHEDULER] Erreur emails: {e}")
    
    # Planifier les tâches
    scheduler.add_job(
        scraping_job,
        'interval',
        minutes=app.config['SCHEDULER_INTERVAL_MINUTES'],
        id='scraping_job',
        replace_existing=True
    )
    logger.info(f"✅ Scheduler scraping configuré (toutes les {app.config['SCHEDULER_INTERVAL_MINUTES']} min)")
    
    scheduler.add_job(
        email_job,
        'cron',
        hour=8,  # Tous les jours à 8h
        id='email_job',
        replace_existing=True
    )
    logger.info("✅ Scheduler emails configuré (tous les jours à 8h)")
    
    scheduler.add_job(
        email_job,
        'cron',
        hour=11,  # Tous les jours à 11h
        id='email_job',
        replace_existing=True
    )
    logger.info("✅ Scheduler emails configuré (tous les jours à 11h)")

    # Planifier emails (fréquence configurable via EMAIL_SCHEDULE_MINUTES)
    # scheduler.add_job(
    #     email_job,
    #     'interval',
    #     minutes=app.config['EMAIL_SCHEDULE_MINUTES'],
    #     id='email_job',
    #     replace_existing=True,
    #     # Ne pas lancer au démarrage, attendre le premier intervalle
    #     next_run_time=datetime.utcnow() + timedelta(minutes=app.config['EMAIL_SCHEDULE_MINUTES'])
    # )
    
    scheduler.start()
    # logger.info(f"✅ Scheduler démarré - Emails: {app.config['EMAIL_SCHEDULE_MINUTES']}min")
    
    # Shutdown handler
    import atexit
    
    atexit.register(lambda: scheduler.shutdown())
    
    logger.info("🚀 Application prête à démarrer!")
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(
        debug=True,
        port=5000,
        host='0.0.0.0',
        use_reloader=False  # Important pour ne pas lancer 2 schedulers
    )