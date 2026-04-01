from .base import BaseScraper
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class EmploiCiScraper(BaseScraper):
    """Scraper pour Emploi.ci"""
    
    def __init__(self):
        super().__init__('Emploi.ci', 'https://www.emploi.ci')
    
    def scrape(self):
        """Scrape les offres d'emploi sur Emploi.ci"""
        logger.info(f"🔄 Démarrage scraping {self.site_name}...")
        offres = []
        
        urls_to_scrape = [
            f'{self.base_url}/offres-emploi',
            f'{self.base_url}/offres-emploi?page=2',
            f'{self.base_url}/offres-emploi?page=3'
        ]
        
        for url in urls_to_scrape:
            html = self._make_request(url)
            if not html:
                continue
            
            soup = self._parse_html(html)
            if not soup:
                continue
            
            # NOTE: Ces sélecteurs sont à adapter selon la structure réelle du site
            # Inspecte le site avec F12 pour trouver les bons sélecteurs
            offre_elements = soup.find_all('div', class_='offre-item') or \
                           soup.find_all('article', class_='job-listing') or \
                           soup.find_all('div', class_='job-card')
            
            for element in offre_elements[:10]:  # Limite à 10 par page pour test
                try:
                    title_elem = element.find('h2') or element.find('h3') or element.find('a', class_='title')
                    title = title_elem.text.strip() if title_elem else 'Sans titre'
                    
                    link_elem = element.find('a')
                    link = link_elem['href'] if link_elem else ''
                    if link and not link.startswith('http'):
                        link = self.base_url + link
                    
                    date_elem = element.find('span', class_='date') or element.find('time')
                    date_text = date_elem.text.strip() if date_elem else ''
                    date_publication = self._normalize_date(date_text)
                    
                    location_elem = element.find('span', class_='location') or element.find('span', class_='city')
                    location = location_elem.text.strip() if location_elem else ''
                    
                    offre_data = {
                        'title': title,
                        'url': link,
                        'source_url': url,
                        'description': '',
                        'category': 'Emploi',
                        'location': location,
                        'employment_type': 'CDI',
                        'date_publication': date_publication,
                        'company_name': '',
                        'tags': [],
                        'scraped_at': datetime.utcnow().isoformat()
                    }
                    
                    offres.append(offre_data)
                    
                except Exception as e:
                    logger.error(f"Erreur parsing offre: {e}")
                    continue
        
        logger.info(f"📦 {len(offres)} offres trouvées sur {self.site_name}")
        
        if offres:
            self.save_to_db(offres)
        
        return offres