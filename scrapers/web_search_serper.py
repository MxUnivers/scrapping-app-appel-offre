# scrapers/web_search_serper.py
from .base import BaseScraper
import logging
import requests
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class WebSearchSerperScraper(BaseScraper):
    """
    Scraper utilisant Serper.dev API pour la recherche Google
    https://serper.dev/ - 100 requêtes gratuites/mois
    """
    
    def __init__(self):
        super().__init__('WebSearch Serper', 'https://google.com')
        self.api_key = os.getenv('SERPER_API_KEY', '')
        self.api_url = 'https://google.serper.dev/search'
        
        self.keywords = [
            "appel d'offre Côte d'Ivoire site:ci",
            "marché public Abidjan",
            # ... tes mots-clés
        ]
    
    def scrape(self):
        if not self.api_key:
            logger.warning("⚠️  SERPER_API_KEY non configuré")
            return []
        
        all_offres = []
        
        for keyword in self.keywords:
            try:
                results = self._search_serper(keyword)
                for r in results:
                    offre = self._process_result(r, keyword)
                    if offre:
                        all_offres.append(offre)
            except Exception as e:
                logger.error(f"❌ Erreur Serper '{keyword}': {e}")
        
        return all_offres
    
    def _search_serper(self, query: str, num_results: int = 20) -> list:
        headers = {
            'X-API-KEY': self.api_key,
            'Content-Type': 'application/json'
        }
        payload = {
            'q': query,
            'num': num_results,
            'gl': 'ci',  # Côte d'Ivoire
            'hl': 'fr'
        }
        
        response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        return data.get('organic', [])
    
    def _process_result(self, result: dict, keyword: str) -> dict:
        return {
            'title': result.get('title', '')[:200],
            'url': result.get('link', ''),
            'source_url': result.get('link', ''),
            'description': result.get('snippet', '')[:500],
            'category': 'Web Search',
            'location': 'Côte d\'Ivoire',
            'employment_type': 'Appel d\'offre',
            'date_publication': datetime.utcnow(),
            'company_name': '',
            'tags': ['serper', 'web-search', keyword],
            'source_type': 'serper_api',
            'scraped_at': datetime.utcnow().isoformat()
        }