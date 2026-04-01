from flask import Blueprint, jsonify, request
from models.offre import Offre
from models.subscription import EmailSubscription
from services.email_service import email_service
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
api_bp = Blueprint('api', __name__)

@api_bp.route('/offres', methods=['GET'])
def get_offres():
    """Récupérer toutes les offres actives avec pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        category = request.args.get('category')
        source = request.args.get('source')
        location = request.args.get('location')
        employment_type = request.args.get('employment_type')
        search = request.args.get('search')
        
        # Construire la requête
        query = {'is_active': True}
        
        if category:
            query['category'] = category
        if source:
            query['source'] = source
        if location:
            query['location'] = location
        if employment_type:
            query['employment_type'] = employment_type
        if search:
            query['title__icontains'] = search
        
        # Pagination
        skip = (page - 1) * limit
        offres = Offre.objects(**query)\
            .order_by('-date_publication')\
            .skip(skip)\
            .limit(limit)
        
        total = Offre.objects(**query).count()
        
        return jsonify({
            'status': 'success',
            'data': [offre.to_json() for offre in offres],
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'pages': (total + limit - 1) // limit if limit > 0 else 0
            }
        })
    except Exception as e:
        logger.error(f"Erreur get_offres: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api_bp.route('/offres/<id>', methods=['GET'])
def get_offre(id):
    """Récupérer une offre spécifique"""
    try:
        offre = Offre.objects(id=id).first()
        if not offre:
            return jsonify({'status': 'error', 'message': 'Offre non trouvée'}), 404
        
        return jsonify({
            'status': 'success',
            'data': offre.to_json_full()
        })
    except Exception as e:
        logger.error(f"Erreur get_offre: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api_bp.route('/offres/sources', methods=['GET'])
def get_sources():
    """Récupérer la liste des sources"""
    try:
        sources = Offre.objects.distinct('source')
        return jsonify({
            'status': 'success',
            'data': sources
        })
    except Exception as e:
        logger.error(f"Erreur get_sources: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api_bp.route('/offres/categories', methods=['GET'])
def get_categories():
    """Récupérer la liste des catégories"""
    try:
        categories = Offre.objects.distinct('category')
        return jsonify({
            'status': 'success',
            'data': categories
        })
    except Exception as e:
        logger.error(f"Erreur get_categories: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api_bp.route('/subscribe', methods=['POST'])
def subscribe():
    """S'abonner aux notifications email"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'status': 'error', 'message': 'Email requis'}), 400
        
        # Vérifier si déjà abonné
        existing = EmailSubscription.objects(email=email).first()
        if existing:
            return jsonify({'status': 'error', 'message': 'Déjà abonné'}), 400
        
        # Créer l'abonnement
        subscription = EmailSubscription(
            email=email,
            categories=data.get('categories', ['all']),
            sources=data.get('sources', ['all']),
            frequency=data.get('frequency', 'daily')
        )
        subscription.save()
        
        # Envoyer email de bienvenue
        email_service.send_welcome_email(email)
        
        return jsonify({
            'status': 'success',
            'message': 'Abonnement confirmé!',
            'data': subscription.to_json()
        }), 201
    except Exception as e:
        logger.error(f"Erreur subscribe: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api_bp.route('/unsubscribe/<email>', methods=['POST'])
def unsubscribe(email):
    """Se désabonner des notifications"""
    try:
        subscription = EmailSubscription.objects(email=email).first()
        if not subscription:
            return jsonify({'status': 'error', 'message': 'Abonnement non trouvé'}), 404
        
        subscription.is_active = False
        subscription.unsubscribed_at = datetime.utcnow()
        subscription.save()
        
        return jsonify({
            'status': 'success',
            'message': 'Désabonnement confirmé'
        })
    except Exception as e:
        logger.error(f"Erreur unsubscribe: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api_bp.route('/stats', methods=['GET'])
def get_stats():
    """Récupérer les statistiques"""
    try:
        total_offres = Offre.objects.count()
        active_offres = Offre.objects(is_active=True).count()
        total_subscribers = EmailSubscription.objects(is_active=True).count()
        
        # Offres par source
        sources_stats = []
        for source in Offre.objects.distinct('source'):
            count = Offre.objects(source=source, is_active=True).count()
            sources_stats.append({'source': source, 'count': count})
        
        # Offres par catégorie
        categories_stats = []
        for category in Offre.objects.distinct('category'):
            count = Offre.objects(category=category, is_active=True).count()
            categories_stats.append({'category': category, 'count': count})
        
        return jsonify({
            'status': 'success',
            'data': {
                'total_offres': total_offres,
                'active_offres': active_offres,
                'total_subscribers': total_subscribers,
                'by_source': sources_stats,
                'by_category': categories_stats
            }
        })
    except Exception as e:
        logger.error(f"Erreur get_stats: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500