from .base import BaseScraper
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class MarchesPublicsCiScraper(BaseScraper):
    """Scraper pour marchespublics.ci - Portail officiel"""
    
    def __init__(self):
        super().__init__('MarchesPublics.ci', 'https://www.marchespublics.ci')
    
    def scrape(self):
        logger.info(f"🔄 Démarrage scraping {self.site_name}...")
        all_offres = []
        
        # Sections à scraper
        sections = [
            ('/appel_offre', 'Appel d\'offre'),
            ('/avis_attribution', 'Avis d\'attribution'),
            ('/avis_appel_offre', 'Avis AAP'),
        ]
        
        for path, tender_type in sections:
            url = f"{self.base_url}{path}"
            offres = self._scrape_section(url, tender_type)
            all_offres.extend(offres)
        
        logger.info(f"📦 Total: {len(all_offres)} appels d'offres trouvés sur {self.site_name}")
        
        if all_offres:
            self.save_to_db(all_offres)
        
        return all_offres
    
    def _scrape_section(self, base_url, tender_type):
        """Scrape une section avec pagination complète"""
        offres = []
        page = 1
        max_pages = 50  # Sites officiels peuvent avoir beaucoup de pages
        
        while page <= max_pages:
            url = f"{base_url}?page={page}" if page > 1 else base_url
            logger.info(f"   📄 Page {page}: {url[:60]}...")
            
            html = self._make_request(url)
            if not html:
                break
            
            soup = self._parse_html(html)
            if not soup:
                break
            
            # Adaptation aux sélecteurs probables du site
            items = (soup.find_all('div', class_='offre') or 
                    soup.find_all('article') or 
                    soup.find_all('tr', class_='row-offre') or
                    soup.find_all('li', class_='item'))
            
            if not items:
                # Essayer d'autres sélecteurs courants
                items = soup.find_all('table')
                if items:
                    items = items[0].find_all('tr')[1:]  # Skip header
            
            for item in items:
                try:
                    title_elem = (item.find('a', class_='title') or 
                                item.find('h3') or 
                                item.find('h4') or
                                item.find('td', class_='title'))
                    
                    if not title_elem:
                        continue
                    
                    title = title_elem.text.strip()
                    if len(title) < 10:  # Filtrer les titres trop courts
                        continue
                    
                    link_elem = item.find('a')
                    link = link_elem['href'] if link_elem else ''
                    if link and not link.startswith('http'):
                        link = self.base_url + link
                    
                    # Extraire date
                    date_elem = (item.find('span', class_='date') or 
                               item.find('time') or
                               item.find('td', class_='date'))
                    date_text = date_elem.text.strip() if date_elem else ''
                    date_pub = self._normalize_date(date_text)
                    
                    # Extraire référence/marché
                    ref_elem = item.find('span', class_='ref') or item.find('td', class_='ref')
                    reference = ref_elem.text.strip() if ref_elem else ''
                    
                    offre = {
                        'title': title,
                        'url': link,
                        'source_url': url,
                        'description': f"Référence: {reference}" if reference else '',
                        'category': 'Marché Public',
                        'location': 'Côte d\'Ivoire',
                        'employment_type': tender_type,
                        'date_publication': date_pub,
                        'company_name': 'Gouvernement CI',
                        'tags': ['marché public', 'CI', tender_type],
                        'reference': reference,
                        'scraped_at': datetime.utcnow().isoformat()
                    }
                    offres.append(offre)
                    
                except Exception as e:
                    logger.debug(f"   Erreur: {e}")
                    continue
            
            # Pagination: vérifier bouton suivant
            next_exists = (soup.find('a', class_='next') or 
                          soup.find('a', string='Suivant') or
                          soup.find('li', class_='next'))
            
            if not next_exists:
                break
            
            page += 1
        
        return offres