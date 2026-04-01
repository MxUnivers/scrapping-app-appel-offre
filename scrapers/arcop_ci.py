from .base import BaseScraper
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ArcopCiScraper(BaseScraper):
    """Scraper pour arcop.ci - Autorité de Régulation"""
    
    def __init__(self):
        super().__init__('ARCOP.ci', 'https://arcop.ci')
    
    def scrape(self):
        logger.info(f"🔄 Démarrage scraping {self.site_name}...")
        all_offres = []
        
        # Sections potentielles
        sections = [
            '/appels-offres',
            '/avis',
            '/marches-publics',
            '/actualites',
        ]
        
        for section in sections:
            url = f"{self.base_url}{section}"
            offres = self._scrape_section(url)
            all_offres.extend(offres)
        
        logger.info(f"📦 Total: {len(all_offres)} sur {self.site_name}")
        
        if all_offres:
            self.save_to_db(all_offres)
        
        return all_offres
    
    def _scrape_section(self, base_url):
        """Scrape une section avec pagination"""
        offres = []
        page = 1
        max_pages = 25
        
        while page <= max_pages:
            url = f"{base_url}?page={page}" if page > 1 else base_url
            logger.info(f"   📄 Page {page}: {base_url[-30:]}")
            
            html = self._make_request(url)
            if not html:
                break
            
            soup = self._parse_html(html)
            if not soup:
                break
            
            # Sélecteurs flexibles
            items = (soup.find_all('div', class_='item') or
                    soup.find_all('article') or
                    soup.find_all('div', class_='post') or
                    soup.find_all('li'))
            
            for item in items:
                try:
                    title_elem = item.find('h3') or item.find('h4') or item.find('a', class_='title')
                    if not title_elem:
                        continue
                    title = title_elem.text.strip()
                    
                    # Filtrer par mots-clés appels d'offres
                    if not self._is_relevant(title):
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
                        'category': 'Marché Public',
                        'location': 'Côte d\'Ivoire',
                        'employment_type': 'Appel d\'offre',
                        'date_publication': date_pub,
                        'company_name': 'ARCOP',
                        'tags': ['arcop', 'régulation', 'marché public'],
                        'scraped_at': datetime.utcnow().isoformat()
                    }
                    offres.append(offre)
                    
                except Exception as e:
                    logger.debug(f"   Erreur: {e}")
                    continue
            
            if not self._has_pagination(soup):
                break
            page += 1
        
        return offres
    
    def _is_relevant(self, title):
        keywords = ['appel', 'offre', 'marché', 'avis', 'consultance', 'tender', 'bid']
        return any(k in title.lower() for k in keywords)
    
    def _has_pagination(self, soup):
        return bool(soup.find('a', class_='next') or soup.find('a', rel='next') or 
                   soup.find('a', string='Suivant'))