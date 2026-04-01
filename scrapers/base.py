from abc import ABC, abstractmethod
import requests
import time
import random
import logging
from datetime import datetime
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    """Classe de base pour tous les scrapers"""
    
    def __init__(self, site_name, base_url):
        self.site_name = site_name
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self._get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def _get_random_user_agent(self):
        """Retourne un User-Agent aléatoire"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        return random.choice(user_agents)
    
    def _make_request(self, url, timeout=30):
        """Fait une requête HTTP avec gestion d'erreurs"""
        try:
            time.sleep(random.uniform(2, 5))  # Respect du serveur
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur requête {url}: {e}")
            return None
    
    def _parse_html(self, html):
        """Parse le HTML avec BeautifulSoup"""
        if not html:
            return None
        return BeautifulSoup(html, 'html.parser')
    
    def _normalize_date(self, date_string):
        """Normalise les dates (à adapter selon le format du site)"""
        if not date_string:
            return datetime.utcnow()
        
        formats = [
            '%d/%m/%Y',
            '%Y-%m-%d',
            '%d %B %Y',
            '%d %b %Y',
            '%Y/%m/%d'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_string.strip(), fmt)
            except ValueError:
                continue
        
        return datetime.utcnow()
    
    @abstractmethod
    def scrape(self):
        """Méthode principale de scraping - à implémenter par chaque site"""
        pass
    
    def save_to_db(self, offres):
        """Sauvegarde les offres dans MongoDB"""
        from models.offre import Offre
        
        saved_count = 0
        for offre_data in offres:
            try:
                offre = Offre(
                    title=offre_data.get('title', ''),
                    url=offre_data.get('url', ''),
                    source=self.site_name,
                    source_url=offre_data.get('source_url', self.base_url),
                    description=offre_data.get('description', ''),
                    category=offre_data.get('category', ''),
                    location=offre_data.get('location', ''),
                    employment_type=offre_data.get('employment_type', 'CDI'),
                    date_publication=offre_data.get('date_publication'),
                    company_name=offre_data.get('company_name', ''),
                    tags=offre_data.get('tags', []),
                    content=offre_data,
                    scraper_version='1.0'
                )
                offre.save()
                saved_count += 1
                logger.info(f"✅ Offre sauvegardée: {offre.title[:50]}")
            except Exception as e:
                logger.error(f"❌ Erreur sauvegarde offre: {e}")
        
        logger.info(f"📊 {saved_count}/{len(offres)} offres sauvegardées pour {self.site_name}")
        return saved_count