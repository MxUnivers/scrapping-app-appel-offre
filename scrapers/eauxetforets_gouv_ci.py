from .base import BaseScraper
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class EauxEtForetsGouvCiScraper(BaseScraper):
    """Scraper pour eauxetforets.gouv.ci - Ministère"""
    
    def __init__(self):
        super().__init__('Eaux&Forêts.gouv.ci', 'https://eauxetforets.gouv.ci')
    
    def scrape(self):
        logger.info(f"🔄 Démarrage scraping {self.site_name}...")
        
        url = f"{self.base_url}/actualite/avis-dappel-doffres"
        offres = self._scrape_page(url)
        
        logger.info(f"📦 {len(offres)} avis trouvés sur {self.site_name}")
        
        if offres:
            self.save_to_db(offres)
        
        return offres
    
    def _scrape_page(self, url):
        """Scrape la page des avis"""
        offres = []
        
        html = self._make_request(url)
        if not html:
            return offres
        
        soup = self._parse_html(html)
        if not soup:
            return offres
        
        # Les sites gouvernementaux utilisent souvent des listes ou articles
        items = (soup.find_all('article', class_='actualite') or
                soup.find_all('div', class_='news-item') or
                soup.find_all('li', class_='list-item') or
                soup.find_all('div', class_='post'))
        
        for item in items:
            try:
                title_elem = item.find('h2') or item.find('h3') or item.find('a')
                if not title_elem:
                    continue
                title = title_elem.text.strip()
                
                # Vérifier pertinence
                if 'appel' not in title.lower() and 'offre' not in title.lower():
                    continue
                
                link_elem = item.find('a')
                link = link_elem['href'] if link_elem else url
                if link and not link.startswith('http'):
                    link = self.base_url + '/' + link.lstrip('/')
                
                # Date
                date_elem = item.find('time') or item.find('span', class_='date')
                date_text = date_elem.text.strip() if date_elem else ''
                date_pub = self._normalize_date(date_text)
                
                # Description
                desc_elem = item.find('p', class_='excerpt') or item.find('div', class_='summary')
                description = desc_elem.text.strip() if desc_elem else ''
                
                offre = {
                    'title': title,
                    'url': link,
                    'source_url': url,
                    'description': description[:500],
                    'category': 'Environnement/Eaux & Forêts',
                    'location': 'Côte d\'Ivoire',
                    'employment_type': 'Appel d\'offre',
                    'date_publication': date_pub,
                    'company_name': 'Ministère Eaux et Forêts CI',
                    'tags': ['environnement', 'eaux', 'forêts', 'gouvernement'],
                    'scraped_at': datetime.utcnow().isoformat()
                }
                offres.append(offre)
                
            except Exception as e:
                logger.debug(f"   Erreur: {e}")
                continue
        
        return offres