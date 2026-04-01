import jwt
from datetime import datetime, timedelta
from models.user import User
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class AuthService:
    def generate_token(self, user):
        """Génère un token JWT pour un utilisateur"""
        try:
            payload = {
                'user_id': str(user.id),
                'email': user.email,
                'is_admin': user.is_admin,
                'exp': datetime.utcnow() + current_app.config['JWT_ACCESS_TOKEN_EXPIRES'],
                'iat': datetime.utcnow()
            }
            
            token = jwt.encode(
                payload,
                current_app.config['JWT_SECRET_KEY'],
                algorithm='HS256'
            )
            
            return token
        except Exception as e:
            logger.error(f"Erreur génération token: {e}")
            return None
    
    def verify_token(self, token):
        """Vérifie et décode un token JWT"""
        try:
            payload = jwt.decode(
                token,
                current_app.config['JWT_SECRET_KEY'],
                algorithms=['HS256']
            )
            
            user = User.objects(id=payload['user_id']).first()
            if not user or not user.is_active:
                return None
            
            return user
        except jwt.ExpiredSignatureError:
            logger.warning("Token expiré")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"Token invalide: {e}")
            return None
    
    def authenticate(self, email, password):
        """Authentifie un utilisateur"""
        try:
            user = User.objects(email=email).first()
            
            if not user:
                return None, "Utilisateur non trouvé"
            
            if not user.is_active:
                return None, "Compte désactivé"
            
            if not user.check_password(password):
                return None, "Mot de passe incorrect"
            
            # Mettre à jour last_login
            user.last_login = datetime.utcnow()
            user.save()
            
            token = self.generate_token(user)
            
            return {
                'user': user,
                'token': token
            }, None
        except Exception as e:
            logger.error(f"Erreur authentification: {e}")
            return None, str(e)
    
    def register_user(self, email, password, first_name='', last_name=''):
        """Inscrit un nouvel utilisateur"""
        try:
            # Vérifier si l'email existe déjà
            existing = User.objects(email=email).first()
            if existing:
                return None, "Email déjà utilisé"
            
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_admin=False,
                is_active=True
            )
            user.set_password(password)
            user.save()
            
            token = self.generate_token(user)
            
            return {
                'user': user,
                'token': token
            }, None
        except Exception as e:
            logger.error(f"Erreur inscription: {e}")
            return None, str(e)

auth_service = AuthService()