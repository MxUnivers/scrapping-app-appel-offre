# scrapers/facebook_graph_api.py
import requests
from .base import BaseScraper
from datetime import datetime

class FacebookGraphApiScraper(BaseScraper):
    """Scraper utilisant l'API Graph officielle de Facebook"""
    
    def __init__(self, access_token: str, page_id: str = "cimarches"):
        super().__init__('Facebook Graph API', f'https://graph.facebook.com/{page_id}')
        self.access_token = access_token
        self.page_id = page_id
        self.api_base = "https://graph.facebook.com/v18.0"
    
    def scrape(self):
        """Récupère les posts via l'API Graph"""
        url = f"{self.api_base}/{self.page_id}/posts"
        params = {
            'access_token': self.access_token,
            'fields': 'message,created_time,permalink_url,full_picture',
            'limit': 25
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            offres = []
            for post in data.get('data', []):
                message = post.get('message', '')
                if not message or len(message) < 30:
                    continue
                
                # Filtrer pour appels d'offres uniquement
                if not self._is_relevant_text(message):
                    continue
                
                offre = {
                    'title': message[:150],
                    'url': post.get('permalink_url', f'https://facebook.com/{self.page_id}'),
                    'source_url': self.base_url,
                    'description': message[:500],
                    'category': 'Réseau Social',
                    'location': 'Côte d\'Ivoire',
                    'employment_type': 'Appel d\'offre',
                    'date_publication': self._normalize_date(post.get('created_time')),
                    'company_name': 'CI Marchés',
                    'tags': ['facebook', 'api-officielle', 'cimarches'],
                    'platform': 'Facebook Graph API',
                    'scraped_at': datetime.utcnow().isoformat(),
                    'post_id': post.get('id')
                }
                offres.append(offre)
            
            return offres
            
        except Exception as e:
            logger.error(f"❌ Erreur API Graph: {e}")
            return []
    
    def _is_relevant_text(self, text: str) -> bool:
        keywords = ['appel d\'offre', 'marché', 'consultance', 'tender', 'soumission']
        return any(k in text.lower() for k in keywords)