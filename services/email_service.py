from flask_mail import Mail, Message
from flask import render_template, current_app
from models.offre import Offre
from models.subscription import EmailSubscription
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, app=None):
        self.mail = Mail()
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        self.mail.init_app(app)
    
    def send_offres_email(self, subscription):
        """Envoie les nouvelles offres par email à un abonné"""
        try:
            # Récupérer les offres non envoyées
            last_sent = subscription.last_sent or (datetime.utcnow() - timedelta(days=1))
            
            query = {
                'is_active': True,
                'date_publication__gte': last_sent
            }
            
            # Filtrer par catégories si nécessaire
            if subscription.categories and 'all' not in subscription.categories:
                query['category__in'] = subscription.categories
            
            offres = Offre.objects(**query).order_by('-date_publication').limit(10)
            
            if not offres:
                logger.info(f"Aucune nouvelle offre pour {subscription.email}")
                return False
            
            # Générer le contenu HTML
            html_content = render_template(
                'email_offres.html',
                offres=offres,
                email=subscription.email,
                date=datetime.now().strftime('%d/%m/%Y'),
                count=offres.count()
            )
            
            # Créer le message
            msg = Message(
                subject=f"🇨🇮 CI Offres - {offres.count()} nouvelles opportunités",
                recipients=[subscription.email],
                html=html_content
            )
            
            self.mail.send(msg)
            
            # Marquer les offres comme envoyées
            for offre in offres:
                offre.is_sent = True
                offre.save()
            
            # Mettre à jour l'abonnement
            subscription.last_sent = datetime.utcnow()
            subscription.total_sent += 1
            subscription.save()
            
            logger.info(f"✅ Email envoyé à {subscription.email} ({offres.count()} offres)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur envoi email à {subscription.email}: {e}")
            return False
    
    def send_welcome_email(self, email):
        """Envoie un email de bienvenue"""
        try:
            html_content = render_template(
                'email_welcome.html',
                email=email
            )
            
            msg = Message(
                subject="🎉 Bienvenue sur CI Offres!",
                recipients=[email],
                html=html_content
            )
            
            self.mail.send(msg)
            logger.info(f"✅ Email de bienvenue envoyé à {email}")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur email bienvenue: {e}")
            return False
    
    def send_password_reset(self, email, token):
        """Envoie un email de réinitialisation de mot de passe"""
        try:
            reset_link = f"{current_app.config.get('FRONTEND_URL', 'http://localhost:5000')}/reset-password/{token}"
            
            html_content = render_template(
                'email_reset.html',
                email=email,
                reset_link=reset_link
            )
            
            msg = Message(
                subject="🔑 Réinitialisation de mot de passe - CI Offres",
                recipients=[email],
                html=html_content
            )
            
            self.mail.send(msg)
            return True
        except Exception as e:
            logger.error(f"❌ Erreur email reset: {e}")
            return False
    
    def send_daily_digest(self):
        """Envoie le récapitulatif quotidien à tous les abonnés"""
        try:
            subscriptions = EmailSubscription.objects(
                is_active=True,
                frequency='daily'
            )
            
            sent_count = 0
            for sub in subscriptions:
                if self.send_offres_email(sub):
                    sent_count += 1
            
            logger.info(f"📧 Digest quotidien envoyé à {sent_count} abonnés")
            return sent_count
        except Exception as e:
            logger.error(f"❌ Erreur digest quotidien: {e}")
            return 0
    def send_test_email(self, recipient: str = None, subject: str = None, content: str = None):
        """
        Envoie un email de test immédiat
        """
        try:
            # Destinataire de test
            to_email = recipient or current_app.config['EMAIL_TEST_RECIPIENT']
            
            # Sujet et contenu par défaut
            test_subject = subject or f"🧪 TEST EMAIL - CI Offres - {datetime.now().strftime('%H:%M:%S')}"
            test_content = content or f"""
            <h2>✅ Email de Test Réussi!</h2>
            <p>Cet email a été envoyé automatiquement par ton application CI Offres.</p>
            <hr>
            <p><strong>Détails du test:</strong></p>
            <ul>
                <li>🕐 Heure: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</li>
                <li>🎯 Destinataire: {to_email}</li>
                <li>🔧 Mode: {'TEST' if current_app.config['EMAIL_TEST_MODE'] else 'PRODUCTION'}</li>
                <li>📡 Serveur: {current_app.config['MAIL_SERVER']}:{current_app.config['MAIL_PORT']}</li>
            </ul>
            <hr>
            <p style="color: #666; font-size: 12px;">
                Si tu reçois cet email, ta configuration SMTP fonctionne correctement! 🎉
            </p>
            """
            
            msg = Message(
                subject=test_subject,
                recipients=[to_email],
                html=test_content
            )
            
            self.mail.send(msg)
            
            logger.info(f"✅ Email de test envoyé à {to_email}")
            return {
                'success': True,
                'recipient': to_email,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur envoi email test: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def send_digest_to_admin_only(self):
        """
        Envoie le digest uniquement à l'admin (pour test sans spammer les abonnés)
        """
        try:
            admin_email = current_app.config['DEFAULT_ADMIN_EMAIL']
            
            # Récupérer les dernières offres
            recent_offres = Offre.objects(is_active=True)\
                .order_by('-date_publication')\
                .limit(current_app.config['EMAIL_BATCH_LIMIT'])
            
            if not recent_offres:
                logger.info("ℹ️  Aucune offre récente à envoyer")
                return {'success': True, 'sent': 0, 'reason': 'no_offres'}
            
            # Générer le contenu
            html_content = render_template(
                'email_offres.html',
                offres=recent_offres,
                email=admin_email,
                date=datetime.now().strftime('%d/%m/%Y'),
                count=recent_offres.count()
            )
            
            msg = Message(
                subject=f"🧪 [TEST] {recent_offres.count()} offres CI - {datetime.now().strftime('%H:%M')}",
                recipients=[admin_email],
                html=html_content
            )
            
            self.mail.send(msg)
            
            logger.info(f"✅ Digest test envoyé à l'admin ({recent_offres.count()} offres)")
            return {
                'success': True,
                'sent': recent_offres.count(),
                'recipient': admin_email
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur digest test: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_email_status(self):
        """
        Retourne le statut de la configuration email
        """
        from models.subscription import EmailSubscription
        
        return {
            'enabled': current_app.config['EMAIL_SENDING_ENABLED'],
            'test_mode': current_app.config['EMAIL_TEST_MODE'],
            'schedule_minutes': current_app.config['EMAIL_SCHEDULE_MINUTES'],
            'batch_limit': current_app.config['EMAIL_BATCH_LIMIT'],
            'smtp_configured': bool(current_app.config['MAIL_USERNAME'] and current_app.config['MAIL_PASSWORD']),
            'smtp_server': f"{current_app.config['MAIL_SERVER']}:{current_app.config['MAIL_PORT']}",
            'test_recipient': current_app.config['EMAIL_TEST_RECIPIENT'],
            'admin_email': current_app.config['DEFAULT_ADMIN_EMAIL'],
            'total_subscribers': EmailSubscription.objects(is_active=True).count(),
            'last_check': datetime.utcnow().isoformat()
        }


email_service = EmailService()