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

email_service = EmailService()