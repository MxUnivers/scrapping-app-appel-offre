from .base import BaseScraper
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class PriciCiScraper(BaseScraper):
    """Scraper pour prici.ci - 2 sections: travaux et fournitures"""
    
    def __init__(self):
        super().__init__('PRICI.ci', 'https://www.prici.ci')
    
    def scrape(self):
        logger.info(f"🔄 Démarrage scraping {self.site_name}...")
        all_offres = []
        
        # Deux sections principales
        sections = [
            ('/avis-d-appel-d-offres-de-travaux.html', 'Travaux'),
            ('/avis-d-appel-d-offres-de-fournitures.html', 'Fournitures'),
        ]
        
        for path, category in sections:
            url = f"{self.base_url}{path}"
            offres = self._scrape_section(url, category)
            all_offres.extend(offres)
        
        logger.info(f"📦 Total: {len(all_offres)} appels d'offres trouvés sur {self.site_name}")
        
        if all_offres:
            self.save_to_db(all_offres)
        
        return all_offres
    
    def _scrape_section(self, base_url, category):
        """Scrape une section avec pagination"""
        offres = []
        page = 1
        max_pages = 20
        
        while page <= max_pages:
            url = f"{base_url}?page={page}" if page > 1 else base_url
            logger.info(f"   📄 {category} - Page {page}")
            
            html = self._make_request(url)
            if not html:
                break
            
            soup = self._parse_html(html)
            if not soup:
                break
            
            # Adaptation flexibles aux sélecteurs
            items = (soup.find_all('div', class_='offre-item') or
                    soup.find_all('article') or
                    soup.find_all('div', class_='news-item') or
                    soup.find_all('li', class_='list-item') or
                    soup.find_all('tr'))
            
            for item in items:
                try:
                    title_elem = (item.find('h2') or item.find('h3') or 
                                item.find('a', class_='title') or
                                item.find('td'))
                    if not title_elem:
                        continue
                    
                    title = title_elem.text.strip()
                    if len(title) < 15:
                        continue
                    
                    # Lien
                    link_elem = item.find('a')
                    link = link_elem['href'] if link_elem else ''
                    if link:
                        if not link.startswith('http'):
                            link = self.base_url + '/' + link.lstrip('/')
                    
                    # Date
                    date_elem = (item.find('time') or item.find('span', class_='date') or
                               item.find('small'))
                    date_text = date_elem.text.strip() if date_elem else ''
                    date_pub = self._normalize_date(date_text)
                    
                    offre = {
                        'title': title,
                        'url': link,
                        'source_url': url,
                        'description': '',
                        'category': f'PRICI - {category}',
                        'location': 'Côte d\'Ivoire',
                        'employment_type': 'Appel d\'offre',
                        'date_publication': date_pub,
                        'company_name': 'PRICI',
                        'tags': ['prici', category.lower(), 'appel d\'offre'],
                        'scraped_at': datetime.utcnow().isoformat()
                    }
                    offres.append(offre)
                    
                except Exception as e:
                    logger.debug(f"   Erreur: {e}")
                    continue
            
            # Pagination check
            if not self._has_next(soup):
                break
            page += 1
        
        return offres
    
    def _has_next(self, soup):
        next_selectors = [
            {'class': 'next'}, {'rel': 'next'}, 
            {'string': 'Suivant'}, {'string': 'Next'},
            {'class': 'pagination-next'}
        ]
        for sel in next_selectors:
            if soup.find('a', **sel) or soup.find('li', **sel):
                return True
        return False