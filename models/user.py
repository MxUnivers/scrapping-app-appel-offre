from mongoengine import (
    Document, StringField, EmailField, BooleanField, 
    DateTimeField, ListField, IntField
)
from datetime import datetime, timedelta
import bcrypt
import secrets

class User(Document):
    # =============================================================================
    # CHAMPS DE BASE (Originaux - OBLIGATOIRES)
    # =============================================================================
    email = EmailField(required=True, unique=True)
    password = StringField(required=True)
    first_name = StringField(max_length=100, default='')
    last_name = StringField(max_length=100, default='')
    is_admin = BooleanField(default=False)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    last_login = DateTimeField()
    
    # Préférences de notification (IMPORTANT - manquant dans ta version)
    notification_categories = ListField(StringField(), default=list)
    notification_frequency = StringField(
        choices=['daily', 'weekly', 'realtime'], 
        default='daily'
    )
    
    # =============================================================================
    # CHAMPS DE SÉCURITÉ (Nouveaux - RECOMMANDÉS)
    # =============================================================================
    
    # Token de réinitialisation de mot de passe
    reset_password_token = StringField()
    reset_password_expires = DateTimeField()
    
    # Token de vérification d'email
    email_verification_token = StringField()
    email_verified = BooleanField(default=False)
    
    # Anti-brute force
    failed_login_attempts = IntField(default=0)
    locked_until = DateTimeField()
    
    # Rôle granulaire
    role = StringField(
        choices=['super_admin', 'admin', 'editor', 'viewer'],
        default='viewer'
    )
    
    # Métadonnées
    last_ip = StringField()
    user_agent = StringField()
    
    # =============================================================================
    # MÉTHODES DE MOT DE PASSE (OBLIGATOIRES - bcrypt)
    # =============================================================================
    
    def set_password(self, password):
        """Hash le mot de passe avec bcrypt"""
        self.password = bcrypt.hashpw(
            password.encode('utf-8'), 
            bcrypt.gensalt()
        ).decode('utf-8')
    
    def check_password(self, password):
        """Vérifie le mot de passe"""
        return bcrypt.checkpw(
            password.encode('utf-8'), 
            self.password.encode('utf-8')
        )
    
    # =============================================================================
    # MÉTHODE DE SAUVEGARDE (OBLIGATOIRE - updated_at auto)
    # =============================================================================
    
    def save(self, *args, **kwargs):
        """Met à jour updated_at automatiquement"""
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)
    
    # =============================================================================
    # MÉTHODES DE SÉCURITÉ (Nouvelles)
    # =============================================================================
    
    def generate_reset_token(self, expires_hours: int = 24) -> str:
        """Génère un token sécurisé pour réinitialisation de mot de passe"""
        self.reset_password_token = secrets.token_urlsafe(32)
        self.reset_password_expires = datetime.utcnow() + timedelta(hours=expires_hours)
        self.save()
        return self.reset_password_token
    
    def is_reset_token_valid(self, token: str) -> bool:
        """Vérifie si un token de réinitialisation est valide"""
        return (
            self.reset_password_token == token and
            self.reset_password_expires and
            self.reset_password_expires > datetime.utcnow()
        )
    
    def clear_reset_token(self):
        """Invalide le token de réinitialisation après usage"""
        self.reset_password_token = None
        self.reset_password_expires = None
        self.save()
    
    def record_failed_login(self):
        """Enregistre une tentative de connexion échouée"""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.locked_until = datetime.utcnow() + timedelta(minutes=30)
        self.save()
    
    def reset_failed_logins(self):
        """Réinitialise le compteur après un login réussi"""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_login = datetime.utcnow()
        self.save()
    
    def is_locked(self) -> bool:
        """Vérifie si le compte est verrouillé"""
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        if self.locked_until:
            self.locked_until = None
            self.failed_login_attempts = 0
            self.save()
        return False
    
    def has_permission(self, required_role: str) -> bool:
        """Vérifie les permissions par rôle (hiérarchie)"""
        hierarchy = {
            'super_admin': 4,
            'admin': 3,
            'editor': 2,
            'viewer': 1
        }
        user_level = hierarchy.get(self.role, 0)
        required_level = hierarchy.get(required_role, 0)
        return user_level >= required_level or self.is_admin
    
    # =============================================================================
    # MÉTHODES DE SÉRIALISATION (OBLIGATOIRES pour l'API)
    # =============================================================================
    
    def to_json(self):
        """Sérialisation standard pour l'API"""
        return {
            'id': str(self.id),
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'is_admin': self.is_admin,
            'role': self.role,
            'is_active': self.is_active,
            'email_verified': self.email_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
    
    def to_json_secure(self, include_sensitive: bool = False):
        """Version avec champs sensibles (pour l'utilisateur lui-même)"""
        data = self.to_json()
        if include_sensitive and self.is_admin:
            data['notification_categories'] = self.notification_categories
            data['notification_frequency'] = self.notification_frequency
        return data
    
    # =============================================================================
    # MÉTADONNÉES MONGODB (OBLIGATOIRE)
    # =============================================================================
    
    meta = {
        'collection': 'users',
        'indexes': [
            'email',
            'is_active',
            'is_admin',
            'role',
            {'fields': ['$email'], 'unique': True},
        ]
    }