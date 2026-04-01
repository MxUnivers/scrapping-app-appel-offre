from mongoengine import (
    Document, StringField, URLField, DateTimeField, 
    BooleanField, DictField, ListField, FloatField, IntField
)
from datetime import datetime

class Offre(Document):
    # Informations de base
    title = StringField(required=True, max_length=200)
    url = URLField(required=True, unique=True)
    source = StringField(required=True, max_length=100)
    source_url = URLField()  # URL du site source
    
    # Contenu
    description = StringField(max_length=5000)
    content = DictField()  # Données brutes du scraping
    full_content = StringField(max_length=50000)  # Contenu complet
    
    # Classification
    category = StringField(max_length=100)
    subcategory = StringField(max_length=100)
    location = StringField(max_length=100)
    employment_type = StringField(
        choices=['CDI', 'CDD', 'Stage', 'Freelance', 'Appel d\'offre', 'Consultance'],
        default='CDI'
    )
    
    # Dates
    date_publication = DateTimeField()
    date_expiration = DateTimeField()
    date_scraped = DateTimeField(default=datetime.utcnow)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    
    # Statut
    is_active = BooleanField(default=True)
    is_sent = BooleanField(default=False)
    is_verified = BooleanField(default=False)
    
    # Métadonnées
    tags = ListField(StringField())
    salary_min = FloatField()
    salary_max = FloatField()
    salary_currency = StringField(default='XOF')
    company_name = StringField(max_length=200)
    
    # Scraping metadata
    scraper_version = StringField(default='1.0')
    scrape_attempts = IntField(default=0)
    
    def save(self, *args, **kwargs):
        self.updated_at = datetime.utcnow()
        return super().save(*args, **kwargs)
    
    def to_json(self):
        return {
            'id': str(self.id),
            'title': self.title,
            'url': self.url,
            'source': self.source,
            'category': self.category,
            'location': self.location,
            'employment_type': self.employment_type,
            'date_publication': self.date_publication.isoformat() if self.date_publication else None,
            'date_expiration': self.date_expiration.isoformat() if self.date_expiration else None,
            'is_active': self.is_active,
            'company_name': self.company_name,
            'tags': self.tags,
            'salary_range': f"{self.salary_min} - {self.salary_max} {self.salary_currency}" if self.salary_min else None
        }
    
    def to_json_full(self):
        data = self.to_json()
        data['description'] = self.description
        data['full_content'] = self.full_content
        data['content'] = self.content
        return data
    
    meta = {
        'collection': 'offres',
        'indexes': [
            'url',
            'source',
            'category',
            'location',
            'employment_type',
            'is_active',
            'date_publication',
            {'fields': ['$is_active', '$date_publication']},
            {'fields': ['$source', '$is_active']}
        ]
    }