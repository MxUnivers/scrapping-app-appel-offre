from mongoengine import Document, EmailField, DateTimeField, BooleanField, ListField, StringField , IntField
from datetime import datetime

class EmailSubscription(Document):
    email = EmailField(required=True, unique=True)
    is_active = BooleanField(default=True)
    is_verified = BooleanField(default=False)
    verification_token = StringField()
    
    # Préférences
    categories = ListField(StringField(), default=['all'])
    sources = ListField(StringField(), default=['all'])
    frequency = StringField(choices=['daily', 'weekly'], default='daily')
    
    # Tracking
    last_sent = DateTimeField()
    total_sent = IntField(default=0)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    
    # Désabonnement
    unsubscribed_at = DateTimeField()
    unsubscribe_reason = StringField()
    
    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)
    
    def to_json(self):
        return {
            'id': str(self.id),
            'email': self.email,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'categories': self.categories,
            'sources': self.sources,
            'frequency': self.frequency,
            'last_sent': self.last_sent.isoformat() if self.last_sent else None,
            'total_sent': self.total_sent,
            'created_at': self.created_at.isoformat()
        }
    
    meta = {
        'collection': 'email_subscriptions',
        'indexes': ['email', 'is_active', 'is_verified']
    }