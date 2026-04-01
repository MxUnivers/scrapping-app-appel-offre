from mongoengine import Document, StringField, EmailField, BooleanField, DateTimeField, ListField
from datetime import datetime
import bcrypt

class User(Document):
    email = EmailField(required=True, unique=True)
    password = StringField(required=True)
    first_name = StringField(max_length=50, default='')
    last_name = StringField(max_length=50, default='')
    is_admin = BooleanField(default=False)
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    last_login = DateTimeField()
    
    # Préférences de notification
    notification_categories = ListField(StringField(), default=list)
    notification_frequency = StringField(
        choices=['daily', 'weekly', 'realtime'], 
        default='daily'
    )
    
    def set_password(self, password):
        """Hash le mot de passe"""
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
    
    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)
    
    def to_json(self):
        return {
            'id': str(self.id),
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'is_admin': self.is_admin,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
    
    meta = {
        'collection': 'users',
        'indexes': ['email', 'is_active']
    }