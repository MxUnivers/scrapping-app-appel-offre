from .base import BaseScraper
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class OnadCiScraper(BaseScraper):
    """Scraper pour onad.ci - Office National"""
    
    def __init__(self):
        super().__init__('ONAD.ci', 'https://onad.ci')
    
    def scrape(self):
        logger.info(f"🔄 Démarrage scraping {self.site_name}...")
        
        url = f"{self.base_url}/appels-doffres/"
        offres = self._scrape_paginated(url)
        
        logger.info(f"📦 {len(offres)} appels trouvés sur {self.site_name}")
        
        if offres:
            self.save_to_db(offres)
        
        return offres
    
    def _scrape_paginated(self, base_url):
        """Scrape avec pagination"""
        offres = []
        page = 1
        max_pages = 20
        
        while page <= max_pages:
            url = f"{base_url}page/{page}/" if page > 1 else base_url
            logger.info(f"   📄 Page {page}")
            
            html = self._make_request(url)
            if not html:
                break
            
            soup = self._parse_html(html)
            if not soup:
                break
            
            items = (soup.find_all('div', class_='post') or
                    soup.find_all('article') or
                    soup.find_all('div', class_='entry'))
            
            for item in items:
                try:
                    title_elem = item.find('h2') or item.find('h3') or item.find('a')
                    if not title_elem:
                        continue
                    title = title_elem.text.strip()
                    
                    if 'appel' not in title.lower() and 'offre' not in title.lower():
                        continue
                    
                    link_elem = item.find('a')
                    link = link_elem['href'] if link_elem else ''
                    if link and not link.startswith('http'):
                        link = self.base_url + '/' + link.lstrip('/')
                    
                    date_elem = item.find('time') or item.find('span', class_='date')
                    date_text = date_elem.text.strip() if date_elem else ''
                    date_pub = self._normalize_date(date_text)
                    
                    offre = {
                        'title': title,
                        'url': link,
                        'source_url': url,
                        'description': '',
                        'category': 'Office National',
                        'location': 'Côte d\'Ivoire',
                        'employment_type': 'Appel d\'offre',
                        'date_publication': date_pub,
                        'company_name': 'ONAD',
                        'tags': ['onad', 'office national', 'appel d\'offre'],
                        'scraped_at': datetime.utcnow().isoformat()
                    }
                    offres.append(offre)
                    
                except Exception as e:
                    logger.debug(f"   Erreur: {e}")
                    continue
            
            if not self._has_next(soup):
                break
            page += 1
        
        return offres
    
    def _has_next(self, soup):
        return bool(soup.find('a', class_='next') or soup.find('a', rel='next'))