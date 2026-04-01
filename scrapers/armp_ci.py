from .base import BaseScraper
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ArmpScraper(BaseScraper):
    """Scraper pour ARMP (Autorité de Régulation des Marchés Publics)"""
    
    def __init__(self):
        super().__init__('ARMP', 'https://www.armp.ci')
    
    def scrape(self):
        """Scrape les appels d'offres sur ARMP"""
        logger.info(f"🔄 Démarrage scraping {self.site_name}...")
        offres = []
        
        urls_to_scrape = [
            f'{self.base_url}/avis-appel-offres',
            f'{self.base_url}/marches-publics',
            f'{self.base_url}/avis?page=1'
        ]
        
        for url in urls_to_scrape:
            html = self._make_request(url)
            if not html:
                continue
            
            soup = self._parse_html(html)
            if not soup:
                continue
            
            # NOTE: Ces sélecteurs sont à adapter selon la structure réelle du site ARMP
            appel_elements = soup.find_all('div', class_='avis-item') or \
                           soup.find_all('article', class_='appel-offre') or \
                           soup.find_all('div', class_='marche-public')
            
            for element in appel_elements[:10]:
                try:
                    title_elem = element.find('h2') or element.find('h3') or element.find('a', class_='title')
                    title = title_elem.text.strip() if title_elem else 'Appel d\'offre'
                    
                    link_elem = element.find('a')
                    link = link_elem['href'] if link_elem else ''
                    if link and not link.startswith('http'):
                        link = self.base_url + link
                    
                    date_elem = element.find('span', class_='date') or element.find('time')
                    date_text = date_elem.text.strip() if date_elem else ''
                    date_publication = self._normalize_date(date_text)
                    
                    # Détection du type d'appel d'offre
                    employment_type = 'Appel d\'offre'
                    if 'consultance' in title.lower():
                        employment_type = 'Consultance'
                    elif 'marché' in title.lower():
                        employment_type = 'Marché Public'
                    
                    offre_data = {
                        'title': title,
                        'url': link,
                        'source_url': url,
                        'description': '',
                        'category': 'Appel d\'offre',
                        'location': 'Côte d\'Ivoire',
                        'employment_type': employment_type,
                        'date_publication': date_publication,
                        'company_name': 'Gouvernement CI',
                        'tags': ['marché public', 'appel d\'offre', 'ARMP'],
                        'scraped_at': datetime.utcnow().isoformat()
                    }
                    
                    offres.append(offre_data)
                    
                except Exception as e:
                    logger.error(f"Erreur parsing appel d'offre: {e}")
                    continue
        
        logger.info(f"📦 {len(offres)} appels d'offres trouvés sur {self.site_name}")
        
        if offres:
            self.save_to_db(offres)
        
        return offres