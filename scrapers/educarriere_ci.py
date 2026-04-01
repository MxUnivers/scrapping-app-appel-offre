from .base import BaseScraper
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class EducarriereCiScraper(BaseScraper):
    """Scraper pour services.educarriere.ci/appelsdoffres/"""
    
    def __init__(self):
        super().__init__('Educarriere.ci', 'https://services.educarriere.ci')
    
    def scrape(self):
        logger.info(f"🔄 Démarrage scraping {self.site_name}...")
        all_offres = []
        
        base_url = f"{self.base_url}/appelsdoffres/"
        offres = self._scrape_paginated(base_url)
        all_offres.extend(offres)
        
        logger.info(f"📦 Total: {len(all_offres)} appels d'offres trouvés sur {self.site_name}")
        
        if all_offres:
            self.save_to_db(all_offres)
        
        return all_offres
    
    def _scrape_paginated(self, base_url):
        """Scrape avec pagination automatique"""
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
            
            # Sélecteurs adaptables
            containers = (soup.find_all('div', class_='offre-container') or
                         soup.find_all('article') or
                         soup.find_all('div', class_='card') or
                         soup.find_all('tr'))
            
            for container in containers:
                try:
                    # Titre
                    title_elem = (container.find('h3') or 
                                container.find('h4') or 
                                container.find('a', class_='title') or
                                container.find('td', class_='title'))
                    if not title_elem:
                        continue
                    title = title_elem.text.strip()
                    
                    # Lien
                    link_elem = container.find('a')
                    link = link_elem['href'] if link_elem else ''
                    if link and not link.startswith('http'):
                        link = self.base_url + link
                    
                    # Date
                    date_elem = (container.find('time') or 
                               container.find('span', class_='date') or
                               container.find('small'))
                    date_text = date_elem.text.strip() if date_elem else ''
                    date_pub = self._normalize_date(date_text)
                    
                    # Description courte
                    desc_elem = (container.find('p', class_='desc') or 
                               container.find('div', class_='summary'))
                    description = desc_elem.text.strip() if desc_elem else ''
                    
                    offre = {
                        'title': title,
                        'url': link,
                        'source_url': url,
                        'description': description[:500],
                        'category': 'Éducation/Formation',
                        'location': 'Côte d\'Ivoire',
                        'employment_type': 'Appel d\'offre',
                        'date_publication': date_pub,
                        'company_name': 'Educarriere CI',
                        'tags': ['éducation', 'formation', 'appel d\'offre'],
                        'scraped_at': datetime.utcnow().isoformat()
                    }
                    offres.append(offre)
                    
                except Exception as e:
                    logger.debug(f"   Erreur item: {e}")
                    continue
            
            # Vérifier pagination
            if not self._has_next_page(soup):
                break
            page += 1
        
        return offres
    
    def _has_next_page(self, soup):
        """Détecte s'il y a une page suivante"""
        selectors = [
            ('a', {'class': 'next'}),
            ('a', {'rel': 'next'}),
            ('a', {'string': 'Suivant'}),
            ('a', {'string': 'Next'}),
            ('li', {'class': 'next'}),
        ]
        for tag, attrs in selectors:
            if soup.find(tag, **attrs):
                return True
        return False