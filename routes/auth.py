from flask import Blueprint, jsonify, request
from services.auth_service import auth_service
from models.user import User
import logging

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    """Inscription d'un nouvel utilisateur"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        
        if not email or not password:
            return jsonify({'status': 'error', 'message': 'Email et mot de passe requis'}), 400
        
        if len(password) < 6:
            return jsonify({'status': 'error', 'message': 'Mot de passe trop court (min 6 caractères)'}), 400
        
        result, error = auth_service.register_user(email, password, first_name, last_name)
        
        if error:
            return jsonify({'status': 'error', 'message': error}), 400
        
        return jsonify({
            'status': 'success',
            'message': 'Inscription réussie',
            'data': {
                'user': result['user'].to_json(),
                'token': result['token']
            }
        }), 201
    except Exception as e:
        logger.error(f"Erreur register: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """Connexion utilisateur"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'status': 'error', 'message': 'Email et mot de passe requis'}), 400
        
        result, error = auth_service.authenticate(email, password)
        
        if error:
            return jsonify({'status': 'error', 'message': error}), 401
        
        return jsonify({
            'status': 'success',
            'message': 'Connexion réussie',
            'data': {
                'user': result['user'].to_json(),
                'token': result['token']
            }
        })
    except Exception as e:
        logger.error(f"Erreur login: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    """Récupérer les infos de l'utilisateur connecté"""
    try:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return jsonify({'status': 'error', 'message': 'Token requis'}), 401
        
        user = auth_service.verify_token(token)
        
        if not user:
            return jsonify({'status': 'error', 'message': 'Token invalide'}), 401
        
        return jsonify({
            'status': 'success',
            'data': user.to_json()
        })
    except Exception as e:
        logger.error(f"Erreur get_current_user: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500