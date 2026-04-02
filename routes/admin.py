from flask import Blueprint, jsonify, request
from models.user import User
from models.offre import Offre
from models.subscription import EmailSubscription
from services.auth_service import auth_service
from services.email_service import email_service
from scrapers.manager import run_all_scrapers
import logging

logger = logging.getLogger(__name__)
admin_bp = Blueprint('admin', __name__)

def require_admin(f):
    """Décorateur pour requérir les droits admin"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({'status': 'error', 'message': 'Token requis'}), 401
        
        user = auth_service.verify_token(token)
        
        if not user or not user.is_admin:
            return jsonify({'status': 'error', 'message': 'Accès admin requis'}), 403
        
        request.current_user = user
        return f(*args, **kwargs)
    
    return decorated_function

@admin_bp.route('/dashboard', methods=['GET'])
@require_admin
def dashboard():
    """Tableau de bord admin"""
    try:
        total_users = User.objects.count()
        active_users = User.objects(is_active=True).count()
        total_offres = Offre.objects.count()
        active_offres = Offre.objects(is_active=True).count()
        total_subscribers = EmailSubscription.objects(is_active=True).count()
        
        # Dernières offres
        recent_offres = Offre.objects.order_by('-created_at').limit(10)
        
        return jsonify({
            'status': 'success',
            'data': {
                'total_users': total_users,
                'active_users': active_users,
                'total_offres': total_offres,
                'active_offres': active_offres,
                'total_subscribers': total_subscribers,
                'recent_offres': [o.to_json() for o in recent_offres]
            }
        })
    except Exception as e:
        logger.error(f"Erreur dashboard: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_bp.route('/scrape', methods=['POST'])
@require_admin
def trigger_scrape():
    """Déclencher manuellement le scraping"""
    try:
        result = run_all_scrapers()
        
        return jsonify({
            'status': 'success',
            'message': 'Scraping terminé',
            'data': result
        })
    except Exception as e:
        logger.error(f"Erreur trigger_scrape: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_bp.route('/users', methods=['GET'])
@require_admin
def get_users():
    """Lister tous les utilisateurs"""
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        
        skip = (page - 1) * limit
        users = User.objects.order_by('-created_at').skip(skip).limit(limit)
        total = User.objects.count()
        
        return jsonify({
            'status': 'success',
            'data': [u.to_json() for u in users],
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total
            }
        })
    except Exception as e:
        logger.error(f"Erreur get_users: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_bp.route('/users/<id>/toggle-active', methods=['POST'])
@require_admin
def toggle_user_active(id):
    """Activer/désactiver un utilisateur"""
    try:
        user = User.objects(id=id).first()
        if not user:
            return jsonify({'status': 'error', 'message': 'Utilisateur non trouvé'}), 404
        
        user.is_active = not user.is_active
        user.save()
        
        return jsonify({
            'status': 'success',
            'message': f'Utilisateur {"activé" if user.is_active else "désactivé"}',
            'data': user.to_json()
        })
    except Exception as e:
        logger.error(f"Erreur toggle_user_active: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_bp.route('/emails/send-digest', methods=['POST'])
@require_admin
def send_digest():
    """Envoyer manuellement le digest email"""
    try:
        count = email_service.send_daily_digest()
        
        return jsonify({
            'status': 'success',
            'message': f'Digest envoyé à {count} abonnés',
            'data': {'sent_count': count}
        })
    except Exception as e:
        logger.error(f"Erreur send_digest: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_bp.route('/offres', methods=['GET'])
@require_admin
def get_all_offres():
    """Lister toutes les offres (admin)"""
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        
        skip = (page - 1) * limit
        offres = Offre.objects.order_by('-created_at').skip(skip).limit(limit)
        total = Offre.objects.count()
        
        return jsonify({
            'status': 'success',
            'data': [o.to_json() for o in offres],
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total
            }
        })
    except Exception as e:
        logger.error(f"Erreur get_all_offres: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_bp.route('/emails/status', methods=['GET'])
@require_admin
def email_status():
    """Voir le statut de la configuration email"""
    try:
        status = email_service.get_email_status()
        return jsonify({
            'status': 'success',
            'data': status
        })
    except Exception as e:
        logger.error(f"Erreur email_status: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_bp.route('/emails/send-test', methods=['POST'])
@require_admin
def send_test_email():
    """
    Envoyer un email de test IMMÉDIATEMENT
    Payload JSON optionnel:
    {
        "recipient": "autre@email.com",  # Optionnel
        "subject": "Mon sujet perso",     # Optionnel
        "content": "<p>Mon contenu HTML</p>"  # Optionnel
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        
        result = email_service.send_test_email(
            recipient=data.get('recipient'),
            subject=data.get('subject'),
            content=data.get('content')
        )
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'message': 'Email de test envoyé!',
                'data': result
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f"Échec: {result.get('error')}",
                'data': result
            }), 500
            
    except Exception as e:
        logger.error(f"Erreur send_test_email: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_bp.route('/emails/send-digest-test', methods=['POST'])
@require_admin
def send_digest_test():
    """Envoyer le digest d'offres uniquement à l'admin (pour test)"""
    try:
        result = email_service.send_digest_to_admin_only()
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'message': f"Digest test envoyé ({result.get('sent', 0)} offres)",
                'data': result
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f"Échec: {result.get('error')}",
                'data': result
            }), 500
            
    except Exception as e:
        logger.error(f"Erreur send_digest_test: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_bp.route('/emails/toggle', methods=['POST'])
@require_admin
def toggle_email_sending():
    """
    Activer/Désactiver l'envoi automatique d'emails
    Payload: {"enabled": true/false}
    
    ⚠️  Note: Ce changement est temporaire (en mémoire).
    Pour un changement permanent, modifier .env et redémarrer.
    """
    try:
        data = request.get_json()
        new_state = data.get('enabled')
        
        if new_state is None:
            return jsonify({'status': 'error', 'message': 'Champ "enabled" requis'}), 400
        
        # Mise à jour temporaire (en mémoire seulement)
        current_app.config['EMAIL_SENDING_ENABLED'] = new_state
        
        logger.info(f"🔘 Email sending {'activé' if new_state else 'désactivé'} (session)")
        
        return jsonify({
            'status': 'success',
            'message': f"Envoi d'emails {'activé' if new_state else 'désactivé'}",
            'data': {
                'enabled': new_state,
                'note': 'Changement temporaire - redémarrez pour appliquer .env'
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur toggle_email: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_bp.route('/emails/update-schedule', methods=['POST'])
@require_admin
def update_email_schedule():
    """
    Modifier la fréquence d'envoi (temporaire)
    Payload: {"minutes": 5}
    """
    try:
        data = request.get_json()
        minutes = data.get('minutes')
        
        if not minutes or not isinstance(minutes, int) or minutes < 1:
            return jsonify({'status': 'error', 'message': 'Minutes valides requises (>=1)'}), 400
        
        # Mise à jour temporaire
        current_app.config['EMAIL_SCHEDULE_MINUTES'] = minutes
        
        # 🔁 Re-scheduler la tâche (si le scheduler est accessible)
        # Note: Pour une mise à jour dynamique du scheduler, 
        # il faudrait exposer le scheduler en variable globale ou via un service
        
        logger.info(f"🔄 Email schedule mis à jour: toutes les {minutes} minutes (session)")
        
        return jsonify({
            'status': 'success',
            'message': f'Fréquence mise à jour: {minutes} minutes',
            'data': {
                'minutes': minutes,
                'note': 'Changement temporaire - redémarrez pour appliquer .env'
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur update_schedule: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500