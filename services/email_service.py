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

    # =========================================================
    # HELPER : variables communes pour les templates
    # =========================================================
    def _template_context(self):
        """Retourne les variables partagées par tous les templates"""
        return {
            'frontend_url':  current_app.config.get('FRONTEND_URL', 'http://localhost:5000'),
            'support_email': current_app.config.get('MAIL_USERNAME', 'support@cioffres.ci'),
        }

    # =========================================================
    # DIGEST QUOTIDIEN — abonnés + admins
    # =========================================================
    def send_daily_digest_with_admins(self):
        """
        Envoie le digest quotidien :
        1. Aux abonnés EmailSubscription actifs (frequency='daily')
        2. Aux admins (User.is_admin=True + ADMIN_EMAILS du config)
        """
        total_sent = 0

        # --- 1. Abonnés EmailSubscription ---
        try:
            subscriptions = EmailSubscription.objects(
                is_active=True,
                frequency='daily'
            )
            for sub in subscriptions:
                if self.send_offres_email(sub):
                    total_sent += 1
        except Exception as e:
            logger.error(f"❌ Erreur digest abonnés: {e}")

        # --- 2. Admins ---
        try:
            from models.user import User
            admin_emails = [
                u.email for u in User.objects(is_admin=True, is_active=True)
            ]
            config_admins = current_app.config.get('ADMIN_EMAILS', [])
            all_admin_emails = list(set(admin_emails + config_admins))

            if all_admin_emails:
                result = self._send_offres_to_emails(all_admin_emails, tag="[ADMIN]")
                if result:
                    total_sent += len(all_admin_emails)
        except Exception as e:
            logger.error(f"❌ Erreur digest admins: {e}")

        logger.info(f"📧 Digest envoyé à {total_sent} destinataires au total")
        return total_sent

    def _send_offres_to_emails(self, emails: list, days_back: int = 1, tag: str = ""):
        """Envoie les offres récentes à une liste d'adresses email"""
        try:
            since = datetime.utcnow() - timedelta(days=days_back)
            offres = Offre.objects(
                is_active=True,
                date_publication__gte=since
            ).order_by('-date_publication').limit(
                current_app.config.get('EMAIL_BATCH_LIMIT', 20)
            )

            if not offres:
                logger.info(f"ℹ️  Aucune offre récente ({tag}) - aucun email envoyé")
                return False

            ctx = self._template_context()
            html_content = render_template(
                'email_offres.html',
                offres=offres,
                email=", ".join(emails),
                date=datetime.now().strftime('%d/%m/%Y'),
                count=offres.count(),
                **ctx                           # ← frontend_url + support_email
            )

            msg = Message(
                subject=f"🇨🇮 {tag} CI Offres - {offres.count()} nouvelles opportunités",
                recipients=emails,
                html=html_content
            )
            self.mail.send(msg)
            logger.info(f"✅ Email {tag} envoyé à {emails} ({offres.count()} offres)")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur envoi {tag} à {emails}: {e}")
            return False

    # =========================================================
    # ENVOI À UN ABONNÉ
    # =========================================================
    def send_offres_email(self, subscription):
        """Envoie les nouvelles offres par email à un abonné"""
        try:
            last_sent = subscription.last_sent or (datetime.utcnow() - timedelta(days=1))

            query = {
                'is_active': True,
                'date_publication__gte': last_sent
            }

            if subscription.categories and 'all' not in subscription.categories:
                query['category__in'] = subscription.categories

            offres = Offre.objects(**query).order_by('-date_publication').limit(10)

            if not offres:
                logger.info(f"Aucune nouvelle offre pour {subscription.email}")
                return False

            ctx = self._template_context()
            html_content = render_template(
                'email_offres.html',
                offres=offres,
                email=subscription.email,
                date=datetime.now().strftime('%d/%m/%Y'),
                count=offres.count(),
                **ctx                           # ← frontend_url + support_email
            )

            msg = Message(
                subject=f"🇨🇮 CI Offres - {offres.count()} nouvelles opportunités",
                recipients=[subscription.email],
                html=html_content
            )
            self.mail.send(msg)

            # Marquer offres + abonnement
            for offre in offres:
                offre.is_sent = True
                offre.save()

            subscription.last_sent = datetime.utcnow()
            subscription.total_sent += 1
            subscription.save()

            logger.info(f"✅ Email envoyé à {subscription.email} ({offres.count()} offres)")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur envoi email à {subscription.email}: {e}")
            return False

    # =========================================================
    # EMAIL DE BIENVENUE
    # =========================================================
    def send_welcome_email(self, email):
        """Envoie un email de bienvenue"""
        try:
            ctx = self._template_context()
            html_content = render_template(
                'email_welcome.html',
                email=email,
                **ctx                           # ← frontend_url + support_email
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

    # =========================================================
    # RÉINITIALISATION MOT DE PASSE
    # =========================================================
    def send_password_reset(self, email, token):
        """Envoie un email de réinitialisation de mot de passe"""
        try:
            ctx = self._template_context()
            reset_link = f"{ctx['frontend_url']}/reset-password/{token}"
            html_content = render_template(
                'email_reset.html',
                email=email,
                reset_link=reset_link,
                **ctx                           # ← frontend_url + support_email
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

    # =========================================================
    # EMAIL DE TEST
    # =========================================================
    def send_test_email(self, recipient: str = None, subject: str = None, content: str = None):
        """Envoie un email de test immédiat"""
        try:
            to_email    = recipient or current_app.config['EMAIL_TEST_RECIPIENT']
            test_mode   = current_app.config['EMAIL_TEST_MODE']
            mail_server = current_app.config['MAIL_SERVER']
            mail_port   = current_app.config['MAIL_PORT']

            test_subject = subject or f"🧪 TEST EMAIL - CI Offres - {datetime.now().strftime('%H:%M:%S')}"
            test_content = content or f"""
            <h2>✅ Email de Test Réussi!</h2>
            <p>Cet email a été envoyé automatiquement par CI Offres.</p>
            <hr>
            <p><strong>Détails du test :</strong></p>
            <ul>
                <li>🕐 Heure    : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</li>
                <li>🎯 Destinataire : {to_email}</li>
                <li>🔧 Mode     : {'TEST' if test_mode else 'PRODUCTION'}</li>
                <li>📡 Serveur  : {mail_server}:{mail_port}</li>
            </ul>
            <hr>
            <p style="color:#666;font-size:12px;">
                Si tu reçois cet email, ta configuration SMTP fonctionne! 🎉
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
                'success':   True,
                'recipient': to_email,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Erreur envoi email test: {e}")
            return {
                'success':   False,
                'error':     str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    # =========================================================
    # DIGEST TEST — admins seulement
    # =========================================================
    def send_digest_to_admin_only(self):
        """Envoie le digest uniquement aux admins (sans spammer les abonnés)"""
        try:
            admin_emails = current_app.config.get('ADMIN_EMAILS', [])
            if not admin_emails:
                admin_emails = [current_app.config['DEFAULT_ADMIN_EMAIL']]

            recent_offres = Offre.objects(is_active=True)\
                .order_by('-date_publication')\
                .limit(current_app.config.get('EMAIL_BATCH_LIMIT', 20))

            if not recent_offres:
                logger.info("ℹ️  Aucune offre récente à envoyer")
                return {'success': True, 'sent': 0, 'reason': 'no_offres'}

            ctx = self._template_context()
            html_content = render_template(
                'email_offres.html',
                offres=recent_offres,
                email=", ".join(admin_emails),
                date=datetime.now().strftime('%d/%m/%Y'),
                count=recent_offres.count(),
                **ctx                           # ← frontend_url + support_email
            )

            msg = Message(
                subject=f"🧪 [TEST ADMIN] {recent_offres.count()} offres CI - {datetime.now().strftime('%H:%M')}",
                recipients=admin_emails,
                html=html_content
            )
            self.mail.send(msg)

            logger.info(f"✅ Digest test → admins: {admin_emails} ({recent_offres.count()} offres)")
            return {
                'success':    True,
                'sent':       recent_offres.count(),
                'recipients': admin_emails
            }
        except Exception as e:
            logger.error(f"❌ Erreur digest test: {e}")
            return {'success': False, 'error': str(e)}

    # =========================================================
    # RÉTROCOMPATIBILITÉ
    # =========================================================
    def send_daily_digest(self):
        """Alias — appelle la méthode complète"""
        return self.send_daily_digest_with_admins()

    # =========================================================
    # STATUT EMAIL
    # =========================================================
    def get_email_status(self):
        """Retourne le statut de la configuration email"""
        return {
            'enabled':          current_app.config['EMAIL_SENDING_ENABLED'],
            'test_mode':        current_app.config['EMAIL_TEST_MODE'],
            'schedule_minutes': current_app.config['EMAIL_SCHEDULE_MINUTES'],
            'batch_limit':      current_app.config['EMAIL_BATCH_LIMIT'],
            'smtp_configured':  bool(
                current_app.config['MAIL_USERNAME'] and
                current_app.config['MAIL_PASSWORD']
            ),
            'smtp_server':      f"{current_app.config['MAIL_SERVER']}:{current_app.config['MAIL_PORT']}",
            'test_recipient':   current_app.config['EMAIL_TEST_RECIPIENT'],
            'admin_emails':     current_app.config.get('ADMIN_EMAILS', []),
            'frontend_url':     current_app.config.get('FRONTEND_URL', ''),
            'total_subscribers': EmailSubscription.objects(is_active=True).count(),
            'last_check':       datetime.utcnow().isoformat()
        }


email_service = EmailService()