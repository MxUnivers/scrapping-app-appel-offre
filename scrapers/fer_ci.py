from .base import BaseScraper
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class FerCiScraper(BaseScraper):
    """Scraper pour fer.ci - Fonds d'Entretien Routier"""
    
    def __init__(self):
        super().__init__('FER.ci', 'https://www.fer.ci')
    
    def scrape(self):
        logger.info(f"🔄 Démarrage scraping {self.site_name}...")
        
        url = f"{self.base_url}/appels_offre/resultats_appels_offre"
        offres = self._scrape_page(url)
        
        logger.info(f"📦 {len(offres)} résultats trouvés sur {self.site_name}")
        
        if offres:
            self.save_to_db(offres)
        
        return offres
    
    def _scrape_page(self, url):
        """Scrape la page des résultats"""
        offres = []
        
        html = self._make_request(url)
        if not html:
            return offres
        
        soup = self._parse_html(html)
        if not soup:
            return offres
        
        # Chercher les tableaux de résultats (typique des sites institutionnels)
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')[1:]  # Skip header
            for row in rows:
                try:
                    cols = row.find_all('td')
                    if len(cols) < 2:
                        continue
                    
                    # Extraction adaptative selon structure tableau
                    title = cols[0].text.strip() if len(cols) > 0 else ''
                    if not title or len(title) < 10:
                        continue
                    
                    # Date dans la 2ème ou 3ème colonne
                    date_text = ''
                    for i in range(1, min(4, len(cols))):
                        if self._looks_like_date(cols[i].text):
                            date_text = cols[i].text.strip()
                            break
                    
                    date_pub = self._normalize_date(date_text)
                    
                    # Lien si présent
                    link_elem = row.find('a')
                    link = link_elem['href'] if link_elem else url
                    if link and not link.startswith('http'):
                        link = self.base_url + '/' + link.lstrip('/')
                    
                    offre = {
                        'title': title,
                        'url': link,
                        'source_url': url,
                        'description': '',
                        'category': 'Infrastructures/Routes',
                        'location': 'Côte d\'Ivoire',
                        'employment_type': 'Résultat appel d\'offre',
                        'date_publication': date_pub,
                        'company_name': 'FER - Fonds d\'Entretien Routier',
                        'tags': ['routes', 'infrastructures', 'FER'],
                        'scraped_at': datetime.utcnow().isoformat()
                    }
                    offres.append(offre)
                    
                except Exception as e:
                    logger.debug(f"   Erreur row: {e}")
                    continue
        
        return offres
    
    def _looks_like_date(self, text):
        """Vérifie si un texte ressemble à une date"""
        import re
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'\d{4}-\d{1,2}-\d{1,2}',
            r'\d{1,2}\s+[a-zA-Z]+\s+\d{4}'
        ]
        return any(re.search(p, text) for p in date_patterns)