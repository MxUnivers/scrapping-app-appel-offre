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
from services.email_service import email_service
from datetime import datetime
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
    except Exception as e:
        logger.error(f"❌ Erreur connexion MongoDB: {e}")
        raise

    # Initialisation Email
    try:
        email_service.init_app(app)
        logger.info("✅ Service Email initialisé")
    except Exception as e:
        logger.warning(f"⚠️  Service Email: {e}")

    # Import des routes
    from routes.api import api_bp
    from routes.auth import auth_bp
    from routes.admin import admin_bp

    app.register_blueprint(api_bp,   url_prefix='/api')
    app.register_blueprint(auth_bp,  url_prefix='/auth')
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
                'api':    '/api/offres',
                'auth':   '/auth/login',
                'admin':  '/admin/dashboard',
                'health': '/health'
            }
        })

    # =========================================================
    # SCHEDULER
    # =========================================================
    scheduler = BackgroundScheduler()

    def scraping_job():
        """Tâche de scraping automatique"""
        # CORRIGÉ : app_context() requis car le scheduler tourne
        # dans un thread séparé sans contexte Flask
        with app.app_context():
            if not app.config.get('SCRAPING_ENABLED', True):
                logger.info("⏭️  Scraping désactivé - skip")
                return
            logger.info("🔄 [SCHEDULER] Démarrage du scraping automatique...")
            try:
                result = run_all_scrapers()
                logger.info(f"✅ [SCHEDULER] Scraping terminé: {result.get('total_offres', 0)} offres")
            except Exception as e:
                logger.error(f"❌ [SCHEDULER] Erreur scraping: {e}")

    def email_job():
        """Tâche d'envoi d'emails automatique (abonnés + admins)"""
        # CORRIGÉ : app_context() requis car email_service utilise
        # current_app, render_template etc. depuis un thread séparé
        with app.app_context():
            if not app.config.get('EMAIL_SENDING_ENABLED', True):
                logger.info("⏭️  Envoi emails désactivé - skip")
                return
            logger.info("📧 [SCHEDULER] Envoi des emails automatiques...")
            try:
                count = email_service.send_daily_digest_with_admins()
                logger.info(f"✅ [SCHEDULER] Emails envoyés à {count} destinataires")
            except Exception as e:
                logger.error(f"❌ [SCHEDULER] Erreur emails: {e}")

    # =========================================================
    # Jobs avec IDs uniques (évite l'écrasement)
    # =========================================================

    # Scraping selon intervalle défini dans .env (SCHEDULER_INTERVAL)
    scheduler.add_job(
        scraping_job,
        'interval',
        minutes=app.config['SCHEDULER_INTERVAL_MINUTES'],
        id='scraping_job',
        replace_existing=True
    )
    logger.info(f"✅ Scheduler scraping: toutes les {app.config['SCHEDULER_INTERVAL_MINUTES']} min")

    # Email tous les jours à 8h
    scheduler.add_job(
        email_job,
        'cron',
        hour=8,
        minute=0,
        id='email_job_8h',
        replace_existing=True
    )
    logger.info("✅ Scheduler emails: tous les jours à 8h00")

    # Email tous les jours à 11h
    scheduler.add_job(
        email_job,
        'cron',
        hour=11,
        minute=0,
        id='email_job_11h',
        replace_existing=True
    )
    logger.info("✅ Scheduler emails: tous les jours à 11h00")

    scheduler.start()

    import atexit
    atexit.register(lambda: scheduler.shutdown())

    logger.info("🚀 Application prête!")

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(
        debug=True,
        port=5000,
        host='0.0.0.0',
        use_reloader=False  # Important: évite de lancer 2 schedulers
    )