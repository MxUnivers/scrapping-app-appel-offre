from .base import BaseScraper
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class BceaoIntScraper(BaseScraper):
    """Scraper pour bceao.int - Banque Centrale"""
    
    def __init__(self):
        super().__init__('BCEAO.int', 'https://www.bceao.int')
    
    def scrape(self):
        logger.info(f"🔄 Démarrage scraping {self.site_name}...")
        
        url = f"{self.base_url}/fr/appels-offres/appels-offres-marches-publics-achats"
        offres = self._scrape_with_pagination(url)
        
        logger.info(f"📦 {len(offres)} marchés trouvés sur {self.site_name}")
        
        if offres:
            self.save_to_db(offres)
        
        return offres
    
    def _scrape_with_pagination(self, base_url):
        """Scrape avec pagination robuste"""
        offres = []
        page = 1
        max_pages = 30
        
        while page <= max_pages:
            url = f"{base_url}?page={page}" if page > 1 else base_url
            logger.info(f"   📄 Page {page}")
            
            html = self._make_request(url)
            if not html:
                break
            
            soup = self._parse_html(html)
            if not soup:
                break
            
            # BCEAO utilise souvent des listes structurées
            items = (soup.find_all('div', class_='item-list') or
                    soup.find_all('article') or
                    soup.find_all('div', class_='news') or
                    soup.find_all('tr', class_='row'))
            
            for item in items:
                try:
                    title_elem = item.find('h3') or item.find('h4') or item.find('a')
                    if not title_elem:
                        continue
                    title = title_elem.text.strip()
                    
                    if len(title) < 15 or 'appel' not in title.lower():
                        continue
                    
                    link_elem = item.find('a')
                    link = link_elem['href'] if link_elem else ''
                    if link and not link.startswith('http'):
                        link = self.base_url + link
                    
                    date_elem = item.find('time') or item.find('span', class_='date')
                    date_text = date_elem.text.strip() if date_elem else ''
                    date_pub = self._normalize_date(date_text)
                    
                    offre = {
                        'title': title,
                        'url': link,
                        'source_url': url,
                        'description': '',
                        'category': 'Finance/Banque',
                        'location': 'Zone UEMOA',
                        'employment_type': 'Marché Public',
                        'date_publication': date_pub,
                        'company_name': 'BCEAO',
                        'tags': ['bceao', 'banque centrale', 'UEMOA', 'marché public'],
                        'scraped_at': datetime.utcnow().isoformat()
                    }
                    offres.append(offre)
                    
                except Exception as e:
                    logger.debug(f"   Erreur: {e}")
                    continue
            
            # Pagination BCEAO
            if not soup.find('a', class_='next') and not soup.find('a', string='Suivant'):
                break
            page += 1
        
        return offres