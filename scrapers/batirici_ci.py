from .base import BaseScraper
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class BatiriciCiScraper(BaseScraper):
    """Scraper pour batirici.ci - BTP et Construction"""
    
    def __init__(self):
        super().__init__('Batirici.ci', 'https://www.batirici.ci')
    
    def scrape(self):
        logger.info(f"🔄 Démarrage scraping {self.site_name}...")
        
        url = f"{self.base_url}/appels-doffres-cote-divoire/marches-prives/"
        offres = self._scrape_page(url)
        
        logger.info(f"📦 {len(offres)} marchés privés trouvés sur {self.site_name}")
        
        if offres:
            self.save_to_db(offres)
        
        return offres
    
    def _scrape_page(self, url):
        """Scrape la page des marchés privés"""
        offres = []
        
        html = self._make_request(url)
        if not html:
            return offres
        
        soup = self._parse_html(html)
        if not soup:
            return offres
        
        # Sites BTP: souvent des cartes ou listes
        items = (soup.find_all('div', class_='card') or
                soup.find_all('article', class_='post') or
                soup.find_all('div', class_='offre') or
                soup.find_all('li'))
        
        for item in items:
            try:
                title_elem = item.find('h2') or item.find('h3') or item.find('a', class_='title')
                if not title_elem:
                    continue
                title = title_elem.text.strip()
                
                # Filtrer BTP/Construction
                if not any(k in title.lower() for k in ['construction', 'btp', 'travaux', 'offre', 'marché']):
                    continue
                
                link_elem = item.find('a')
                link = link_elem['href'] if link_elem else url
                if link and not link.startswith('http'):
                    link = self.base_url + '/' + link.lstrip('/')
                
                date_elem = item.find('time') or item.find('span', class_='meta-date')
                date_text = date_elem.text.strip() if date_elem else ''
                date_pub = self._normalize_date(date_text)
                
                # Extraire localisation si présente
                location_elem = item.find('span', class_='location') or item.find('span', class_='city')
                location = location_elem.text.strip() if location_elem else 'Côte d\'Ivoire'
                
                offre = {
                    'title': title,
                    'url': link,
                    'source_url': url,
                    'description': '',
                    'category': 'BTP/Construction',
                    'location': location,
                    'employment_type': 'Marché Privé',
                    'date_publication': date_pub,
                    'company_name': '',
                    'tags': ['btp', 'construction', 'marché privé', 'batiment'],
                    'scraped_at': datetime.utcnow().isoformat()
                }
                offres.append(offre)
                
            except Exception as e:
                logger.debug(f"   Erreur: {e}")
                continue
        
        return offres